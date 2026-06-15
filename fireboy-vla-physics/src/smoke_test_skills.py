from __future__ import annotations

import json

from fireboy_mjcf import write_default_mjcf
from ik_expert import PickBallIkExpert
from pet_skills import PetSkillController, SUPPORTED_SKILLS
from pick_ball_env import PickBallConfig, PickBallEnv


def smoke_pick_ball() -> dict:
    write_default_mjcf()
    env = PickBallEnv(PickBallConfig(camera="world_cam", render=False))
    expert = PickBallIkExpert(env)
    obs = env.reset(seed=7)
    total_reward = 0.0
    try:
        for _ in range(env.config.max_steps):
            action = expert.act(obs)
            obs, reward, done, truncated, info = env.step(action)
            total_reward += float(reward)
            if done or truncated:
                return {
                    "success": bool(info["success"]),
                    "grasped": bool(info["grasped"]),
                    "reward": round(total_reward, 3),
                    "ball_z": round(float(obs["ball_pos"][2]), 3),
                }
    finally:
        env.close()
    return {"success": False, "grasped": False, "reward": round(total_reward, 3), "ball_z": round(float(obs["ball_pos"][2]), 3)}


def smoke_eat_berry() -> dict:
    write_default_mjcf()
    env = PickBallEnv(PickBallConfig(render=False, task="eat_berry", max_steps=240))
    expert = PickBallIkExpert(env)
    obs = env.reset(seed=11)
    total_reward = 0.0
    try:
        for _ in range(env.config.max_steps):
            action = expert.act(obs)
            obs, reward, done, truncated, info = env.step(action)
            total_reward += float(reward)
            if done or truncated:
                return {
                    "success": bool(info["success"]),
                    "grasped": bool(info["grasped"]),
                    "eaten": bool(info["eaten"]),
                    "reward": round(total_reward, 3),
                }
    finally:
        env.close()
    return {"success": False, "grasped": False, "eaten": False, "reward": round(total_reward, 3)}


def smoke_skills() -> dict:
    controller = PetSkillController()
    commands = [
        "idle",
        "walk around",
        "run around",
        "walk to me",
        "run to the ball",
        "turn and look",
        "wave",
        "sit",
        "dance",
        "pick up the ball",
        "drop the ball",
        "go find berry and eat it",
    ]
    routed = []
    for command in commands:
        result = controller.execute_text(command)
        routed.append(
            {
                "command": command,
                "skill": result.skill,
                "lane": result.lane,
                "success": result.success,
                "path_points": len(result.path),
                "holding": result.pose.holding,
            }
        )
    pick = smoke_pick_ball()
    berry = smoke_eat_berry()
    ok = all(item["success"] for item in routed) and pick["success"] and berry["success"] and set(SUPPORTED_SKILLS)
    return {"success": bool(ok), "routed": routed, "pick_ball": pick, "eat_berry": berry}


if __name__ == "__main__":
    result = smoke_skills()
    print(json.dumps(result, indent=2))
    if not result["success"]:
        raise SystemExit(1)
