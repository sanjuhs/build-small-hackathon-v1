from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from pick_ball_env import PickBallConfig, PickBallEnv


def eval_policy(
    checkpoint: Path,
    num_episodes: int = 10,
    seed: int = 100,
    task: str = "pick_ball",
    smooth_alpha: float = 0.25,
) -> dict:
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("Install torch from fireboy-vla-physics/requirements.txt before evaluation") from exc

    payload = torch.load(checkpoint, map_location="cpu")
    model = nn.Sequential(
        nn.Linear(payload["input_dim"], 256),
        nn.ReLU(),
        nn.Linear(256, 256),
        nn.ReLU(),
        nn.Linear(256, payload["action_dim"]),
    )
    model.load_state_dict(payload["model"])
    model.eval()

    env = PickBallEnv(PickBallConfig(render=False, task=task))
    successes = 0
    eaten = 0
    try:
        for episode in range(num_episodes):
            obs = env.reset(seed=seed + episode)
            previous_action = np.asarray(obs["previous_action"], dtype=np.float32).copy()
            success = False
            for _ in range(env.config.max_steps):
                state = state_from_obs(obs, int(payload["input_dim"]))
                x = (state - payload["x_mean"]) / payload["x_std"]
                with torch.no_grad():
                    y = model(torch.tensor(x).float().unsqueeze(0)).squeeze(0).numpy()
                action = y * payload["y_std"] + payload["y_mean"]
                if smooth_alpha > 0.0:
                    action = smooth_alpha * previous_action + (1.0 - smooth_alpha) * action
                action = np.clip(action, -1.0, 1.0)
                obs, _reward, done, truncated, info = env.step(action)
                previous_action = action.astype(np.float32, copy=True)
                success = bool(info.get("success"))
                if done or truncated:
                    break
            successes += int(success)
            eaten += int(bool(obs.get("eaten", False)))
    finally:
        env.close()
    return {
        "task": task,
        "episodes": num_episodes,
        "successes": successes,
        "success_rate": successes / max(1, num_episodes),
        "eaten": eaten,
        "smooth_alpha": smooth_alpha,
    }


def state_from_obs(obs: dict, input_dim: int) -> np.ndarray:
    old_state = (
        list(obs["qpos"])
        + list(obs["qvel"])
        + list(obs["ctrl"])
        + list(obs["previous_action"])
        + list(obs["right_hand_pos"])
        + list(obs["left_hand_pos"])
        + list(obs["ball_pos"])
        + [float(obs["step"]) / 200.0, 1.0 if obs.get("grasped", False) else 0.0]
    )
    new_state = (
        list(obs["qpos"])
        + list(obs["qvel"])
        + list(obs["ctrl"])
        + list(obs["previous_action"])
        + list(obs["right_hand_pos"])
        + list(obs["left_hand_pos"])
        + list(obs["ball_pos"])
        + list(obs.get("mouth_pos", [0.0, 0.0, 0.0]))
        + [
            float(obs["step"]) / 250.0,
            1.0 if obs.get("grasped", False) else 0.0,
            1.0 if obs.get("eaten", False) else 0.0,
        ]
    )
    state = old_state if input_dim == len(old_state) else new_state
    if len(state) < input_dim:
        state = state + [0.0] * (input_dim - len(state))
    return np.asarray(state[:input_dim], dtype=np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=Path("fireboy-vla-physics/build/checkpoints/state_policy.pt"))
    parser.add_argument("--num-episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--task", choices=["pick_ball", "eat_berry"], default="pick_ball")
    parser.add_argument("--smooth-alpha", type=float, default=0.25)
    args = parser.parse_args()
    print(eval_policy(args.checkpoint, args.num_episodes, args.seed, args.task, args.smooth_alpha))


if __name__ == "__main__":
    main()
