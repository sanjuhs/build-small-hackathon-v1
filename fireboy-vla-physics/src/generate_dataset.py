from __future__ import annotations

import argparse
from pathlib import Path

from dataset import EpisodeWriter
from ik_expert import PickBallIkExpert
from pick_ball_env import PickBallConfig, PickBallEnv


def generate_dataset(num_episodes: int, out_dir: Path, seed: int = 1, task: str = "pick_ball", save_images: bool = True) -> dict:
    env = PickBallEnv(PickBallConfig(seed=seed, render=False, task=task))
    expert = PickBallIkExpert(env)
    writer = EpisodeWriter(out_dir, task=f"fireboy_{task}", save_images=save_images)
    successes = 0
    try:
        for episode in range(num_episodes):
            obs = env.reset(seed=seed + episode)
            expert.reset()
            rows = []
            success = False
            for _ in range(env.config.max_steps):
                action = expert.act(obs)
                next_obs, reward, terminated, truncated, info = env.step(action)
                rows.append({
                    "episode_id": episode,
                    "step": obs["step"],
                    "instruction": obs["instruction"],
                    "image": obs["image"],
                    "qpos": obs["qpos"],
                    "qvel": obs["qvel"],
                    "ctrl": obs["ctrl"],
                    "previous_action": obs["previous_action"],
                    "action": action,
                    "reward": reward,
                    "success": bool(info.get("success")),
                    "grasped": bool(info.get("grasped")),
                    "eaten": bool(info.get("eaten")),
                    "right_hand_pos": obs["right_hand_pos"],
                    "left_hand_pos": obs["left_hand_pos"],
                    "mouth_pos": obs["mouth_pos"],
                    "ball_pos": obs["ball_pos"],
                })
                obs = next_obs
                success = bool(info.get("success"))
                if terminated or truncated:
                    break
            if success:
                successes += 1
            writer.write_episode(episode, rows)
    finally:
        env.close()
    return {"episodes": num_episodes, "successes": successes, "success_rate": successes / max(1, num_episodes), "out_dir": str(out_dir)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-episodes", type=int, default=10)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--task", choices=["pick_ball", "eat_berry"], default="pick_ball")
    parser.add_argument("--no-images", action="store_true")
    args = parser.parse_args()
    out_dir = args.out_dir or Path(f"fireboy-vla-physics/build/datasets/fireboy_{args.task}")
    print(generate_dataset(args.num_episodes, out_dir, args.seed, args.task, save_images=not args.no_images))


if __name__ == "__main__":
    main()
