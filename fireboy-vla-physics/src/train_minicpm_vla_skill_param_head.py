from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from build_vla_skill_param_manifest import PARAM_NAMES, SKILL_NAMES
from train_articulated_policy import state_from_row
from train_minicpm_vla_action_head import (
    apply_minicpm_chat_template,
    first_model_device,
    load_embedding_cache,
    load_minicpm,
    manifest_state_to_training_row,
    save_embedding_cache,
)


MODEL_ID = "openbmb/MiniCPM-V-4.6"


@dataclass
class SkillParamSample:
    image_path: Path
    instruction: str
    task: str
    skill: str
    state: list[float]
    skill_id: int
    target_params: list[float]


class MiniCPMSkillParamHead:
    def __init__(
        self,
        input_dim: int,
        skill_count: int,
        param_dim: int,
        hidden_dim: int = 512,
    ):
        import torch
        from torch import nn

        class Head(nn.Module):
            def __init__(self, input_dim: int, skill_count: int, param_dim: int, hidden_dim: int):
                super().__init__()
                self.trunk = nn.Sequential(
                    nn.Linear(input_dim, hidden_dim),
                    nn.SiLU(),
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.SiLU(),
                )
                self.skill_head = nn.Linear(hidden_dim, skill_count)
                self.param_head = nn.Linear(hidden_dim, param_dim)

            def forward(self, x: Any) -> tuple[Any, Any]:
                h = self.trunk(x)
                return self.skill_head(h), self.param_head(h)

        self.torch = torch
        self.model = Head(input_dim, skill_count, param_dim, hidden_dim)

    def to(self, device: Any) -> "MiniCPMSkillParamHead":
        self.model.to(device)
        return self

    def parameters(self):
        return self.model.parameters()

    def __call__(self, x: Any) -> tuple[Any, Any]:
        return self.model(x)

    def state_dict(self) -> dict[str, Any]:
        return self.model.state_dict()

    def load_state_dict(self, state_dict: dict[str, Any]) -> None:
        self.model.load_state_dict(state_dict)

    def eval(self) -> None:
        self.model.eval()


def train_minicpm_vla_skill_param_head(
    manifests: list[Path],
    out_dir: Path,
    *,
    model_id: str = MODEL_ID,
    max_steps: int = 900,
    limit_rows: int = 1024,
    state_mode: str = "nav_clock",
    include_stage_flags: bool = True,
    downsample_mode: str = "16x",
    max_slice_nums: int = 9,
    val_fraction: float = 0.16,
    seed: int = 29,
    embedding_cache: Path | None = None,
    skill_loss_weight: float = 1.0,
    param_loss_weight: float = 0.35,
) -> dict[str, Any]:
    try:
        import torch
        from torch.nn import functional as F
    except ImportError as exc:
        raise RuntimeError("Install torch before training the MiniCPM-V skill-param head") from exc

    samples = load_skill_param_samples(
        manifests,
        limit_rows=limit_rows,
        state_mode=state_mode,
        include_stage_flags=include_stage_flags,
    )
    if not samples:
        raise RuntimeError(f"No usable skill-param samples in manifests: {manifests}")

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(samples))
    val_count = max(1, int(round(len(samples) * val_fraction))) if len(samples) > 8 else 1
    val_indices = set(int(i) for i in order[:val_count])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cache = load_embedding_cache(embedding_cache)
    processor, minicpm = load_minicpm(model_id)
    minicpm.eval()
    for param in minicpm.parameters():
        param.requires_grad_(False)

    embeddings: list[np.ndarray] = []
    cache_hits = 0
    for index, sample in enumerate(samples):
        cache_key = make_skill_param_cache_key(sample, model_id, downsample_mode, max_slice_nums)
        if cache_key in cache:
            embedding = cache[cache_key]
            cache_hits += 1
        else:
            embedding = encode_minicpm_skill_param_prompt(
                processor,
                minicpm,
                sample.image_path,
                sample.instruction,
                downsample_mode=downsample_mode,
                max_slice_nums=max_slice_nums,
            )
            cache[cache_key] = embedding
        embeddings.append(embedding)
        if (index + 1) % 50 == 0:
            print(json.dumps({"encoded": index + 1, "total": len(samples), "cache_hits": cache_hits}), file=sys.stderr, flush=True)
    save_embedding_cache(embedding_cache, cache)

    vl = np.asarray(embeddings, dtype=np.float32)
    states = np.asarray([sample.state for sample in samples], dtype=np.float32)
    params = np.asarray([sample.target_params for sample in samples], dtype=np.float32)
    skill_ids = np.asarray([sample.skill_id for sample in samples], dtype=np.int64)

    vl_mean, vl_std = vl.mean(axis=0), vl.std(axis=0) + 1e-6
    state_mean, state_std = states.mean(axis=0), states.std(axis=0) + 1e-6
    param_mean = params.mean(axis=0)
    param_std = np.maximum(params.std(axis=0), 1e-4) + 1e-6

    features = np.concatenate([(vl - vl_mean) / vl_std, (states - state_mean) / state_std], axis=1)
    param_targets = (params - param_mean) / param_std
    train_mask = np.asarray([index not in val_indices for index in range(len(samples))], dtype=bool)
    if not train_mask.any():
        train_mask[:] = True

    xt = torch.tensor(features[train_mask], dtype=torch.float32, device=device)
    skill_t = torch.tensor(skill_ids[train_mask], dtype=torch.long, device=device)
    param_t = torch.tensor(param_targets[train_mask], dtype=torch.float32, device=device)
    xv = torch.tensor(features[~train_mask], dtype=torch.float32, device=device) if (~train_mask).any() else xt[:1]
    skill_v = torch.tensor(skill_ids[~train_mask], dtype=torch.long, device=device) if (~train_mask).any() else skill_t[:1]
    param_v = torch.tensor(param_targets[~train_mask], dtype=torch.float32, device=device) if (~train_mask).any() else param_t[:1]

    head = MiniCPMSkillParamHead(
        input_dim=features.shape[1],
        skill_count=len(SKILL_NAMES),
        param_dim=len(PARAM_NAMES),
    ).to(device)
    opt = torch.optim.AdamW(head.parameters(), lr=2.5e-4, weight_decay=1e-4)
    batch = min(128, xt.shape[0])
    history: list[dict[str, float]] = []
    for step in range(max_steps):
        idx = torch.randint(0, xt.shape[0], (batch,), device=device)
        skill_logits, param_pred = head(xt[idx])
        skill_loss = F.cross_entropy(skill_logits, skill_t[idx])
        param_loss = F.mse_loss(param_pred, param_t[idx])
        loss = skill_loss_weight * skill_loss + param_loss_weight * param_loss
        opt.zero_grad()
        loss.backward()
        opt.step()
        if step % 50 == 0 or step == max_steps - 1:
            with torch.no_grad():
                val_skill_logits, val_param_pred = head(xv)
                val_skill_loss = F.cross_entropy(val_skill_logits, skill_v)
                val_param_loss = F.mse_loss(val_param_pred, param_v)
                train_acc = float((skill_logits.argmax(dim=-1) == skill_t[idx]).float().mean().detach().cpu())
                val_acc = float((val_skill_logits.argmax(dim=-1) == skill_v).float().mean().detach().cpu())
            history.append(
                {
                    "step": float(step),
                    "loss": float(loss.detach().cpu()),
                    "skill_loss": float(skill_loss.detach().cpu()),
                    "param_loss": float(param_loss.detach().cpu()),
                    "train_skill_accuracy": train_acc,
                    "val_skill_accuracy": val_acc,
                    "val_skill_loss": float(val_skill_loss.detach().cpu()),
                    "val_param_loss": float(val_param_loss.detach().cpu()),
                }
            )

    val_metrics = evaluate_head_arrays(
        head,
        xv,
        skill_v,
        param_v,
        param_mean,
        param_std,
        device=device,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = out_dir / "minicpm_vla_skill_param_head.pt"
    torch.save(
        {
            "head": {key: value.detach().cpu() for key, value in head.state_dict().items()},
            "model_id": model_id,
            "downsample_mode": downsample_mode,
            "max_slice_nums": int(max_slice_nums),
            "state_mean": state_mean,
            "state_std": state_std,
            "vl_mean": vl_mean,
            "vl_std": vl_std,
            "param_mean": param_mean,
            "param_std": param_std,
            "state_dim": int(states.shape[1]),
            "vl_dim": int(vl.shape[1]),
            "input_dim": int(features.shape[1]),
            "skill_count": len(SKILL_NAMES),
            "param_dim": len(PARAM_NAMES),
            "skill_names": list(SKILL_NAMES),
            "param_names": list(PARAM_NAMES),
            "state_mode": state_mode,
            "include_stage_flags": include_stage_flags,
            "policy_kind": "minicpm_vla_frozen_encoder_skill_param_head_v1",
            "lora_rank": 0,
            "manifests": [str(path) for path in manifests],
            "note": (
                "MiniCPM-V 4.6 is frozen here. This predicts a stable pet skill plus "
                "continuous skill parameters, then dispatches to verified MuJoCo policies."
            ),
        },
        checkpoint,
    )
    return {
        "checkpoint": str(checkpoint),
        "model_id": model_id,
        "rows": len(samples),
        "train_rows": int(train_mask.sum()),
        "val_rows": int((~train_mask).sum()),
        "device": str(device),
        "vl_dim": int(vl.shape[1]),
        "state_dim": int(states.shape[1]),
        "input_dim": int(features.shape[1]),
        "skill_names": list(SKILL_NAMES),
        "param_names": list(PARAM_NAMES),
        "state_mode": state_mode,
        "cache_hits": cache_hits,
        "history": history[-10:],
        "val_metrics": val_metrics,
    }


def load_skill_param_samples(
    manifests: list[Path],
    *,
    limit_rows: int,
    state_mode: str,
    include_stage_flags: bool,
) -> list[SkillParamSample]:
    samples: list[SkillParamSample] = []
    for manifest in manifests:
        with manifest.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw = json.loads(line)
                image_path = Path(str(raw.get("image_path", "")))
                if not image_path.exists():
                    continue
                state_raw = manifest_state_to_training_row(raw)
                state = state_from_row(state_raw, include_stage_flags=include_stage_flags, state_mode=state_mode)
                skill = str(raw.get("skill") or SKILL_NAMES[int(raw.get("skill_id", 0))])
                if skill not in SKILL_NAMES:
                    continue
                samples.append(
                    SkillParamSample(
                        image_path=image_path,
                        instruction=str(raw.get("instruction") or skill.replace("_", " ")),
                        task=str(raw.get("task") or skill),
                        skill=skill,
                        state=state,
                        skill_id=int(SKILL_NAMES.index(skill)),
                        target_params=[float(value) for value in raw.get("target_params", [0.0] * len(PARAM_NAMES))],
                    )
                )
                if len(samples) >= limit_rows:
                    return samples
    return samples


def evaluate_head_arrays(
    head: MiniCPMSkillParamHead,
    features: Any,
    skill_targets: Any,
    param_targets: Any,
    param_mean: np.ndarray,
    param_std: np.ndarray,
    *,
    device: Any,
) -> dict[str, Any]:
    import torch

    with torch.no_grad():
        skill_logits, param_pred = head(features)
        pred_ids = skill_logits.argmax(dim=-1)
        skill_accuracy = float((pred_ids == skill_targets).float().mean().detach().cpu())
        pred_params = param_pred.detach().cpu().numpy() * param_std + param_mean
        true_params = param_targets.detach().cpu().numpy() * param_std + param_mean
    abs_error = np.abs(pred_params - true_params)
    confusion = np.zeros((len(SKILL_NAMES), len(SKILL_NAMES)), dtype=np.int64)
    for true_id, pred_id in zip(skill_targets.detach().cpu().numpy(), pred_ids.detach().cpu().numpy(), strict=False):
        confusion[int(true_id), int(pred_id)] += 1
    return {
        "skill_accuracy": skill_accuracy,
        "param_mae": float(abs_error.mean()),
        "param_mae_by_name": {
            name: float(abs_error[:, index].mean()) for index, name in enumerate(PARAM_NAMES)
        },
        "confusion": confusion.tolist(),
        "skill_names": list(SKILL_NAMES),
    }


def encode_minicpm_skill_param_prompt(
    processor: Any,
    model: Any,
    image_path: Path,
    instruction: str,
    *,
    downsample_mode: str,
    max_slice_nums: int,
) -> np.ndarray:
    import torch

    prompt = (
        "You are the vision-language planner for Fire Boy in a MuJoCo toy room. "
        "From the image, command, and robot state, choose the next pet skill and "
        "its continuous parameters. Valid skills are: "
        f"{', '.join(SKILL_NAMES)}. Command: {instruction}."
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "url": str(image_path)},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    try:
        inputs = apply_minicpm_chat_template(processor, messages, downsample_mode, max_slice_nums)
    except Exception:
        image = Image.open(image_path).convert("RGB")
        messages[0]["content"][0] = {"type": "image", "image": image}
        inputs = apply_minicpm_chat_template(processor, messages, downsample_mode, max_slice_nums)

    device = first_model_device(model)
    inputs = inputs.to(device)
    with torch.inference_mode():
        outputs = model(**inputs, output_hidden_states=True, return_dict=True)
    hidden_states = getattr(outputs, "hidden_states", None)
    if not hidden_states:
        raise RuntimeError("MiniCPM forward did not return hidden_states; cannot train skill-param head.")
    last_hidden = hidden_states[-1].float()
    attention = inputs.get("attention_mask")
    if attention is not None:
        mask = attention.to(last_hidden.device).unsqueeze(-1).float()
        pooled = (last_hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
    else:
        pooled = last_hidden.mean(dim=1)
    return pooled.squeeze(0).detach().cpu().numpy().astype(np.float32)


def make_skill_param_cache_key(sample: SkillParamSample, model_id: str, downsample_mode: str, max_slice_nums: int) -> str:
    return "|".join(
        [
            "skill_param_v1",
            model_id,
            downsample_mode,
            str(max_slice_nums),
            str(sample.image_path),
            sample.instruction,
        ]
    )


def parse_path_list(values: list[Path] | None) -> list[Path]:
    return [Path(value) for value in values or []]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--max-steps", type=int, default=900)
    parser.add_argument("--limit-rows", type=int, default=1024)
    parser.add_argument("--state-mode", choices=["full", "clock", "nav_clock"], default="nav_clock")
    parser.add_argument("--include-stage-flags", action="store_true", default=True)
    parser.add_argument("--no-stage-flags", action="store_false", dest="include_stage_flags")
    parser.add_argument("--downsample-mode", default="16x")
    parser.add_argument("--max-slice-nums", type=int, default=9)
    parser.add_argument("--val-fraction", type=float, default=0.16)
    parser.add_argument("--seed", type=int, default=29)
    parser.add_argument("--embedding-cache", type=Path)
    parser.add_argument("--skill-loss-weight", type=float, default=1.0)
    parser.add_argument("--param-loss-weight", type=float, default=0.35)
    args = parser.parse_args()
    result = train_minicpm_vla_skill_param_head(
        parse_path_list(args.manifest),
        args.out_dir,
        model_id=args.model_id,
        max_steps=args.max_steps,
        limit_rows=args.limit_rows,
        state_mode=args.state_mode,
        include_stage_flags=args.include_stage_flags,
        downsample_mode=args.downsample_mode,
        max_slice_nums=args.max_slice_nums,
        val_fraction=args.val_fraction,
        seed=args.seed,
        embedding_cache=args.embedding_cache,
        skill_loss_weight=args.skill_loss_weight,
        param_loss_weight=args.param_loss_weight,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
