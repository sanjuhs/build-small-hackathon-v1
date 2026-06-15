from __future__ import annotations

import argparse
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from fireboy_mjcf import write_default_mjcf
from ik_expert import PickBallIkExpert
from pick_ball_env import PickBallConfig, PickBallEnv


def smoke_test(out_dir: Path = Path("fireboy-vla-physics/build/smoke"), render: bool = True) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    xml_path = write_default_mjcf()
    env = PickBallEnv(PickBallConfig(camera="world_cam", task="eat_berry", render=render, max_steps=240))
    expert = PickBallIkExpert(env)
    frames = []
    obs = env.reset(seed=11)
    success = False
    total_reward = 0.0
    try:
        for _ in range(env.config.max_steps):
            action = expert.act(obs)
            obs, reward, done, truncated, info = env.step(action)
            total_reward += float(reward)
            if render and len(frames) < 150:
                frames.append(obs["image"])
            success = bool(info.get("success"))
            if done or truncated:
                if render:
                    for _ in range(8):
                        frames.append(obs["image"])
                break
    finally:
        env.close()
    gif_path = out_dir / "berry_eat.gif"
    if frames:
        imageio.mimsave(gif_path, frames, duration=0.05)
    mouth = np.asarray(obs["mouth_pos"], dtype=np.float32)
    berry = np.asarray(obs["ball_pos"], dtype=np.float32)
    return {
        "xml_path": str(xml_path),
        "gif_path": str(gif_path) if frames else None,
        "success": success,
        "eaten": bool(obs.get("eaten", False)),
        "grasped": bool(obs.get("grasped", False)),
        "reward": round(total_reward, 3),
        "final_mouth": mouth.tolist(),
        "final_berry": berry.tolist(),
        "mouth_distance": round(float(np.linalg.norm(berry - mouth)), 4),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=Path("fireboy-vla-physics/build/smoke"))
    args = parser.parse_args()
    print(smoke_test(args.out_dir, render=not args.no_render))
