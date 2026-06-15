from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def export_policy_npz(checkpoint: Path, out_path: Path) -> dict:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Torch is required to export the policy checkpoint") from exc

    payload = torch.load(checkpoint, map_location="cpu")
    model = payload["model"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        out_path,
        x_mean=np.asarray(payload["x_mean"], dtype=np.float32),
        x_std=np.asarray(payload["x_std"], dtype=np.float32),
        y_mean=np.asarray(payload["y_mean"], dtype=np.float32),
        y_std=np.asarray(payload["y_std"], dtype=np.float32),
        input_dim=np.asarray(payload["input_dim"], dtype=np.int64),
        action_dim=np.asarray(payload["action_dim"], dtype=np.int64),
        include_stage_flags=np.asarray(bool(payload.get("include_stage_flags", False)), dtype=np.bool_),
        state_mode=np.asarray(str(payload.get("state_mode", "full"))),
        w0=model["0.weight"].numpy().astype(np.float32),
        b0=model["0.bias"].numpy().astype(np.float32),
        w1=model["2.weight"].numpy().astype(np.float32),
        b1=model["2.bias"].numpy().astype(np.float32),
        w2=model["4.weight"].numpy().astype(np.float32),
        b2=model["4.bias"].numpy().astype(np.float32),
    )
    return {"checkpoint": str(checkpoint), "out_path": str(out_path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(export_policy_npz(args.checkpoint, args.out))


if __name__ == "__main__":
    main()
