from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from dataset import EpisodeWriter
from eval_policy import state_from_obs
from ik_expert import PickBallIkExpert
from pick_ball_env import PickBallConfig, PickBallEnv
from rollout_numpy_policy import DEFAULT_POLICY_PATH, policy_action


def generate_recovery_dataset(
    num_episodes: int,
    out_dir: Path,
    policy_path: Path = DEFAULT_POLICY_PATH,
    seed: int = 7000,
    task: str = "eat_berry",
    policy_mix: float = 0.55,
    noise_std: float = 0.08,
    smooth_alpha: float = 0.25,
) -> dict:
    raw = np.load(policy_path)
    policy = {key: raw[key] for key in raw.files}
    input_dim = int(policy["input_dim"])
    env = PickBallEnv(PickBallConfig(seed=seed, render=False, task=task, max_steps=240))
    expert = PickBallIkExpert(env)
    writer = EpisodeWriter(out_dir, task=f"fireboy_{task}_recovery", save_images=False)
    successes = 0
    rows_total = 0
    rng = np.random.default_rng(seed)
    try:
        for episode in range(num_episodes):
            obs = env.reset(seed=seed + episode)
            expert.reset()
            previous_action = np.asarray(obs["previous_action"], dtype=np.float32)
            rows = []
            success = False
            for _ in range(env.config.max_steps):
                expert_action = expert.act(obs)
                state = state_from_obs(obs, input_dim)
                learned_action = policy_action(policy, state)
                learned_action = smooth_alpha * previous_action + (1.0 - smooth_alpha) * learned_action
                behavior_action = policy_mix * learned_action + (1.0 - policy_mix) * expert_action
                behavior_action += rng.normal(0.0, noise_std, size=behavior_action.shape).astype(np.float32)
                behavior_action = np.clip(behavior_action, -1.0, 1.0)
                next_obs, reward, terminated, truncated, info = env.step(behavior_action)
                rows.append(
                    {
                        "episode_id": episode,
                        "step": obs["step"],
                        "instruction": obs["instruction"],
                        "image": obs["image"],
                        "qpos": obs["qpos"],
                        "qvel": obs["qvel"],
                        "ctrl": obs["ctrl"],
                        "previous_action": obs["previous_action"],
                        "action": expert_action,
                        "behavior_action": behavior_action,
                        "learned_action": learned_action,
                        "reward": reward,
                        "success": bool(info.get("success")),
                        "grasped": bool(info.get("grasped")),
                        "eaten": bool(info.get("eaten")),
                        "right_hand_pos": obs["right_hand_pos"],
                        "left_hand_pos": obs["left_hand_pos"],
                        "mouth_pos": obs["mouth_pos"],
                        "ball_pos": obs["ball_pos"],
                        "source": "recovery_dagger",
                    }
                )
                rows_total += 1
                obs = next_obs
                previous_action = behavior_action.astype(np.float32, copy=True)
                success = bool(info.get("success"))
                if terminated or truncated:
                    break
            if success:
                successes += 1
            writer.write_episode(episode, rows)
    finally:
        env.close()
    return {
        "episodes": num_episodes,
        "rows": rows_total,
        "successes": successes,
        "success_rate": successes / max(1, num_episodes),
        "out_dir": str(out_dir),
        "policy_path": str(policy_path),
        "policy_mix": policy_mix,
        "noise_std": noise_std,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-episodes", type=int, default=300)
    parser.add_argument("--out-dir", type=Path, default=Path("fireboy-vla-physics/build/datasets/fireboy_eat_berry_recovery"))
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--seed", type=int, default=7000)
    parser.add_argument("--policy-mix", type=float, default=0.55)
    parser.add_argument("--noise-std", type=float, default=0.08)
    parser.add_argument("--smooth-alpha", type=float, default=0.25)
    args = parser.parse_args()
    print(
        generate_recovery_dataset(
            num_episodes=args.num_episodes,
            out_dir=args.out_dir,
            policy_path=args.policy,
            seed=args.seed,
            policy_mix=args.policy_mix,
            noise_std=args.noise_std,
            smooth_alpha=args.smooth_alpha,
        )
    )


if __name__ == "__main__":
    main()
