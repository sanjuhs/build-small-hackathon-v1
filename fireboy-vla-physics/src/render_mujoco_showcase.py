from __future__ import annotations

import argparse
import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from eval_policy import state_from_obs
from fireboy_mjcf import ACTUATED_JOINTS, write_default_mjcf
from ik_expert import PickBallIkExpert
from pick_ball_env import PickBallConfig, PickBallEnv
from rollout_numpy_policy import DEFAULT_POLICY_PATH, policy_action


DEFAULT_OUT_DIR = Path("fireboy-vla-physics/build/showcase")


def render_showcase(
    mode: str,
    out_dir: Path = DEFAULT_OUT_DIR,
    policy_path: Path = DEFAULT_POLICY_PATH,
    seed: int = 5000,
    smooth_alpha: float = 0.25,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_default_mjcf()
    if mode == "rest":
        result = render_rest(out_dir, seed)
    elif mode == "expert":
        result = render_expert(out_dir, seed)
    elif mode == "learned":
        result = render_learned(out_dir, policy_path, seed, smooth_alpha)
    else:
        raise ValueError(f"Unknown mode: {mode}")
    result["model_summary"] = model_summary()
    return result


def render_rest(out_dir: Path, seed: int) -> dict:
    env = PickBallEnv(PickBallConfig(camera="world_cam", task="eat_berry", render=True, width=480, height=368, max_steps=80))
    frames = []
    obs = env.reset(seed=seed)
    try:
        for _ in range(64):
            frames.append(obs["image"])
    finally:
        env.close()
    return save_media(frames, out_dir / "mujoco_fireboy_rest", {"mode": "rest", "success": True})


def render_expert(out_dir: Path, seed: int) -> dict:
    env = PickBallEnv(PickBallConfig(camera="world_cam", task="eat_berry", render=True, width=480, height=368, max_steps=240))
    expert = PickBallIkExpert(env)
    obs = env.reset(seed=seed)
    frames = []
    success = False
    try:
        for _ in range(env.config.max_steps):
            action = expert.act(obs)
            obs, _reward, done, truncated, info = env.step(action)
            if len(frames) < 180:
                frames.append(obs["image"])
            success = bool(info.get("success"))
            if done or truncated:
                for _ in range(10):
                    frames.append(obs["image"])
                break
    finally:
        env.close()
    return save_media(
        frames,
        out_dir / "mujoco_fireboy_expert_eat_berry",
        {"mode": "expert", "success": success, "eaten": bool(obs.get("eaten", False)), "grasped": bool(obs.get("grasped", False))},
    )


def render_learned(out_dir: Path, policy_path: Path, seed: int, smooth_alpha: float) -> dict:
    raw = np.load(policy_path)
    policy = {key: raw[key] for key in raw.files}
    input_dim = int(policy["input_dim"])
    env = PickBallEnv(PickBallConfig(camera="world_cam", task="eat_berry", render=True, width=480, height=368, max_steps=240))
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
            if len(frames) < 180:
                frames.append(obs["image"])
            success = bool(info.get("success"))
            if done or truncated:
                for _ in range(10):
                    frames.append(obs["image"])
                break
    finally:
        env.close()
    return save_media(
        frames,
        out_dir / "mujoco_fireboy_learned_eat_berry",
        {
            "mode": "learned",
            "success": success,
            "eaten": bool(obs.get("eaten", False)),
            "grasped": bool(obs.get("grasped", False)),
            "policy_path": str(policy_path),
            "smooth_alpha": smooth_alpha,
        },
    )


def save_media(frames: list[np.ndarray], stem: Path, result: dict) -> dict:
    if not frames:
        return result | {"gif_path": None, "mp4_path": None}
    gif_path = stem.with_suffix(".gif")
    mp4_path = stem.with_suffix(".mp4")
    imageio.mimsave(gif_path, frames, duration=0.05)
    try:
        imageio.mimsave(mp4_path, frames, fps=20)
        mp4 = str(mp4_path)
    except Exception as exc:
        mp4 = None
        result["mp4_error"] = str(exc)[:240]
    return result | {"gif_path": str(gif_path), "mp4_path": mp4, "frames": len(frames)}


def model_summary() -> dict:
    return {
        "truth": "Current MuJoCo body is a bimanual manipulation harness, not a full articulated humanoid.",
        "visual_body": "Static Fire Boy costume made from MuJoCo geoms.",
        "actuated_joints": list(ACTUATED_JOINTS),
        "action_dim": len(ACTUATED_JOINTS),
        "manipulator": "Two Cartesian end-effectors with high-friction hand tips/lips.",
        "task": "eat_berry: grasp berry with both hands, move it to mouth target, mark eaten=True.",
        "next_physics_upgrade": "Replace this harness with Unitree G1/H1/SMPL-like humanoid body and retarget Fire Boy mesh as a costume.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["rest", "expert", "learned"], default="learned")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--seed", type=int, default=5000)
    parser.add_argument("--smooth-alpha", type=float, default=0.25)
    args = parser.parse_args()
    print(json.dumps(render_showcase(args.mode, args.out_dir, args.policy, args.seed, args.smooth_alpha), indent=2))


if __name__ == "__main__":
    main()
