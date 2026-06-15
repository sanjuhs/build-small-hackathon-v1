from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from fireboy_articulated_mjcf import ACTUATED_JOINTS
from generate_articulated_dataset import STAGE_NAMES, TASK_NAMES, stage_one_hot, task_one_hot


def train_articulated_policy(
    dataset_dir: Path | list[Path],
    out_dir: Path,
    max_steps: int = 1000,
    task_filter: list[str] | None = None,
    include_stage_flags: bool = False,
    state_mode: str = "full",
) -> dict:
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("Install torch from fireboy-vla-physics/requirements.txt before training") from exc

    dataset_dirs = dataset_dir if isinstance(dataset_dir, list) else [dataset_dir]
    rows = load_rows(
        dataset_dirs,
        limit=max_steps * 8,
        task_filter=task_filter,
        include_stage_flags=include_stage_flags,
        state_mode=state_mode,
    )
    if not rows:
        raise RuntimeError(f"No rows found under {dataset_dirs}")

    x = np.asarray([row["state"] for row in rows], dtype=np.float32)
    y = np.asarray([row["action"] for row in rows], dtype=np.float32)
    x_mean, x_std = x.mean(axis=0), x.std(axis=0) + 1e-6
    y_mean, y_std = y.mean(axis=0), y.std(axis=0) + 1e-6
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    xt = torch.tensor((x - x_mean) / x_std, device=device)
    yt = torch.tensor((y - y_mean) / y_std, device=device)

    model = nn.Sequential(
        nn.Linear(xt.shape[1], 384),
        nn.ReLU(),
        nn.Linear(384, 384),
        nn.ReLU(),
        nn.Linear(384, yt.shape[1]),
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4)
    batch = min(384, len(rows))
    losses = []
    for step in range(max_steps):
        idx = torch.randint(0, xt.shape[0], (batch,), device=device)
        pred = model(xt[idx])
        loss = torch.nn.functional.mse_loss(pred, yt[idx])
        opt.zero_grad()
        loss.backward()
        opt.step()
        if step % 50 == 0 or step == max_steps - 1:
            losses.append(float(loss.detach().cpu()))

    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = out_dir / "faithful_articulated_policy.pt"
    torch.save(
        {
            "model": {key: value.detach().cpu() for key, value in model.state_dict().items()},
            "x_mean": x_mean,
            "x_std": x_std,
            "y_mean": y_mean,
            "y_std": y_std,
            "input_dim": int(x.shape[1]),
            "action_dim": int(y.shape[1]),
            "device": str(device),
            "task_names": list(TASK_NAMES),
            "stage_names": list(STAGE_NAMES),
            "task_filter": list(task_filter or []),
            "include_stage_flags": include_stage_flags,
            "state_mode": state_mode,
            "joint_names": list(ACTUATED_JOINTS),
            "state_schema": (
                "faithful_articulated_nav_clock_root_target_sites_taskflags_stageflags_v1"
                if state_mode == "nav_clock"
                else "faithful_articulated_clock_sites_taskflags_stageflags_v1"
                if state_mode == "clock"
                else
                "faithful_articulated_qpos_qvel_ctrl_prev_sites_taskflags_stageflags_v2"
                if include_stage_flags
                else "faithful_articulated_qpos_qvel_ctrl_prev_sites_taskflags_v1"
            ),
            "note": (
                "Command-conditioned state policy for the faithful Fireboy-shaped MuJoCo body. "
                "This is the retraining lane for serious policies; do not use the old two-hand harness for new results."
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
        "action_dim": int(y.shape[1]),
        "losses": losses[-10:],
    }


def load_rows(
    dataset_dirs: list[Path],
    limit: int,
    task_filter: list[str] | None = None,
    include_stage_flags: bool = False,
    state_mode: str = "full",
) -> list[dict]:
    allowed = set(task_filter or [])
    rows = []
    for dataset_dir in dataset_dirs:
        for path in sorted((dataset_dir / "episodes").glob("*.jsonl")):
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    raw = json.loads(line)
                    if allowed and raw.get("task") not in allowed:
                        continue
                    rows.append({
                        "state": state_from_row(
                            raw,
                            include_stage_flags=include_stage_flags,
                            state_mode=state_mode,
                        ),
                        "action": raw["action"],
                    })
                    if len(rows) >= limit:
                        return rows
    return rows


def state_from_row(raw: dict, include_stage_flags: bool = False, state_mode: str = "full") -> list[float]:
    task_flags = raw.get("task_flags")
    if task_flags is None:
        task_flags = task_one_hot(str(raw.get("task", "pick_up")))
    if state_mode in {"clock", "nav_clock"}:
        nav_state = navigation_features_from_row(raw) if state_mode == "nav_clock" else []
        state = (
            nav_state
            + list(raw.get("right_hand_pos", [0.0, 0.0, 0.0]))
            + list(raw.get("left_hand_pos", [0.0, 0.0, 0.0]))
            + list(raw.get("ball_pos", [0.0, 0.0, 0.0]))
            + list(raw.get("mouth_pos", [0.0, 0.0, 0.0]))
            + list(task_flags)
        )
        if state_mode == "nav_clock":
            state += list(raw.get("previous_action", [0.0, 0.0, -0.7, 0.0]))[:4]
    else:
        state = (
        list(raw["qpos"])
        + list(raw["qvel"])
        + list(raw["ctrl"])
        + list(raw["previous_action"])
        + list(raw.get("right_hand_pos", [0.0, 0.0, 0.0]))
        + list(raw.get("left_hand_pos", [0.0, 0.0, 0.0]))
        + list(raw.get("ball_pos", [0.0, 0.0, 0.0]))
        + list(raw.get("mouth_pos", [0.0, 0.0, 0.0]))
        + list(task_flags)
        )
    if include_stage_flags:
        flags = raw.get("stage_flags")
        if flags is None:
            flags = stage_one_hot(str(raw.get("stage", "approach")))
        state += list(flags)
    state += [
        float(raw.get("step", 0)) / 250.0,
        1.0 if raw.get("grasped", False) else 0.0,
        1.0 if raw.get("eaten", False) else 0.0,
    ]
    return state


def navigation_features_from_row(raw: dict) -> list[float]:
    qpos = list(raw.get("qpos", []))
    # qpos layout: berry freejoint has 7 dof, then Fire Boy root_x/root_y/root_z/root_yaw.
    root_x = float(qpos[7]) if len(qpos) > 7 else 0.0
    root_y = float(qpos[8]) if len(qpos) > 8 else 0.0
    root_yaw = float(qpos[10]) if len(qpos) > 10 else 0.0
    target = list(raw.get("ball_pos", [0.0, 0.0, 0.0]))
    target_x = float(target[0]) if len(target) > 0 else 0.0
    target_y = float(target[1]) if len(target) > 1 else 0.0
    return navigation_features(root_x, root_y, root_yaw, target_x, target_y)


def navigation_features(root_x: float, root_y: float, root_yaw: float, target_x: float, target_y: float) -> list[float]:
    dx = float(target_x - root_x)
    dy = float(target_y - root_y)
    distance = float(np.hypot(dx, dy))
    bearing = float(np.arctan2(dy, dx)) if distance > 1e-6 else 0.0
    relative_bearing = bearing - float(root_yaw)
    return [
        float(root_x),
        float(root_y),
        float(np.sin(root_yaw)),
        float(np.cos(root_yaw)),
        dx,
        dy,
        distance,
        float(np.sin(bearing)),
        float(np.cos(bearing)),
        float(np.sin(relative_bearing)),
        float(np.cos(relative_bearing)),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=Path("fireboy-vla-physics/build/datasets/fireboy_articulated_all"))
    parser.add_argument("--extra-dataset-dir", type=Path, action="append", default=[])
    parser.add_argument("--out-dir", type=Path, default=Path("fireboy-vla-physics/build/checkpoints/fireboy_articulated_all"))
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--task-filter", choices=TASK_NAMES, action="append", default=[])
    parser.add_argument("--include-stage-flags", action="store_true")
    parser.add_argument("--state-mode", choices=["full", "clock", "nav_clock"], default="full")
    args = parser.parse_args()
    result = train_articulated_policy(
        [args.dataset_dir, *args.extra_dataset_dir],
        args.out_dir,
        args.max_steps,
        task_filter=args.task_filter or None,
        include_stage_flags=args.include_stage_flags,
        state_mode=args.state_mode,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
