from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio

from fireboy_mjcf import write_default_mjcf
from ik_expert import PickBallIkExpert
from pick_ball_env import PickBallConfig, PickBallEnv


def smoke_test(out_dir: Path = Path("fireboy-vla-physics/build/smoke")) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    xml_path = write_default_mjcf()
    env = PickBallEnv(PickBallConfig(camera="world_cam"))
    expert = PickBallIkExpert(env)
    frames = []
    obs = env.reset(seed=7)
    success = False
    total_reward = 0.0
    try:
        for _ in range(env.config.max_steps):
            action = expert.act(obs)
            obs, reward, done, truncated, info = env.step(action)
            total_reward += float(reward)
            if len(frames) < 90:
                frames.append(obs["image"])
            success = bool(info.get("success"))
            if done or truncated:
                break
    finally:
        env.close()
    gif_path = out_dir / "expert_smoke.gif"
    if frames:
        imageio.mimsave(gif_path, frames, duration=0.05)
    right_hand = obs["right_hand_pos"].tolist()
    left_hand = obs["left_hand_pos"].tolist()
    ball = obs["ball_pos"].tolist()
    return {
        "xml_path": str(xml_path),
        "gif_path": str(gif_path),
        "success": success,
        "reward": round(total_reward, 3),
        "grasped": bool(obs.get("grasped", False)),
        "final_right_hand": right_hand,
        "final_left_hand": left_hand,
        "final_ball": ball,
    }


if __name__ == "__main__":
    print(smoke_test())
