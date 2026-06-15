from __future__ import annotations

import argparse
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from eval_policy import state_from_obs
from pick_ball_env import PickBallConfig, PickBallEnv


DEFAULT_POLICY_PATH = Path("fireboy-vla-physics/checkpoints/berry_eat_wide/state_policy.npz")


def relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def policy_action(policy: dict[str, np.ndarray], state: np.ndarray) -> np.ndarray:
    x = (state - policy["x_mean"]) / policy["x_std"]
    h0 = relu(policy["w0"] @ x + policy["b0"])
    h1 = relu(policy["w1"] @ h0 + policy["b1"])
    y = policy["w2"] @ h1 + policy["b2"]
    return y * policy["y_std"] + policy["y_mean"]


def rollout(
    policy_path: Path,
    out_gif: Path,
    task: str = "eat_berry",
    seed: int = 5000,
    smooth_alpha: float = 0.25,
    max_frames: int = 180,
    render: bool = True,
) -> dict:
    raw = np.load(policy_path)
    policy = {key: raw[key] for key in raw.files}
    input_dim = int(policy["input_dim"])
    env = PickBallEnv(PickBallConfig(camera="world_cam", task=task, render=render, max_steps=240))
    obs = env.reset(seed=seed)
    previous_action = np.asarray(obs["previous_action"], dtype=np.float32)
    frames = []
    success = False
    try:
        for _ in range(env.config.max_steps):
            state = state_from_obs(obs, input_dim)
            action = policy_action(policy, state)
            action = np.clip(smooth_alpha * previous_action + (1.0 - smooth_alpha) * action, -1.0, 1.0)
            obs, _reward, done, truncated, info = env.step(action)
            previous_action = action.astype(np.float32, copy=True)
            if render and len(frames) < max_frames:
                frames.append(obs["image"])
            success = bool(info.get("success"))
            if done or truncated:
                for _ in range(8 if render else 0):
                    frames.append(obs["image"])
                break
    finally:
        env.close()
    out_gif.parent.mkdir(parents=True, exist_ok=True)
    if frames:
        imageio.mimsave(out_gif, frames, duration=0.05)
    return {
        "policy_path": str(policy_path),
        "gif_path": str(out_gif),
        "task": task,
        "success": success,
        "eaten": bool(obs.get("eaten", False)),
        "grasped": bool(obs.get("grasped", False)),
        "smooth_alpha": smooth_alpha,
        "rendered": render,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--out-gif", type=Path, default=Path("fireboy-vla-physics/build/smoke/learned_berry_eat.gif"))
    parser.add_argument("--task", choices=["pick_ball", "eat_berry"], default="eat_berry")
    parser.add_argument("--seed", type=int, default=5000)
    parser.add_argument("--smooth-alpha", type=float, default=0.25)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    print(rollout(args.policy, args.out_gif, args.task, args.seed, args.smooth_alpha, render=not args.no_render))


if __name__ == "__main__":
    main()
