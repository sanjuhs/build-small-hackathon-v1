from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from eval_articulated_policy import EAT_DISTANCE, infer_stage, save_episode_media, state_from_demo
from generate_articulated_dataset import ActionCoder, TASK_NAMES
from render_articulated_fireboy import ArticulatedFireboyDemo


DEFAULT_CHECKPOINT = Path("fireboy-vla-physics/build/checkpoints/fireboy_articulated_go_eat_berry_chunk/faithful_articulated_chunk_policy.pt")
DEFAULT_OUT_DIR = Path("fireboy-vla-physics/build/articulated_chunk_policy")


def eval_articulated_chunk_policy(
    checkpoint: Path = DEFAULT_CHECKPOINT,
    task: str = "go_eat_berry",
    num_episodes: int = 10,
    seed: int = 9300,
    smooth_alpha: float = 0.0,
    replan_interval: int = 8,
    render: bool = False,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("Install torch from fireboy-vla-physics/requirements.txt before evaluation") from exc

    payload = torch.load(checkpoint, map_location="cpu")
    model = nn.Sequential(
        nn.Linear(int(payload["input_dim"]), 512),
        nn.SiLU(),
        nn.Linear(512, 512),
        nn.SiLU(),
        nn.Linear(512, int(payload["output_dim"])),
    )
    model.load_state_dict(payload["model"])
    model.eval()

    rng = np.random.default_rng(seed)
    successes = 0
    episode_reports = []
    for episode in range(num_episodes):
        report = rollout_episode(
            model,
            payload,
            task,
            rng,
            smooth_alpha=smooth_alpha,
            replan_interval=replan_interval,
            render=render and episode == 0,
            out_dir=out_dir,
            episode_id=episode,
        )
        successes += int(report["success"])
        episode_reports.append(report)
    return {
        "checkpoint": str(checkpoint),
        "task": task,
        "episodes": num_episodes,
        "successes": successes,
        "success_rate": successes / max(1, num_episodes),
        "smooth_alpha": smooth_alpha,
        "replan_interval": replan_interval,
        "chunk_steps": int(payload["chunk_steps"]),
        "reports": episode_reports,
    }


def rollout_episode(
    model: Any,
    payload: dict[str, Any],
    task: str,
    rng: np.random.Generator,
    smooth_alpha: float,
    replan_interval: int,
    render: bool,
    out_dir: Path,
    episode_id: int,
) -> dict[str, Any]:
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
        max_steps = 180 if task == "run_around" else 170 if task == "go_to_point" else 250
        success = False
        action_plan: np.ndarray | None = None
        plan_index = 0

        for step in range(max_steps):
            stage = infer_stage(task, step, grasped, eaten, berry_attached, demo)
            should_replan = (
                action_plan is None
                or plan_index >= len(action_plan)
                or (replan_interval > 0 and step % replan_interval == 0)
            )
            if should_replan:
                state = state_from_demo(
                    demo,
                    previous_action,
                    task,
                    step,
                    grasped,
                    eaten,
                    int(payload["input_dim"]),
                    include_stage_flags=bool(payload.get("include_stage_flags", False)),
                    stage=stage,
                    state_mode=str(payload.get("state_mode", "clock")),
                )
                flat_plan = predict_action_chunk(model, payload, state)
                action_plan = flat_plan.reshape(int(payload["chunk_steps"]), int(payload["action_dim"]))
                plan_index = 0

            action = action_plan[plan_index]
            plan_index += 1
            action = np.clip(smooth_alpha * previous_action + (1.0 - smooth_alpha) * action, -1.0, 1.0)
            target_pose = coder.action_to_pose(action)
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

        media = save_episode_media(frames, out_dir / f"faithful_chunk_{task}_policy_ep{episode_id:03d}") if render else {}
        return {
            "episode": episode_id,
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
        }
    finally:
        demo.close()


def predict_action_chunk(model: Any, payload: dict[str, Any], state: np.ndarray) -> np.ndarray:
    import torch

    x = (state - np.asarray(payload["x_mean"], dtype=np.float32)) / np.asarray(payload["x_std"], dtype=np.float32)
    with torch.no_grad():
        y = model(torch.tensor(x, dtype=torch.float32).unsqueeze(0)).squeeze(0).numpy()
    action = y * np.asarray(payload["y_std"], dtype=np.float32) + np.asarray(payload["y_mean"], dtype=np.float32)
    return np.clip(action, -1.0, 1.0).astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--task", choices=TASK_NAMES, default="go_eat_berry")
    parser.add_argument("--num-episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=9300)
    parser.add_argument("--smooth-alpha", type=float, default=0.0)
    parser.add_argument("--replan-interval", type=int, default=8)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    result = eval_articulated_chunk_policy(
        checkpoint=args.checkpoint,
        task=args.task,
        num_episodes=args.num_episodes,
        seed=args.seed,
        smooth_alpha=args.smooth_alpha,
        replan_interval=args.replan_interval,
        render=args.render,
        out_dir=args.out_dir,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
