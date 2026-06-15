from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from eval_articulated_policy import EAT_DISTANCE, infer_stage, save_episode_media, state_from_demo
from fireboy_articulated_mjcf import ACTUATED_JOINTS
from generate_articulated_dataset import ActionCoder, TASK_NAMES
from render_articulated_fireboy import ArticulatedFireboyDemo


DEFAULT_OUT_DIR = Path("fireboy-vla-physics/build/articulated_policy")
RETARGET_FRAME_STRIDE = 2
RETARGET_MAX_FRAMES = 96


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
    task: str,
    out_dir: Path = DEFAULT_OUT_DIR,
    seed: int = 9100,
    smooth_alpha: float = 0.20,
    render: bool = True,
) -> dict[str, Any]:
    raw = np.load(policy_path)
    policy = {key: raw[key] for key in raw.files}
    input_dim = int(policy["input_dim"])
    state_mode = str(policy.get("state_mode", np.asarray("full")).item())
    rng = np.random.default_rng(seed)
    demo = ArticulatedFireboyDemo(camera="world_cam" if task in {"run_around", "go_to_point"} else "front_cam", render_enabled=render)
    coder = ActionCoder(demo)
    frames: list[np.ndarray] = []
    try:
        pose = demo.reset()
        target_xy: np.ndarray | None = None
        if task == "go_to_point":
            angle = rng.uniform(-0.75, 0.75)
            distance = rng.uniform(0.34, 0.54)
            berry = np.array([distance * math.cos(angle), distance * math.sin(angle), 0.295], dtype=np.float64)
            target_xy = berry[:2].copy()
        else:
            berry = np.array(
                [
                    0.40 + rng.uniform(-0.030, 0.030),
                    -0.10 + rng.uniform(-0.035, 0.035),
                    0.295,
                ],
                dtype=np.float64,
            )
        demo.set_berry(berry)
        previous_action = coder.pose_to_action(pose)
        grasped = False
        eaten = False
        berry_attached = False
        attach_offset = np.zeros(3, dtype=np.float64)
        min_mouth_dist = float("inf")
        start_xy = np.array([pose["root_x"], pose["root_y"]], dtype=np.float64)
        max_steps = 180 if task == "run_around" else 170 if task == "go_to_point" else 240
        success = False
        retarget_frames: list[dict[str, Any]] = []
        for step in range(max_steps):
            stage = infer_stage(task, step, grasped, eaten, berry_attached, demo)
            state = state_from_demo(
                demo,
                previous_action,
                task,
                step,
                grasped,
                eaten,
                input_dim,
                include_stage_flags=bool(policy.get("include_stage_flags", False)),
                stage=stage,
                state_mode=state_mode,
            )
            action = policy_action(policy, state)
            action = np.clip(smooth_alpha * previous_action + (1.0 - smooth_alpha) * action, -1.0, 1.0)
            target_pose = coder.action_to_pose(action)
            maybe_append_retarget_frame(retarget_frames, step, stage, target_pose)
            closing = target_pose.get("finger_R_a", 0.060) < 0.032 and target_pose.get("finger_R_b", 0.060) < 0.032
            is_manipulation = task not in {"run_around", "go_to_point"}
            demo.set_right_gripper_collision(is_manipulation and closing)
            demo.step(target_pose, 4 if is_manipulation else 3)

            hand = demo.site_pos("right_hand")
            berry_pos = demo.berry_pos()
            if is_manipulation and closing and not berry_attached and np.linalg.norm(hand - berry_pos) < 0.14:
                grasped = True
                berry_attached = True
                attach_offset = berry_pos - hand
                attach_offset[2] = np.clip(attach_offset[2], -0.018, 0.026)
            if berry_attached:
                berry_target = hand + attach_offset
                berry_target[2] = max(berry_target[2], 0.29)
                demo.set_berry(berry_target)
            min_mouth_dist = min(min_mouth_dist, float(np.linalg.norm(demo.berry_pos() - demo.site_pos("mouth"))))
            if task == "go_eat_berry" and min_mouth_dist < EAT_DISTANCE:
                eaten = True
            if task == "pick_up":
                success = bool(grasped and demo.berry_pos()[2] > 0.36)
            elif task == "go_eat_berry":
                success = bool(eaten)
            elif task == "go_to_point":
                root_xy = np.array(
                    [
                        demo.data.qpos[demo.qpos_addr["root_x"]],
                        demo.data.qpos[demo.qpos_addr["root_y"]],
                    ],
                    dtype=np.float64,
                )
                compare_xy = target_xy if target_xy is not None else demo.berry_pos()[:2]
                success = bool(np.linalg.norm(root_xy - compare_xy) < 0.10)
            else:
                root_xy = np.array([target_pose["root_x"], target_pose["root_y"]], dtype=np.float64)
                success = bool(np.linalg.norm(root_xy - start_xy) > 0.25)

            previous_action = action.astype(np.float32, copy=True)
            if render and step % 2 == 0:
                frames.append(demo.render())
            if success and task != "run_around" and step > 40:
                break

        media = save_episode_media(frames, out_dir / f"faithful_learned_{task}") if render else {}
        return {
            "policy_path": str(policy_path),
            "task": task,
            "success": success,
            "grasped": grasped,
            "eaten": eaten,
            "final_berry_pos": demo.berry_pos().round(4).tolist(),
            "final_root_xy": [
                round(float(demo.data.qpos[demo.qpos_addr["root_x"]]), 4),
                round(float(demo.data.qpos[demo.qpos_addr["root_y"]]), 4),
            ],
            "target_xy": target_xy.round(4).tolist() if target_xy is not None else None,
            "min_mouth_dist": round(min_mouth_dist, 4) if math.isfinite(min_mouth_dist) else None,
            "gif_path": media.get("gif"),
            "mp4_path": media.get("mp4"),
            "retarget_trajectory": {
                "format": "fireboy_articulated_pose_v1",
                "source": "mujoco_articulated_policy",
                "task": task,
                "joint_names": list(ACTUATED_JOINTS),
                "fps": 24,
                "duration_ms": int(max(900, len(retarget_frames) * 1000 / 24)),
                "frames": retarget_frames,
            },
        }
    finally:
        demo.close()


def maybe_append_retarget_frame(frames: list[dict[str, Any]], step: int, stage: str, pose: dict[str, float]) -> None:
    if step % RETARGET_FRAME_STRIDE and len(frames) < RETARGET_MAX_FRAMES - 1:
        return
    if len(frames) >= RETARGET_MAX_FRAMES:
        return
    frames.append(
        {
            "step": int(step),
            "stage": stage,
            "values": [round(float(pose.get(name, 0.0)), 5) for name in ACTUATED_JOINTS],
        }
    )


def default_policy(task: str) -> Path:
    return Path(f"fireboy-vla-physics/checkpoints/fireboy_articulated_{task}/faithful_articulated_policy.npz")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=TASK_NAMES, default="run_around")
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed", type=int, default=9100)
    parser.add_argument("--smooth-alpha", type=float, default=0.20)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    result = rollout(
        policy_path=args.policy or default_policy(args.task),
        task=args.task,
        out_dir=args.out_dir,
        seed=args.seed,
        smooth_alpha=args.smooth_alpha,
        render=not args.no_render,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
