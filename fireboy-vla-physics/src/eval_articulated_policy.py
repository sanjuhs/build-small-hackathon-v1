from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np

from generate_articulated_dataset import ActionCoder, STAGE_NAMES, TASK_NAMES, stage_one_hot
from render_articulated_fireboy import ArticulatedFireboyDemo
from train_articulated_policy import navigation_features


DEFAULT_CHECKPOINT = Path("fireboy-vla-physics/build/checkpoints/fireboy_articulated_all/faithful_articulated_policy.pt")
DEFAULT_OUT_DIR = Path("fireboy-vla-physics/build/articulated_policy")
EAT_DISTANCE = 0.14


def eval_articulated_policy(
    checkpoint: Path = DEFAULT_CHECKPOINT,
    task: str = "go_eat_berry",
    num_episodes: int = 5,
    seed: int = 9000,
    smooth_alpha: float = 0.20,
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
        nn.Linear(int(payload["input_dim"]), 384),
        nn.ReLU(),
        nn.Linear(384, 384),
        nn.ReLU(),
        nn.Linear(384, int(payload["action_dim"])),
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
        "reports": episode_reports,
    }


def rollout_episode(
    model: Any,
    payload: dict[str, Any],
    task: str,
    rng: np.random.Generator,
    smooth_alpha: float,
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
        max_steps = 180 if task == "run_around" else 170 if task == "go_to_point" else 240
        success = False
        for step in range(max_steps):
            stage = infer_stage(task, step, grasped, eaten, berry_attached, demo)
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
                state_mode=str(payload.get("state_mode", "full")),
            )
            x = (state - np.asarray(payload["x_mean"], dtype=np.float32)) / np.asarray(payload["x_std"], dtype=np.float32)
            with torch_no_grad(model) as predict:
                y = predict(x)
            action = y * np.asarray(payload["y_std"], dtype=np.float32) + np.asarray(payload["y_mean"], dtype=np.float32)
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

        media = save_episode_media(frames, out_dir / f"faithful_articulated_{task}_policy_ep{episode_id:03d}") if render else {}
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


class torch_no_grad:
    def __init__(self, model: Any):
        self.model = model
        self.torch = None
        self.guard = None

    def __enter__(self):
        import torch

        self.torch = torch
        self.guard = torch.no_grad()
        self.guard.__enter__()

        def predict(x: np.ndarray) -> np.ndarray:
            tensor = torch.tensor(x, dtype=torch.float32).unsqueeze(0)
            return self.model(tensor).squeeze(0).numpy()

        return predict

    def __exit__(self, exc_type, exc, tb):
        if self.guard is not None:
            self.guard.__exit__(exc_type, exc, tb)
        return False


def state_from_demo(
    demo: ArticulatedFireboyDemo,
    previous_action: np.ndarray,
    task: str,
    step: int,
    grasped: bool,
    eaten: bool,
    input_dim: int,
    include_stage_flags: bool = False,
    stage: str | None = None,
    state_mode: str = "full",
) -> np.ndarray:
    task_flags = task_flags_for(task)
    if state_mode in {"clock", "nav_clock"}:
        nav_state: list[float] = []
        if state_mode == "nav_clock":
            root_x = float(demo.data.qpos[demo.qpos_addr["root_x"]])
            root_y = float(demo.data.qpos[demo.qpos_addr["root_y"]])
            root_yaw = float(demo.data.qpos[demo.qpos_addr["root_yaw"]])
            target = demo.berry_pos()
            nav_state = navigation_features(root_x, root_y, root_yaw, float(target[0]), float(target[1]))
        state = (
            nav_state
            + list(demo.site_pos("right_hand"))
            + list(demo.site_pos("left_hand"))
            + list(demo.berry_pos())
            + list(demo.site_pos("mouth"))
            + task_flags
        )
        if state_mode == "nav_clock":
            state += list(np.asarray(previous_action, dtype=np.float32))[:4]
    else:
        state = (
            list(np.asarray(demo.data.qpos, dtype=np.float32))
            + list(np.asarray(demo.data.qvel, dtype=np.float32))
            + list(np.asarray(demo.data.ctrl, dtype=np.float32))
            + list(np.asarray(previous_action, dtype=np.float32))
            + list(demo.site_pos("right_hand"))
            + list(demo.site_pos("left_hand"))
            + list(demo.berry_pos())
            + list(demo.site_pos("mouth"))
            + task_flags
        )
    if include_stage_flags:
        state += stage_one_hot(stage or infer_stage(task, step, grasped, eaten, False, demo))
    state += [
        float(step) / 250.0,
        1.0 if grasped else 0.0,
        1.0 if eaten else 0.0,
    ]
    if len(state) < input_dim:
        state = state + [0.0] * (input_dim - len(state))
    return np.asarray(state[:input_dim], dtype=np.float32)


def task_flags_for(task: str) -> list[float]:
    return [1.0 if name == task else 0.0 for name in TASK_NAMES]


def infer_stage(
    task: str,
    step: int,
    grasped: bool,
    eaten: bool,
    berry_attached: bool,
    demo: ArticulatedFireboyDemo,
) -> str:
    if task == "run_around":
        return "run_loop"
    if task == "go_to_point":
        return "walk_to"
    if eaten:
        return "mouth"
    if step < 38:
        return "approach"
    if step < 80:
        return "reach_above"
    if step < 114:
        return "descend"
    if not grasped:
        return "close"
    if task == "pick_up":
        return "lift"
    if step < 184 and demo.berry_pos()[2] < 0.48:
        return "lift"
    return "mouth"


def save_episode_media(frames: list[np.ndarray], stem: Path) -> dict[str, str | None]:
    if not frames:
        return {"gif": None, "mp4": None}
    stem.parent.mkdir(parents=True, exist_ok=True)
    gif_path = stem.with_suffix(".gif")
    mp4_path = stem.with_suffix(".mp4")
    imageio.mimsave(gif_path, frames, duration=0.05)
    try:
        imageio.mimsave(mp4_path, frames, fps=20)
        mp4 = str(mp4_path)
    except Exception:
        mp4 = None
    return {"gif": str(gif_path), "mp4": mp4}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--task", choices=TASK_NAMES, default="go_eat_berry")
    parser.add_argument("--num-episodes", type=int, default=5)
    parser.add_argument("--seed", type=int, default=9000)
    parser.add_argument("--smooth-alpha", type=float, default=0.20)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    result = eval_articulated_policy(
        checkpoint=args.checkpoint,
        task=args.task,
        num_episodes=args.num_episodes,
        seed=args.seed,
        smooth_alpha=args.smooth_alpha,
        render=args.render,
        out_dir=args.out_dir,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
