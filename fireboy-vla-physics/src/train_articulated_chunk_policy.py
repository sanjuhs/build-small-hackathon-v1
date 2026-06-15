from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from fireboy_articulated_mjcf import ACTUATED_JOINTS
from generate_articulated_dataset import STAGE_NAMES, TASK_NAMES
from train_articulated_policy import state_from_row


def train_articulated_chunk_policy(
    dataset_dir: Path | list[Path],
    out_dir: Path,
    max_steps: int = 20000,
    task_filter: list[str] | None = None,
    include_stage_flags: bool = True,
    state_mode: str = "clock",
    chunk_steps: int = 16,
    stride: int = 1,
) -> dict[str, Any]:
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("Install torch from fireboy-vla-physics/requirements.txt before training") from exc

    dataset_dirs = dataset_dir if isinstance(dataset_dir, list) else [dataset_dir]
    rows = load_chunk_rows(
        dataset_dirs,
        limit=max_steps * 10,
        task_filter=task_filter,
        include_stage_flags=include_stage_flags,
        state_mode=state_mode,
        chunk_steps=chunk_steps,
        stride=stride,
    )
    if not rows:
        raise RuntimeError(f"No chunk rows found under {dataset_dirs}")

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
    checkpoint = out_dir / "faithful_articulated_chunk_policy.pt"
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
            "chunk_steps": int(chunk_steps),
            "device": str(device),
            "task_names": list(TASK_NAMES),
            "stage_names": list(STAGE_NAMES),
            "task_filter": list(task_filter or []),
            "include_stage_flags": include_stage_flags,
            "state_mode": state_mode,
            "joint_names": list(ACTUATED_JOINTS),
            "policy_kind": "faithful_articulated_action_chunk_v1",
            "state_schema": (
                "faithful_articulated_nav_clock_root_target_sites_taskflags_stageflags_v1"
                if state_mode == "nav_clock"
                else "faithful_articulated_clock_sites_taskflags_stageflags_v1"
                if state_mode == "clock"
                else "faithful_articulated_qpos_qvel_ctrl_prev_sites_taskflags_stageflags_v2"
            ),
            "note": (
                "Predicts a short future sequence of normalized joint targets. This is the "
                "MuJoCo-side analogue of the MiniCPM-V VLA action head."
            ),
        },
        checkpoint,
    )
    return {
        "rows": len(rows),
        "datasets": [str(path) for path in dataset_dirs],
        "checkpoint": str(checkpoint),
        "device": str(device),
        "task_filter": list(task_filter or []),
        "include_stage_flags": include_stage_flags,
        "state_mode": state_mode,
        "input_dim": int(x.shape[1]),
        "output_dim": int(y.shape[1]),
        "action_dim": action_dim,
        "chunk_steps": int(chunk_steps),
        "stride": int(stride),
        "losses": losses[-10:],
    }


def load_chunk_rows(
    dataset_dirs: list[Path],
    limit: int,
    task_filter: list[str] | None,
    include_stage_flags: bool,
    state_mode: str,
    chunk_steps: int,
    stride: int,
) -> list[dict[str, Any]]:
    allowed = set(task_filter or [])
    rows: list[dict[str, Any]] = []
    for dataset_dir in dataset_dirs:
        for path in sorted((dataset_dir / "episodes").glob("*.jsonl")):
            episode = load_episode(path)
            if not episode:
                continue
            for index in range(0, len(episode), max(1, stride)):
                raw = episode[index]
                if allowed and raw.get("task") not in allowed:
                    continue
                chunk = [
                    episode[min(index + offset, len(episode) - 1)]["action"]
                    for offset in range(chunk_steps)
                ]
                rows.append(
                    {
                        "state": state_from_row(
                            raw,
                            include_stage_flags=include_stage_flags,
                            state_mode=state_mode,
                        ),
                        "action_chunk": np.asarray(chunk, dtype=np.float32).reshape(-1).tolist(),
                    }
                )
                if len(rows) >= limit:
                    return rows
    return rows


def load_episode(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=Path("fireboy-vla-physics/build/datasets/fireboy_articulated_all"))
    parser.add_argument("--extra-dataset-dir", type=Path, action="append", default=[])
    parser.add_argument("--out-dir", type=Path, default=Path("fireboy-vla-physics/build/checkpoints/fireboy_articulated_go_eat_berry_chunk"))
    parser.add_argument("--max-steps", type=int, default=20000)
    parser.add_argument("--task-filter", choices=TASK_NAMES, action="append", default=[])
    parser.add_argument("--include-stage-flags", action="store_true", default=True)
    parser.add_argument("--no-stage-flags", action="store_false", dest="include_stage_flags")
    parser.add_argument("--state-mode", choices=["full", "clock", "nav_clock"], default="clock")
    parser.add_argument("--chunk-steps", type=int, default=16)
    parser.add_argument("--stride", type=int, default=1)
    args = parser.parse_args()
    result = train_articulated_chunk_policy(
        [args.dataset_dir, *args.extra_dataset_dir],
        args.out_dir,
        args.max_steps,
        task_filter=args.task_filter or None,
        include_stage_flags=args.include_stage_flags,
        state_mode=args.state_mode,
        chunk_steps=args.chunk_steps,
        stride=args.stride,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
