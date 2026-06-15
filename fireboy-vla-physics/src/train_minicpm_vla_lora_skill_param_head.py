from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from build_vla_skill_param_manifest import PARAM_NAMES, SKILL_NAMES
from train_minicpm_vla_action_head import apply_minicpm_chat_template
from train_minicpm_vla_lora_action_head import find_lora_targets
from train_minicpm_vla_skill_param_head import (
    MODEL_ID,
    MiniCPMSkillParamHead,
    evaluate_head_arrays,
    load_skill_param_samples,
)


def train_minicpm_vla_lora_skill_param_head(
    manifest: Path,
    seed_checkpoint: Path,
    out_dir: Path,
    *,
    model_id: str = MODEL_ID,
    limit_rows: int = 512,
    max_steps: int = 350,
    lora_rank: int = 8,
    lora_alpha: int = 16,
    lora_dropout: float = 0.05,
    lr_lora: float = 1.0e-5,
    lr_head: float = 4.0e-5,
    skill_loss_weight: float = 1.0,
    param_loss_weight: float = 0.35,
    downsample_mode: str | None = None,
    max_slice_nums: int | None = None,
    val_fraction: float = 0.16,
    seed: int = 37,
) -> dict[str, Any]:
    try:
        import torch
        from torch.nn import functional as F
    except ImportError as exc:
        raise RuntimeError("Install torch before training the MiniCPM-V LoRA skill-param router") from exc

    payload = torch.load(seed_checkpoint, map_location="cpu")
    downsample_mode = downsample_mode or str(payload.get("downsample_mode", "16x"))
    max_slice_nums = int(max_slice_nums or payload.get("max_slice_nums", 9))

    samples = load_skill_param_samples(
        [manifest],
        limit_rows=limit_rows,
        state_mode=str(payload.get("state_mode", "nav_clock")),
        include_stage_flags=bool(payload.get("include_stage_flags", True)),
    )
    if not samples:
        raise RuntimeError(f"No usable skill-param samples found in {manifest}")

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(samples))
    val_count = max(1, int(round(len(samples) * val_fraction))) if len(samples) > 8 else 1
    val_indices = set(int(index) for index in order[:val_count])
    train_indices = [index for index in range(len(samples)) if index not in val_indices]
    val_list = [index for index in range(len(samples)) if index in val_indices]
    if not train_indices:
        train_indices = list(range(len(samples)))
        val_list = train_indices[:1]

    states = np.asarray([sample.state for sample in samples], dtype=np.float32)
    params = np.asarray([sample.target_params for sample in samples], dtype=np.float32)
    skill_ids = np.asarray([sample.skill_id for sample in samples], dtype=np.int64)

    state_mean = np.asarray(payload["state_mean"], dtype=np.float32)
    state_std = np.asarray(payload["state_std"], dtype=np.float32)
    vl_mean = np.asarray(payload["vl_mean"], dtype=np.float32)
    vl_std = np.asarray(payload["vl_std"], dtype=np.float32)
    param_mean = np.asarray(payload["param_mean"], dtype=np.float32)
    param_std = np.asarray(payload["param_std"], dtype=np.float32)

    states_norm = (states - state_mean) / state_std
    param_targets = (params - param_mean) / param_std

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    processor, minicpm = load_minicpm_for_lora(model_id, lora_rank, lora_alpha, lora_dropout, device)
    head = MiniCPMSkillParamHead(
        input_dim=int(payload["input_dim"]),
        skill_count=int(payload["skill_count"]),
        param_dim=int(payload["param_dim"]),
    ).to(device)
    head.load_state_dict(payload["head"])

    lora_params = [param for param in minicpm.parameters() if param.requires_grad]
    head_params = [param for param in head.parameters() if param.requires_grad]
    if not lora_params:
        raise RuntimeError("No trainable LoRA parameters were found.")
    opt = torch.optim.AdamW(
        [
            {"params": lora_params, "lr": lr_lora},
            {"params": head_params, "lr": lr_head},
        ],
        weight_decay=1.0e-4,
    )

    vl_mean_t = torch.tensor(vl_mean, dtype=torch.float32, device=device).unsqueeze(0)
    vl_std_t = torch.tensor(vl_std, dtype=torch.float32, device=device).unsqueeze(0)
    state_norm_t = torch.tensor(states_norm, dtype=torch.float32, device=device)
    param_target_t = torch.tensor(param_targets, dtype=torch.float32, device=device)
    skill_id_t = torch.tensor(skill_ids, dtype=torch.long, device=device)

    history: list[dict[str, float]] = []
    py_rng = np.random.default_rng(seed + 1)
    for step in range(max_steps):
        sample_index = int(py_rng.choice(train_indices))
        minicpm.train()
        head.model.train()
        skill_logits, param_pred = forward_sample(
            processor,
            minicpm,
            head,
            samples[sample_index],
            state_norm_t[sample_index],
            vl_mean_t,
            vl_std_t,
            device,
            downsample_mode,
            max_slice_nums,
        )
        skill_loss = F.cross_entropy(skill_logits, skill_id_t[sample_index].view(1))
        param_loss = F.mse_loss(param_pred, param_target_t[sample_index].view(1, -1))
        loss = skill_loss_weight * skill_loss + param_loss_weight * param_loss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()

        if step % 25 == 0 or step == max_steps - 1:
            minicpm.eval()
            head.model.eval()
            with torch.no_grad():
                val_metrics = eval_lora_subset(
                    processor,
                    minicpm,
                    head,
                    samples,
                    state_norm_t,
                    skill_id_t,
                    param_target_t,
                    param_mean,
                    param_std,
                    sorted(val_list)[: min(24, len(val_list))],
                    vl_mean_t,
                    vl_std_t,
                    device,
                    downsample_mode,
                    max_slice_nums,
                )
            record = {
                "step": float(step),
                "loss": float(loss.detach().cpu()),
                "skill_loss": float(skill_loss.detach().cpu()),
                "param_loss": float(param_loss.detach().cpu()),
                "val_skill_accuracy": float(val_metrics["skill_accuracy"]),
                "val_param_mae": float(val_metrics["param_mae"]),
            }
            history.append(record)
            print(json.dumps(record), file=sys.stderr, flush=True)

    minicpm.eval()
    head.model.eval()
    with torch.no_grad():
        final_val_metrics = eval_lora_subset(
            processor,
            minicpm,
            head,
            samples,
            state_norm_t,
            skill_id_t,
            param_target_t,
            param_mean,
            param_std,
            sorted(val_list),
            vl_mean_t,
            vl_std_t,
            device,
            downsample_mode,
            max_slice_nums,
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir = out_dir / "lora_adapter"
    minicpm.save_pretrained(adapter_dir)
    checkpoint = out_dir / "minicpm_vla_lora_skill_param_head.pt"
    save_payload = dict(payload)
    save_payload.update(
        {
            "head": {key: value.detach().cpu() for key, value in head.state_dict().items()},
            "model_id": model_id,
            "policy_kind": "minicpm_vla_lora_skill_param_head_v1",
            "lora_rank": int(lora_rank),
            "lora_alpha": int(lora_alpha),
            "lora_dropout": float(lora_dropout),
            "lora_adapter_dir": "lora_adapter",
            "seed_checkpoint": str(seed_checkpoint),
            "train_rows": len(train_indices),
            "val_rows": len(val_list),
            "rows": len(samples),
            "downsample_mode": downsample_mode,
            "max_slice_nums": int(max_slice_nums),
            "history": history[-12:],
            "val_metrics": final_val_metrics,
            "note": (
                "MiniCPM-V 4.6 LoRA adapters plus skill/parameter router head. "
                "This keeps the proven router target: image + command + robot state "
                "maps to a pet skill and continuous parameters for MuJoCo dispatch."
            ),
        }
    )
    torch.save(save_payload, checkpoint)
    return {
        "checkpoint": str(checkpoint),
        "adapter_dir": str(adapter_dir),
        "seed_checkpoint": str(seed_checkpoint),
        "model_id": model_id,
        "rows": len(samples),
        "train_rows": len(train_indices),
        "val_rows": len(val_list),
        "device": str(device),
        "lora_rank": int(lora_rank),
        "lora_alpha": int(lora_alpha),
        "downsample_mode": downsample_mode,
        "max_slice_nums": int(max_slice_nums),
        "history": history[-12:],
        "val_metrics": final_val_metrics,
    }


def load_minicpm_for_lora(
    model_id: str,
    lora_rank: int,
    lora_alpha: int,
    lora_dropout: float,
    device: Any,
) -> tuple[Any, Any]:
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForImageTextToText, AutoProcessor

    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )
    model.to(device)
    if hasattr(model, "config"):
        model.config.use_cache = False
    if hasattr(model, "gradient_checkpointing_enable"):
        try:
            model.gradient_checkpointing_enable()
        except Exception:
            pass
    targets = find_lora_targets(model)
    config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
        target_modules=targets,
    )
    model = get_peft_model(model, config)
    model.train()
    return processor, model


def forward_sample(
    processor: Any,
    minicpm: Any,
    head: MiniCPMSkillParamHead,
    sample: Any,
    state_norm: Any,
    vl_mean: Any,
    vl_std: Any,
    device: Any,
    downsample_mode: str,
    max_slice_nums: int,
) -> tuple[Any, Any]:
    import torch

    vl = encode_skill_param_prompt_tensor(
        processor,
        minicpm,
        sample.image_path,
        sample.instruction,
        device,
        downsample_mode,
        max_slice_nums,
    )
    vl = (vl - vl_mean) / vl_std
    state = state_norm.view(1, -1)
    return head.model(torch.cat([vl, state], dim=-1))


def eval_lora_subset(
    processor: Any,
    minicpm: Any,
    head: MiniCPMSkillParamHead,
    samples: list[Any],
    state_norm: Any,
    skill_ids: Any,
    param_targets: Any,
    param_mean: np.ndarray,
    param_std: np.ndarray,
    indices: list[int],
    vl_mean: Any,
    vl_std: Any,
    device: Any,
    downsample_mode: str,
    max_slice_nums: int,
) -> dict[str, Any]:
    if not indices:
        return {"skill_accuracy": 0.0, "param_mae": 0.0, "param_mae_by_name": {}, "confusion": [], "skill_names": list(SKILL_NAMES)}
    feature_rows = []
    for sample_index in indices:
        vl = encode_skill_param_prompt_tensor(
            processor,
            minicpm,
            samples[sample_index].image_path,
            samples[sample_index].instruction,
            device,
            downsample_mode,
            max_slice_nums,
        )
        feature_rows.append(torch_cat_feature(vl, state_norm[sample_index], vl_mean, vl_std))
    import torch

    features = torch.cat(feature_rows, dim=0)
    return evaluate_head_arrays(
        head,
        features,
        skill_ids[indices],
        param_targets[indices],
        param_mean,
        param_std,
        device=device,
    )


def torch_cat_feature(vl: Any, state_norm: Any, vl_mean: Any, vl_std: Any) -> Any:
    import torch

    return torch.cat([(vl - vl_mean) / vl_std, state_norm.view(1, -1)], dim=-1)


def encode_skill_param_prompt_tensor(
    processor: Any,
    model: Any,
    image_path: Path,
    instruction: str,
    device: Any,
    downsample_mode: str,
    max_slice_nums: int,
) -> Any:
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

    inputs = inputs.to(device)
    outputs = model(**inputs, output_hidden_states=True, return_dict=True)
    hidden_states = getattr(outputs, "hidden_states", None)
    if not hidden_states:
        raise RuntimeError("MiniCPM forward did not return hidden states.")
    last_hidden = hidden_states[-1].float()
    attention = inputs.get("attention_mask")
    if attention is not None:
        mask = attention.to(last_hidden.device).unsqueeze(-1).float()
        return (last_hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
    return last_hidden.mean(dim=1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed-checkpoint", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--limit-rows", type=int, default=512)
    parser.add_argument("--max-steps", type=int, default=350)
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--lr-lora", type=float, default=1.0e-5)
    parser.add_argument("--lr-head", type=float, default=4.0e-5)
    parser.add_argument("--skill-loss-weight", type=float, default=1.0)
    parser.add_argument("--param-loss-weight", type=float, default=0.35)
    parser.add_argument("--downsample-mode")
    parser.add_argument("--max-slice-nums", type=int)
    parser.add_argument("--val-fraction", type=float, default=0.16)
    parser.add_argument("--seed", type=int, default=37)
    args = parser.parse_args()
    result = train_minicpm_vla_lora_skill_param_head(
        manifest=args.manifest,
        seed_checkpoint=args.seed_checkpoint,
        out_dir=args.out_dir,
        model_id=args.model_id,
        limit_rows=args.limit_rows,
        max_steps=args.max_steps,
        lora_rank=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        lr_lora=args.lr_lora,
        lr_head=args.lr_head,
        skill_loss_weight=args.skill_loss_weight,
        param_loss_weight=args.param_loss_weight,
        downsample_mode=args.downsample_mode,
        max_slice_nums=args.max_slice_nums,
        val_fraction=args.val_fraction,
        seed=args.seed,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
