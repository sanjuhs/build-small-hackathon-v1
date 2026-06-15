from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def train_policy(dataset_dir: Path | list[Path], out_dir: Path, max_steps: int = 1000) -> dict:
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("Install torch from fireboy-vla-physics/requirements.txt before training") from exc

    dataset_dirs = dataset_dir if isinstance(dataset_dir, list) else [dataset_dir]
    rows = load_rows(dataset_dirs, limit=max_steps * 8)
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
        nn.Linear(xt.shape[1], 256),
        nn.ReLU(),
        nn.Linear(256, 256),
        nn.ReLU(),
        nn.Linear(256, yt.shape[1]),
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4)
    batch = min(256, len(rows))
    losses = []
    for step in range(max_steps):
        idx = torch.randint(0, xt.shape[0], (batch,))
        pred = model(xt[idx])
        loss = torch.nn.functional.mse_loss(pred, yt[idx])
        opt.zero_grad()
        loss.backward()
        opt.step()
        if step % 50 == 0 or step == max_steps - 1:
            losses.append(float(loss.detach().cpu()))

    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = out_dir / "state_policy.pt"
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
            "state_schema": "qpos_qvel_ctrl_prev_hands_object_mouth_taskflags_v2",
            "note": "State-only MuJoCo policy. Replace the state encoder with MiniCPM-V image-language features for the true VLA stage.",
        },
        checkpoint,
    )
    return {"rows": len(rows), "datasets": [str(path) for path in dataset_dirs], "checkpoint": str(checkpoint), "device": str(device), "losses": losses[-10:]}


def load_rows(dataset_dirs: list[Path], limit: int) -> list[dict]:
    rows = []
    for dataset_dir in dataset_dirs:
        for path in sorted((dataset_dir / "episodes").glob("*.jsonl")):
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    raw = json.loads(line)
                    state = state_from_row(raw)
                    rows.append({"state": state, "action": raw["action"]})
                    if len(rows) >= limit:
                        return rows
    return rows


def state_from_row(raw: dict) -> list[float]:
    return (
        list(raw["qpos"])
        + list(raw["qvel"])
        + list(raw["ctrl"])
        + list(raw["previous_action"])
        + list(raw.get("right_hand_pos", [0.0, 0.0, 0.0]))
        + list(raw.get("left_hand_pos", [0.0, 0.0, 0.0]))
        + list(raw.get("ball_pos", [0.0, 0.0, 0.0]))
        + list(raw.get("mouth_pos", [0.0, 0.0, 0.0]))
        + [
            float(raw.get("step", 0)) / 250.0,
            1.0 if raw.get("grasped", False) else 0.0,
            1.0 if raw.get("eaten", False) else 0.0,
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=Path("fireboy-vla-physics/build/datasets/fireboy_pick_ball"))
    parser.add_argument("--extra-dataset-dir", type=Path, action="append", default=[])
    parser.add_argument("--out-dir", type=Path, default=Path("fireboy-vla-physics/build/checkpoints"))
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args()
    print(train_policy([args.dataset_dir, *args.extra_dataset_dir], args.out_dir, args.max_steps))


if __name__ == "__main__":
    main()
