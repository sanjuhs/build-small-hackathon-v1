from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from fireboy_articulated_mjcf import ACTUATED_JOINTS
from generate_articulated_dataset import STAGE_NAMES, TASK_NAMES
from train_articulated_policy import state_from_row


def train_vla_manifest_action_head(
    manifest: Path,
    out_dir: Path,
    max_steps: int = 12000,
    task_filter: list[str] | None = None,
    include_stage_flags: bool = True,
    state_mode: str = "clock",
    require_existing_images: bool = True,
) -> dict[str, Any]:
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("Install torch from fireboy-vla-physics/requirements.txt before training") from exc

    rows = load_manifest_rows(
        manifest,
        limit=max_steps * 10,
        task_filter=task_filter,
        include_stage_flags=include_stage_flags,
        state_mode=state_mode,
        require_existing_images=require_existing_images,
    )
    if not rows:
        raise RuntimeError(f"No usable VLA manifest rows found in {manifest}")

    x = np.asarray([row["state"] for row in rows], dtype=np.float32)
    y = np.asarray([row["action_chunk"] for row in rows], dtype=np.float32)
    x_mean, x_std = x.mean(axis=0), x.std(axis=0) + 1e-6
    y_mean, y_std = y.mean(axis=0), y.std(axis=0) + 1e-6

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    xt = torch.tensor((x - x_mean) / x_std, device=device)
    yt = torch.tensor((y - y_mean) / y_std, device=device)

    model = nn.Sequential(
        nn.Linear(xt.shape[1], 512),
        nn.SiLU(),
        nn.Linear(512, 512),
        nn.SiLU(),
        nn.Linear(512, yt.shape[1]),
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=2.5e-4, weight_decay=1e-4)
    batch = min(512, len(rows))
    losses: list[float] = []

    action_dim = len(ACTUATED_JOINTS)
    chunk_steps = int(y.shape[1] // action_dim)
    chunk_weights = np.linspace(1.45, 0.75, chunk_steps, dtype=np.float32)
    chunk_weights = np.repeat(chunk_weights, action_dim)
    weight = torch.tensor(chunk_weights, device=device).unsqueeze(0)

    for step in range(max_steps):
        idx = torch.randint(0, xt.shape[0], (batch,), device=device)
        pred = model(xt[idx])
        loss = ((pred - yt[idx]) ** 2 * weight).mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        if step % 100 == 0 or step == max_steps - 1:
            losses.append(float(loss.detach().cpu()))

    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = out_dir / "vla_manifest_action_head.pt"
    torch.save(
        {
            "model": {key: value.detach().cpu() for key, value in model.state_dict().items()},
            "x_mean": x_mean,
            "x_std": x_std,
            "y_mean": y_mean,
            "y_std": y_std,
            "input_dim": int(x.shape[1]),
            "output_dim": int(y.shape[1]),
            "action_dim": action_dim,
            "chunk_steps": chunk_steps,
            "device": str(device),
            "task_names": list(TASK_NAMES),
            "stage_names": list(STAGE_NAMES),
            "task_filter": list(task_filter or []),
            "include_stage_flags": include_stage_flags,
            "state_mode": state_mode,
            "joint_names": list(ACTUATED_JOINTS),
            "policy_kind": "vla_manifest_action_head_v1",
            "vision_backbone": "none_state_language_baseline",
            "uses_image_paths": True,
            "manifest": str(manifest),
            "state_schema": (
                "faithful_articulated_nav_clock_root_target_sites_taskflags_stageflags_v1"
                if state_mode == "nav_clock"
                else "faithful_articulated_clock_sites_taskflags_stageflags_v1"
                if state_mode == "clock"
                else "faithful_articulated_qpos_qvel_ctrl_prev_sites_taskflags_stageflags_v2"
            ),
            "note": (
                "Baseline action head trained from VLA manifest rows. It does not encode pixels yet; "
                "MiniCPM-V should replace the none_state_language_baseline vision path next."
            ),
        },
        checkpoint,
    )
    return {
        "manifest": str(manifest),
        "rows": len(rows),
        "checkpoint": str(checkpoint),
        "device": str(device),
        "task_filter": list(task_filter or []),
        "include_stage_flags": include_stage_flags,
        "state_mode": state_mode,
        "input_dim": int(x.shape[1]),
        "output_dim": int(y.shape[1]),
        "action_dim": action_dim,
        "chunk_steps": chunk_steps,
        "losses": losses[-10:],
    }


def load_manifest_rows(
    manifest: Path,
    limit: int,
    task_filter: list[str] | None,
    include_stage_flags: bool,
    state_mode: str,
    require_existing_images: bool,
) -> list[dict[str, Any]]:
    allowed = set(task_filter or [])
    rows: list[dict[str, Any]] = []
    with manifest.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            if allowed and raw.get("task") not in allowed:
                continue
            image_path = raw.get("image_path")
            if require_existing_images and (not image_path or not Path(image_path).exists()):
                continue
            state_raw = manifest_state_to_training_row(raw)
            action_chunk = np.asarray(raw["action_chunk"], dtype=np.float32).reshape(-1)
            rows.append(
                {
                    "state": state_from_row(
                        state_raw,
                        include_stage_flags=include_stage_flags,
                        state_mode=state_mode,
                    ),
                    "action_chunk": action_chunk.tolist(),
                }
            )
            if len(rows) >= limit:
                break
    return rows


def manifest_state_to_training_row(raw: dict[str, Any]) -> dict[str, Any]:
    robot_state = dict(raw.get("robot_state") or {})
    robot_state["task"] = raw.get("task", "pick_up")
    robot_state["stage"] = raw.get("stage", "approach")
    robot_state["step"] = raw.get("step", 0)
    robot_state["grasped"] = raw.get("grasped", False)
    robot_state["eaten"] = raw.get("eaten", False)
    return robot_state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=12000)
    parser.add_argument("--task-filter", choices=TASK_NAMES, action="append", default=[])
    parser.add_argument("--include-stage-flags", action="store_true", default=True)
    parser.add_argument("--no-stage-flags", action="store_false", dest="include_stage_flags")
    parser.add_argument("--state-mode", choices=["full", "clock", "nav_clock"], default="clock")
    parser.add_argument("--allow-missing-images", action="store_true")
    args = parser.parse_args()
    result = train_vla_manifest_action_head(
        args.manifest,
        args.out_dir,
        max_steps=args.max_steps,
        task_filter=args.task_filter or None,
        include_stage_flags=args.include_stage_flags,
        state_mode=args.state_mode,
        require_existing_images=not args.allow_missing_images,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
