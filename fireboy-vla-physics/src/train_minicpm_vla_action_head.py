from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from fireboy_articulated_mjcf import ACTUATED_JOINTS
from generate_articulated_dataset import STAGE_NAMES, TASK_NAMES
from train_vla_manifest_action_head import manifest_state_to_training_row
from train_articulated_policy import state_from_row


MODEL_ID = "openbmb/MiniCPM-V-4.6"
ROOT_X_ACTION_INDEX = int(ACTUATED_JOINTS.index("root_x"))
ROOT_Y_ACTION_INDEX = int(ACTUATED_JOINTS.index("root_y"))
ROOT_YAW_ACTION_INDEX = int(ACTUATED_JOINTS.index("root_yaw"))
ROOT_HALF_RANGE_X_M = 2.4
ROOT_HALF_RANGE_Y_M = 2.0
ROOT_YAW_HALF_RANGE_RAD = float(np.pi)


@dataclass
class ManifestSample:
    image_path: Path
    instruction: str
    task: str
    stage: str
    step: int
    state: list[float]
    action_chunk: list[float]


class MiniCPMStateActionHead:
    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        hidden_dim: int = 512,
        architecture: str = "single_tower_v1",
        vl_dim: int | None = None,
        state_dim: int | None = None,
        vl_residual_scale: float = 0.15,
    ):
        import torch
        from torch import nn

        class StateResidualFusion(nn.Module):
            def __init__(
                self,
                vl_dim: int,
                state_dim: int,
                output_dim: int,
                hidden_dim: int,
                vl_residual_scale: float,
            ):
                super().__init__()
                self.vl_dim = vl_dim
                self.state_dim = state_dim
                self.vl_residual_scale = float(vl_residual_scale)
                self.state_head = nn.Sequential(
                    nn.Linear(state_dim, hidden_dim),
                    nn.SiLU(),
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.SiLU(),
                    nn.Linear(hidden_dim, output_dim),
                )
                self.vl_head = nn.Sequential(
                    nn.Linear(vl_dim, 256),
                    nn.SiLU(),
                    nn.Linear(256, 256),
                    nn.SiLU(),
                )
                self.residual_head = nn.Sequential(
                    nn.Linear(256 + state_dim, hidden_dim),
                    nn.SiLU(),
                    nn.Linear(hidden_dim, output_dim),
                )

            def forward(self, x: Any) -> Any:
                vl = x[:, : self.vl_dim]
                state = x[:, self.vl_dim : self.vl_dim + self.state_dim]
                state_action = self.state_head(state)
                vl_context = self.vl_head(vl)
                residual = self.residual_head(torch.cat([vl_context, state], dim=-1))
                return state_action + self.vl_residual_scale * residual

        self.torch = torch
        self.architecture = architecture
        if architecture == "state_residual_fusion_v1":
            if vl_dim is None or state_dim is None:
                raise ValueError("state_residual_fusion_v1 requires vl_dim and state_dim")
            self.model = StateResidualFusion(
                vl_dim=int(vl_dim),
                state_dim=int(state_dim),
                output_dim=output_dim,
                hidden_dim=hidden_dim,
                vl_residual_scale=vl_residual_scale,
            )
        elif architecture == "single_tower_v1":
            self.model = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.SiLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.SiLU(),
                nn.Linear(hidden_dim, output_dim),
            )
        else:
            raise ValueError(f"Unknown MiniCPM action head architecture: {architecture}")

    def to(self, device: Any) -> "MiniCPMStateActionHead":
        self.model.to(device)
        return self

    def parameters(self):
        return self.model.parameters()

    def __call__(self, x: Any) -> Any:
        return self.model(x)

    def state_dict(self) -> dict[str, Any]:
        return self.model.state_dict()

    def load_state_dict(self, state_dict: dict[str, Any]) -> None:
        self.model.load_state_dict(state_dict)

    def eval(self) -> None:
        self.model.eval()


def train_minicpm_vla_action_head(
    manifests: list[Path],
    out_dir: Path,
    model_id: str = MODEL_ID,
    max_steps: int = 1200,
    limit_rows: int = 256,
    task_filter: list[str] | None = None,
    state_mode: str = "clock",
    include_stage_flags: bool = True,
    downsample_mode: str = "16x",
    max_slice_nums: int = 9,
    val_fraction: float = 0.12,
    seed: int = 7,
    embedding_cache: Path | None = None,
    head_architecture: str = "state_residual_fusion_v1",
    vl_residual_scale: float = 0.15,
    action_std_floor: float = 0.01,
    action_target_mode: str = "absolute_joint_targets",
    root_velocity_max_step_m: float = 0.035,
) -> dict[str, Any]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install torch before training MiniCPM-V action head") from exc

    samples = load_manifest_samples(
        manifests,
        limit_rows=limit_rows,
        task_filter=task_filter,
        state_mode=state_mode,
        include_stage_flags=include_stage_flags,
        action_target_mode=action_target_mode,
        root_velocity_max_step_m=root_velocity_max_step_m,
    )
    if not samples:
        raise RuntimeError(f"No usable samples in manifests: {manifests}")

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
        cache_key = make_cache_key(sample, model_id, downsample_mode, max_slice_nums)
        if cache_key in cache:
            embedding = cache[cache_key]
            cache_hits += 1
        else:
            embedding = encode_minicpm_prompt(
                processor,
                minicpm,
                sample.image_path,
                sample.instruction,
                downsample_mode=downsample_mode,
                max_slice_nums=max_slice_nums,
            )
            cache[cache_key] = embedding
        embeddings.append(embedding)
        if (index + 1) % 25 == 0:
            print(json.dumps({"encoded": index + 1, "total": len(samples), "cache_hits": cache_hits}), flush=True)
    save_embedding_cache(embedding_cache, cache)

    vl = np.asarray(embeddings, dtype=np.float32)
    states = np.asarray([sample.state for sample in samples], dtype=np.float32)
    actions = np.asarray([sample.action_chunk for sample in samples], dtype=np.float32)

    state_mean, state_std = states.mean(axis=0), states.std(axis=0) + 1e-6
    vl_mean, vl_std = vl.mean(axis=0), vl.std(axis=0) + 1e-6
    action_mean = actions.mean(axis=0)
    action_std = np.maximum(actions.std(axis=0), float(action_std_floor)) + 1e-6

    features = np.concatenate([(vl - vl_mean) / vl_std, (states - state_mean) / state_std], axis=1)
    targets = (actions - action_mean) / action_std
    train_mask = np.asarray([index not in val_indices for index in range(len(samples))], dtype=bool)
    if not train_mask.any():
        train_mask[:] = True

    xt = torch.tensor(features[train_mask], dtype=torch.float32, device=device)
    yt = torch.tensor(targets[train_mask], dtype=torch.float32, device=device)
    xv = torch.tensor(features[~train_mask], dtype=torch.float32, device=device) if (~train_mask).any() else xt[:1]
    yv = torch.tensor(targets[~train_mask], dtype=torch.float32, device=device) if (~train_mask).any() else yt[:1]

    head = MiniCPMStateActionHead(
        xt.shape[1],
        yt.shape[1],
        architecture=head_architecture,
        vl_dim=vl.shape[1],
        state_dim=states.shape[1],
        vl_residual_scale=vl_residual_scale,
    ).to(device)
    opt = torch.optim.AdamW(head.parameters(), lr=2.5e-4, weight_decay=1e-4)
    batch = min(128, xt.shape[0])
    losses: list[float] = []
    val_losses: list[float] = []
    action_dim = len(ACTUATED_JOINTS)
    chunk_steps = int(actions.shape[1] // action_dim)
    chunk_weights = np.linspace(1.45, 0.75, chunk_steps, dtype=np.float32)
    chunk_weights = np.repeat(chunk_weights, action_dim)
    weight = torch.tensor(chunk_weights, device=device).unsqueeze(0)
    for step in range(max_steps):
        idx = torch.randint(0, xt.shape[0], (batch,), device=device)
        pred = head(xt[idx])
        loss = ((pred - yt[idx]) ** 2 * weight).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        if step % 50 == 0 or step == max_steps - 1:
            with torch.no_grad():
                val_loss = ((head(xv) - yv) ** 2 * weight).mean()
            losses.append(float(loss.detach().cpu()))
            val_losses.append(float(val_loss.detach().cpu()))

    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = out_dir / "minicpm_vla_action_head.pt"
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
            "action_mean": action_mean,
            "action_std": action_std,
            "state_dim": int(states.shape[1]),
            "vl_dim": int(vl.shape[1]),
            "input_dim": int(features.shape[1]),
            "output_dim": int(actions.shape[1]),
            "action_dim": action_dim,
            "chunk_steps": chunk_steps,
            "head_architecture": head_architecture,
            "vl_residual_scale": float(vl_residual_scale),
            "action_std_floor": float(action_std_floor),
            "action_target_mode": action_target_mode,
            "root_velocity_max_step_m": float(root_velocity_max_step_m),
            "task_names": list(TASK_NAMES),
            "stage_names": list(STAGE_NAMES),
            "task_filter": list(task_filter or []),
            "state_mode": state_mode,
            "include_stage_flags": include_stage_flags,
            "joint_names": list(ACTUATED_JOINTS),
            "policy_kind": "minicpm_vla_frozen_encoder_action_head_v2",
            "lora_rank": 0,
            "manifests": [str(path) for path in manifests],
            "note": (
                "MiniCPM-V 4.6 is frozen here. This trains the robot-state/action head over "
                "MiniCPM image+language embeddings; LoRA is the next stage once this rollout gate passes."
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
        "task_filter": list(task_filter or []),
        "vl_dim": int(vl.shape[1]),
        "state_dim": int(states.shape[1]),
        "output_dim": int(actions.shape[1]),
        "chunk_steps": chunk_steps,
        "head_architecture": head_architecture,
        "vl_residual_scale": float(vl_residual_scale),
        "action_std_floor": float(action_std_floor),
        "action_target_mode": action_target_mode,
        "root_velocity_max_step_m": float(root_velocity_max_step_m),
        "cache_hits": cache_hits,
        "losses": losses[-10:],
        "val_losses": val_losses[-10:],
    }


def build_minicpm_action_head(payload: dict[str, Any]) -> MiniCPMStateActionHead:
    return MiniCPMStateActionHead(
        int(payload["input_dim"]),
        int(payload["output_dim"]),
        architecture=str(payload.get("head_architecture", "single_tower_v1")),
        vl_dim=int(payload.get("vl_dim", 0)) or None,
        state_dim=int(payload.get("state_dim", 0)) or None,
        vl_residual_scale=float(payload.get("vl_residual_scale", 0.15)),
    )


def load_manifest_samples(
    manifests: list[Path],
    limit_rows: int,
    task_filter: list[str] | None,
    state_mode: str,
    include_stage_flags: bool,
    action_target_mode: str = "absolute_joint_targets",
    root_velocity_max_step_m: float = 0.035,
) -> list[ManifestSample]:
    allowed = set(task_filter or [])
    samples: list[ManifestSample] = []
    for manifest in manifests:
        with manifest.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw = json.loads(line)
                if allowed and raw.get("task") not in allowed:
                    continue
                image_path = Path(str(raw.get("image_path", "")))
                if not image_path.exists():
                    continue
                state_raw = manifest_state_to_training_row(raw)
                state = state_from_row(state_raw, include_stage_flags=include_stage_flags, state_mode=state_mode)
                action_chunk = np.asarray(raw["action_chunk"], dtype=np.float32)
                action = transform_action_chunk(
                    raw,
                    action_chunk,
                    action_target_mode=action_target_mode,
                    root_velocity_max_step_m=root_velocity_max_step_m,
                ).reshape(-1).tolist()
                samples.append(
                    ManifestSample(
                        image_path=image_path,
                        instruction=str(raw.get("instruction") or raw.get("task") or "do the task"),
                        task=str(raw.get("task", "unknown")),
                        stage=str(raw.get("stage", "unknown")),
                        step=int(raw.get("step", 0)),
                        state=state,
                        action_chunk=action,
                    )
                )
                if len(samples) >= limit_rows:
                    return samples
    return samples


def transform_action_chunk(
    raw: dict[str, Any],
    action_chunk: np.ndarray,
    action_target_mode: str,
    root_velocity_max_step_m: float,
) -> np.ndarray:
    chunk = np.asarray(action_chunk, dtype=np.float32).reshape(-1, len(ACTUATED_JOINTS)).copy()
    if action_target_mode == "absolute_joint_targets":
        return chunk
    if action_target_mode != "root_velocity_v1":
        raise ValueError(f"Unknown action target mode: {action_target_mode}")

    robot_state = raw.get("robot_state") or {}
    previous_action = np.asarray(
        robot_state.get("previous_action", [0.0] * len(ACTUATED_JOINTS)),
        dtype=np.float32,
    )
    if previous_action.size < len(ACTUATED_JOINTS):
        previous_action = np.pad(previous_action, (0, len(ACTUATED_JOINTS) - previous_action.size))

    qpos = list(robot_state.get("qpos", []))
    target = list(robot_state.get("ball_pos", [0.0, 0.0, 0.0]))
    target_x = float(target[0]) if len(target) > 0 else 0.0
    target_y = float(target[1]) if len(target) > 1 else 0.0
    source_action = previous_action.copy()
    max_step = max(float(root_velocity_max_step_m), 1e-6)

    for index in range(chunk.shape[0]):
        if index == 0 and len(qpos) > 8:
            root_x = float(qpos[7])
            root_y = float(qpos[8])
        else:
            root_x = float(source_action[ROOT_X_ACTION_INDEX]) * ROOT_HALF_RANGE_X_M
            root_y = float(source_action[ROOT_Y_ACTION_INDEX]) * ROOT_HALF_RANGE_Y_M
        dx = target_x - root_x
        dy = target_y - root_y
        heading = float(np.arctan2(dy, dx)) if np.hypot(dx, dy) > 1e-6 else 0.0
        transformed = chunk[index].copy()
        transformed[ROOT_X_ACTION_INDEX] = float(np.clip(dx / max_step, -1.0, 1.0))
        transformed[ROOT_Y_ACTION_INDEX] = float(np.clip(dy / max_step, -1.0, 1.0))
        transformed[ROOT_YAW_ACTION_INDEX] = float(np.clip(heading / ROOT_YAW_HALF_RANGE_RAD, -1.0, 1.0))
        chunk[index] = transformed
        source_action = np.asarray(action_chunk[index], dtype=np.float32).copy()
    return chunk


def load_minicpm(model_id: str) -> tuple[Any, Any]:
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None,
        trust_remote_code=True,
    )
    if not torch.cuda.is_available():
        model.to("cpu")
    return processor, model


def encode_minicpm_prompt(
    processor: Any,
    model: Any,
    image_path: Path,
    instruction: str,
    downsample_mode: str = "16x",
    max_slice_nums: int = 9,
) -> np.ndarray:
    import torch

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "url": str(image_path)},
                {"type": "text", "text": make_vla_prompt(instruction)},
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
        raise RuntimeError("MiniCPM forward did not return hidden_states; cannot train action head from embeddings.")
    last_hidden = hidden_states[-1].float()
    attention = inputs.get("attention_mask")
    if attention is not None:
        mask = attention.to(last_hidden.device).unsqueeze(-1).float()
        pooled = (last_hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
    else:
        pooled = last_hidden.mean(dim=1)
    return pooled.squeeze(0).detach().cpu().numpy().astype(np.float32)


def apply_minicpm_chat_template(
    processor: Any,
    messages: list[dict[str, Any]],
    downsample_mode: str,
    max_slice_nums: int,
) -> Any:
    base_kwargs = {
        "tokenize": True,
        "add_generation_prompt": True,
        "return_dict": True,
        "return_tensors": "pt",
    }
    try:
        return processor.apply_chat_template(
            messages,
            **base_kwargs,
            processor_kwargs={
                "downsample_mode": downsample_mode,
                "max_slice_nums": max_slice_nums,
            },
        )
    except TypeError:
        return processor.apply_chat_template(
            messages,
            **base_kwargs,
            downsample_mode=downsample_mode,
            max_slice_nums=max_slice_nums,
        )


def make_vla_prompt(instruction: str) -> str:
    return (
        "You are controlling Fire Boy in a toy-room MuJoCo simulation. "
        f"Command: {instruction}. "
        "Represent the scene so a robot action head can predict the next short chunk of joint targets."
    )


def first_model_device(model: Any) -> Any:
    for parameter in model.parameters():
        return parameter.device
    raise RuntimeError("Model has no parameters")


def make_cache_key(sample: ManifestSample, model_id: str, downsample_mode: str, max_slice_nums: int) -> str:
    return "|".join(
        [
            model_id,
            downsample_mode,
            str(max_slice_nums),
            str(sample.image_path),
            sample.instruction,
        ]
    )


def load_embedding_cache(path: Path | None) -> dict[str, np.ndarray]:
    if path is None or not path.exists():
        return {}
    raw = np.load(path, allow_pickle=False)
    return {key: raw[key].astype(np.float32) for key in raw.files}


def save_embedding_cache(path: Path | None, cache: dict[str, np.ndarray]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **cache)


def parse_path_list(values: list[Path] | None) -> list[Path]:
    return [Path(value) for value in values or []]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--max-steps", type=int, default=1200)
    parser.add_argument("--limit-rows", type=int, default=256)
    parser.add_argument("--task-filter", choices=TASK_NAMES, action="append", default=[])
    parser.add_argument("--state-mode", choices=["full", "clock", "nav_clock"], default="clock")
    parser.add_argument("--include-stage-flags", action="store_true", default=True)
    parser.add_argument("--no-stage-flags", action="store_false", dest="include_stage_flags")
    parser.add_argument("--downsample-mode", default="16x")
    parser.add_argument("--max-slice-nums", type=int, default=9)
    parser.add_argument("--val-fraction", type=float, default=0.12)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--embedding-cache", type=Path)
    parser.add_argument("--head-architecture", choices=["single_tower_v1", "state_residual_fusion_v1"], default="state_residual_fusion_v1")
    parser.add_argument("--vl-residual-scale", type=float, default=0.15)
    parser.add_argument("--action-std-floor", type=float, default=0.01)
    parser.add_argument("--action-target-mode", choices=["absolute_joint_targets", "root_velocity_v1"], default="absolute_joint_targets")
    parser.add_argument("--root-velocity-max-step-m", type=float, default=0.035)
    args = parser.parse_args()
    result = train_minicpm_vla_action_head(
        parse_path_list(args.manifest),
        args.out_dir,
        model_id=args.model_id,
        max_steps=args.max_steps,
        limit_rows=args.limit_rows,
        task_filter=args.task_filter or None,
        state_mode=args.state_mode,
        include_stage_flags=args.include_stage_flags,
        downsample_mode=args.downsample_mode,
        max_slice_nums=args.max_slice_nums,
        val_fraction=args.val_fraction,
        seed=args.seed,
        embedding_cache=args.embedding_cache,
        head_architecture=args.head_architecture,
        vl_residual_scale=args.vl_residual_scale,
        action_std_floor=args.action_std_floor,
        action_target_mode=args.action_target_mode,
        root_velocity_max_step_m=args.root_velocity_max_step_m,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
