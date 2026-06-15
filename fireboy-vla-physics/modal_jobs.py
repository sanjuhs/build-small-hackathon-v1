from __future__ import annotations

from pathlib import Path

import modal


app = modal.App("fireboy-vla-physics")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("fireboy-vla-physics/requirements.txt")
    .add_local_dir("fireboy-vla-physics", remote_path="/root/fireboy-vla-physics")
)

data_volume = modal.Volume.from_name("fireboy-vla-data", create_if_missing=True)
checkpoint_volume = modal.Volume.from_name("fireboy-vla-checkpoints", create_if_missing=True)


def _prepare_path() -> None:
    import sys

    sys.path.insert(0, "/root/fireboy-vla-physics/src")


@app.function(image=image, volumes={"/data": data_volume}, timeout=600)
def smoke_test_env() -> dict:
    _prepare_path()
    from smoke_test_env import smoke_test

    result = smoke_test(Path("/data/smoke"))
    data_volume.commit()
    return result


@app.function(image=image, volumes={"/data": data_volume}, timeout=60 * 60)
def generate_dataset(num_episodes: int = 200, seed: int = 1) -> dict:
    _prepare_path()
    from generate_dataset import generate_dataset as run

    result = run(num_episodes=num_episodes, out_dir=Path("/data/datasets/fireboy_pick_ball"), seed=seed)
    data_volume.commit()
    return result


@app.function(image=image, gpu="L40S", volumes={"/data": data_volume, "/checkpoints": checkpoint_volume}, timeout=60 * 60)
def train_policy(max_steps: int = 5000) -> dict:
    _prepare_path()
    from train_policy import train_policy as run

    result = run(
        dataset_dir=Path("/data/datasets/fireboy_pick_ball"),
        out_dir=Path("/checkpoints/fireboy_pick_ball"),
        max_steps=max_steps,
    )
    checkpoint_volume.commit()
    return result


@app.function(image=image, gpu="L40S", volumes={"/data": data_volume, "/checkpoints": checkpoint_volume}, timeout=30 * 60)
def eval_policy(num_episodes: int = 25) -> dict:
    _prepare_path()
    from eval_policy import eval_policy as run

    return run(Path("/checkpoints/fireboy_pick_ball/state_policy.pt"), num_episodes=num_episodes)
