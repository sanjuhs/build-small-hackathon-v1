from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from dataset import EpisodeWriter
from fireboy_articulated_mjcf import ACTUATED_JOINTS
from render_articulated_fireboy import ArticulatedFireboyDemo, add_walk_cycle, deg, smoothstep


TASK_NAMES = ["pick_up", "go_eat_berry", "run_around", "go_to_point"]
STAGE_NAMES = ["approach", "reach_above", "descend", "close", "lift", "mouth", "run_loop", "walk_to"]
EAT_DISTANCE = 0.14
TASK_INSTRUCTIONS = {
    "pick_up": [
        "pick up the berry",
        "grab the berry",
        "go to the berry and lift it",
    ],
    "go_eat_berry": [
        "go find the berry and eat it",
        "pick up the berry and bring it to your mouth",
        "eat the berry",
    ],
    "run_around": [
        "run around",
        "walk around quickly",
        "circle around the room",
    ],
    "go_to_point": [
        "walk to the target",
        "go to that point",
        "move over to the yellow marker",
    ],
}


class ActionCoder:
    def __init__(self, demo: ArticulatedFireboyDemo):
        lows = []
        highs = []
        for name in ACTUATED_JOINTS:
            low, high = demo.joint_range(name)
            lows.append(low)
            highs.append(high)
        self.lows = np.asarray(lows, dtype=np.float32)
        self.highs = np.asarray(highs, dtype=np.float32)
        self.centers = (self.highs + self.lows) * 0.5
        self.half_ranges = np.maximum((self.highs - self.lows) * 0.5, 1e-6)

    def pose_to_action(self, pose: dict[str, float]) -> np.ndarray:
        values = np.asarray([pose[name] for name in ACTUATED_JOINTS], dtype=np.float32)
        return np.clip((values - self.centers) / self.half_ranges, -1.0, 1.0)

    def action_to_pose(self, action: np.ndarray) -> dict[str, float]:
        values = self.centers + np.clip(np.asarray(action, dtype=np.float32), -1.0, 1.0) * self.half_ranges
        return {name: float(value) for name, value in zip(ACTUATED_JOINTS, values)}


def generate_articulated_dataset(
    num_episodes: int,
    out_dir: Path,
    seed: int = 1,
    task: str = "all",
    save_images: bool = False,
    image_stride: int = 1,
    go_to_point_recovery: bool = False,
) -> dict[str, Any]:
    tasks = parse_tasks(task)
    writer = EpisodeWriter(
        out_dir,
        task=f"fireboy_articulated_{task}",
        save_images=save_images,
        language_templates=[template for name in tasks for template in TASK_INSTRUCTIONS[name]],
        image_stride=image_stride,
        state_keys=[
            "qpos",
            "qvel",
            "ctrl",
            "previous_action",
            "right_hand_pos",
            "left_hand_pos",
            "mouth_pos",
            "ball_pos",
            "task_flags",
            "stage_flags",
        ],
    )
    rng = np.random.default_rng(seed)
    demo = ArticulatedFireboyDemo(render_enabled=save_images)
    coder = ActionCoder(demo)
    successes = {name: 0 for name in tasks}
    written = 0
    try:
        for episode in range(num_episodes):
            for task_name in tasks:
                if task_name == "run_around":
                    rows, success = run_around_episode(demo, coder, rng, written, task_name, save_images)
                elif task_name == "go_to_point":
                    if go_to_point_recovery:
                        rows, success = go_to_point_recovery_episode(demo, coder, rng, written, task_name, save_images)
                    else:
                        rows, success = go_to_point_episode(demo, coder, rng, written, task_name, save_images)
                else:
                    rows, success = pick_episode(
                        demo,
                        coder,
                        rng,
                        written,
                        task_name,
                        eat=task_name == "go_eat_berry",
                        save_images=save_images,
                    )
                writer.write_episode(written, rows)
                successes[task_name] += int(success)
                written += 1
    finally:
        demo.close()
    return {
        "episodes": written,
        "episodes_per_task": num_episodes,
        "tasks": tasks,
        "successes": successes,
        "success_rate": {name: successes[name] / max(1, num_episodes) for name in tasks},
        "out_dir": str(out_dir),
        "action_dim": len(ACTUATED_JOINTS),
        "action_joints": list(ACTUATED_JOINTS),
        "save_images": save_images,
        "image_stride": image_stride if save_images else None,
        "go_to_point_recovery": bool(go_to_point_recovery),
    }


def pick_episode(
    demo: ArticulatedFireboyDemo,
    coder: ActionCoder,
    rng: np.random.Generator,
    episode_id: int,
    task: str,
    eat: bool,
    save_images: bool,
) -> tuple[list[dict[str, Any]], bool]:
    pose = demo.reset()
    demo.set_camera("front_cam")
    demo.set_right_gripper_collision(False)
    berry = np.array(
        [
            0.40 + rng.uniform(-0.030, 0.030),
            -0.10 + rng.uniform(-0.035, 0.035),
            0.295,
        ],
        dtype=np.float64,
    )
    demo.set_berry(berry)
    instruction = choose_instruction(task, episode_id)
    rows: list[dict[str, Any]] = []
    previous_action = coder.pose_to_action(pose)
    grasped = False
    eaten = False
    berry_attached = False
    attach_offset = np.zeros(3, dtype=np.float64)
    min_mouth_dist = float("inf")
    step_index = 0

    stages = [
        ("approach", 38, berry + np.array([-0.30, 0.08, -berry[2]], dtype=np.float64)),
        ("reach_above", 42, berry + np.array([0.0, 0.0, 0.125], dtype=np.float64)),
        ("descend", 34, berry + np.array([0.0, 0.0, 0.010], dtype=np.float64)),
        ("close", 28, berry + np.array([0.0, 0.0, 0.010], dtype=np.float64)),
        ("lift", 42, np.array([berry[0] - 0.07, berry[1], 0.555], dtype=np.float64)),
    ]
    if eat:
        stages.append(("mouth", 58, np.zeros(3, dtype=np.float64)))

    current_pose = pose.copy()
    for stage, steps, target in stages:
        start_pose = current_pose.copy()
        if stage == "approach":
            target_pose = start_pose.copy()
            target_pose["root_x"] = float(target[0])
            target_pose["root_y"] = float(target[1])
            target_pose["root_yaw"] = deg(4)
        elif stage == "mouth":
            target_pose = demo.solve_right_hand_to_mouth(start_pose, attach_offset, iterations=80)
        else:
            target_pose = demo.solve_right_hand_ik(start_pose, target)

        if stage in {"reach_above", "descend"}:
            target_pose["finger_R_a"] = 0.056
            target_pose["finger_R_b"] = 0.056
        if stage in {"close", "lift", "mouth"}:
            target_pose["finger_R_a"] = 0.014
            target_pose["finger_R_b"] = 0.014

        demo.set_pose(start_pose)
        for local_step in range(steps):
            alpha = smoothstep(local_step / max(1, steps - 1))
            current_pose = demo.blend_pose(start_pose, target_pose, alpha)
            if stage == "approach":
                add_walk_cycle(current_pose, local_step * 0.35, speed=0.6)

            action = coder.pose_to_action(current_pose)
            observation = observe(demo, save_images)
            demo.set_right_gripper_collision(stage in {"close", "lift", "mouth"})
            demo.step(current_pose, 4)

            hand = demo.site_pos("right_hand")
            berry_pos = demo.berry_pos()
            if stage == "close" and np.linalg.norm(hand - berry_pos) < 0.14:
                grasped = True
                berry_attached = True
                attach_offset = berry_pos - hand
                attach_offset[2] = np.clip(attach_offset[2], -0.018, 0.026)
            if berry_attached:
                berry_target = hand + attach_offset
                berry_target[2] = max(berry_target[2], 0.29)
                demo.set_berry(berry_target)
            if eat and stage == "mouth" and np.linalg.norm(demo.berry_pos() - demo.site_pos("mouth")) < EAT_DISTANCE:
                eaten = True
            min_mouth_dist = min(min_mouth_dist, float(np.linalg.norm(demo.berry_pos() - demo.site_pos("mouth"))))

            success = bool(eaten if eat else (grasped and demo.berry_pos()[2] > 0.36))
            rows.append(
                make_row(
                    observation,
                    episode_id,
                    step_index,
                    task,
                    instruction,
                    previous_action,
                    action,
                    success=success,
                    grasped=grasped,
                    eaten=eaten,
                    stage=stage,
                    min_mouth_dist=min_mouth_dist,
                )
            )
            previous_action = action
            step_index += 1
    final_success = bool(eaten if eat else (grasped and demo.berry_pos()[2] > 0.36))
    return rows, final_success


def run_around_episode(
    demo: ArticulatedFireboyDemo,
    coder: ActionCoder,
    rng: np.random.Generator,
    episode_id: int,
    task: str,
    save_images: bool,
) -> tuple[list[dict[str, Any]], bool]:
    pose = demo.reset()
    demo.set_camera("world_cam")
    instruction = choose_instruction(task, episode_id)
    rows: list[dict[str, Any]] = []
    previous_action = coder.pose_to_action(pose)
    radius = 0.28 + rng.uniform(0.00, 0.08)
    center = np.array([0.04 + rng.uniform(-0.03, 0.03), 0.04 + rng.uniform(-0.03, 0.03)], dtype=np.float64)
    turns = 0.9 + rng.uniform(-0.06, 0.06)
    start_xy = np.array([pose["root_x"], pose["root_y"]], dtype=np.float64)
    current_pose = pose.copy()
    for step_index in range(160):
        phase = step_index * 0.18
        theta = step_index / 159 * math.tau * turns
        current_pose["root_x"] = float(center[0] + radius * math.cos(theta))
        current_pose["root_y"] = float(center[1] + radius * math.sin(theta))
        current_pose["root_yaw"] = theta + math.pi / 2
        current_pose["spine_pitch"] = deg(4 + 2 * math.sin(phase))
        current_pose["chest_yaw"] = deg(8 * math.sin(phase))
        current_pose["hip_R_pitch"] = deg(20 * math.sin(phase))
        current_pose["knee_R"] = deg(22 + 28 * max(0.0, math.sin(phase + math.pi)))
        current_pose["ankle_R"] = deg(-8 * math.sin(phase))
        current_pose["hip_L_pitch"] = deg(20 * math.sin(phase + math.pi))
        current_pose["knee_L"] = deg(22 + 28 * max(0.0, math.sin(phase)))
        current_pose["ankle_L"] = deg(-8 * math.sin(phase + math.pi))
        current_pose["shoulder_R_pitch"] = deg(26 + 14 * math.sin(phase + math.pi))
        current_pose["shoulder_L_pitch"] = deg(26 + 14 * math.sin(phase))
        current_pose["elbow_R"] = deg(36 + 10 * max(0.0, math.sin(phase)))
        current_pose["elbow_L"] = deg(36 + 10 * max(0.0, math.sin(phase + math.pi)))
        action = coder.pose_to_action(current_pose)
        observation = observe(demo, save_images)
        demo.step(current_pose, 3)
        moved = float(np.linalg.norm(np.array([current_pose["root_x"], current_pose["root_y"]]) - start_xy))
        success = moved > 0.20
        rows.append(
            make_row(
                observation,
                episode_id,
                step_index,
                task,
                instruction,
                previous_action,
                action,
                success=success,
                grasped=False,
                eaten=False,
                stage="run_loop",
                min_mouth_dist=None,
            )
        )
        previous_action = action
    return rows, True


def go_to_point_episode(
    demo: ArticulatedFireboyDemo,
    coder: ActionCoder,
    rng: np.random.Generator,
    episode_id: int,
    task: str,
    save_images: bool,
) -> tuple[list[dict[str, Any]], bool]:
    pose = demo.reset()
    demo.set_camera("world_cam")
    instruction = choose_instruction(task, episode_id)
    rows: list[dict[str, Any]] = []
    previous_action = coder.pose_to_action(pose)
    angle = rng.uniform(-0.75, 0.75)
    distance = rng.uniform(0.34, 0.54)
    target_xy = np.array([distance * math.cos(angle), distance * math.sin(angle)], dtype=np.float64)
    target_marker = np.array([target_xy[0], target_xy[1], 0.295], dtype=np.float64)
    demo.set_berry(target_marker)
    start_xy = np.array([pose["root_x"], pose["root_y"]], dtype=np.float64)
    heading = math.atan2(float(target_xy[1] - start_xy[1]), float(target_xy[0] - start_xy[0]))
    current_pose = pose.copy()
    final_dist = float("inf")
    for step_index in range(150):
        alpha = smoothstep(step_index / 149)
        phase = step_index * 0.24
        xy = start_xy + (target_xy - start_xy) * alpha
        current_pose["root_x"] = float(xy[0])
        current_pose["root_y"] = float(xy[1])
        current_pose["root_yaw"] = heading
        current_pose["spine_pitch"] = deg(3 + 1.5 * math.sin(phase))
        current_pose["chest_yaw"] = deg(4 * math.sin(phase))
        add_walk_cycle(current_pose, phase, speed=0.85)
        action = coder.pose_to_action(current_pose)
        observation = observe(demo, save_images)
        demo.step(current_pose, 3)
        root_xy = np.array([current_pose["root_x"], current_pose["root_y"]], dtype=np.float64)
        final_dist = float(np.linalg.norm(root_xy - target_xy))
        success = final_dist < 0.08
        rows.append(
            make_row(
                observation,
                episode_id,
                step_index,
                task,
                instruction,
                previous_action,
                action,
                success=success,
                grasped=False,
                eaten=False,
                stage="walk_to",
                min_mouth_dist=None,
            )
        )
        previous_action = action
    return rows, final_dist < 0.08


def go_to_point_recovery_episode(
    demo: ArticulatedFireboyDemo,
    coder: ActionCoder,
    rng: np.random.Generator,
    episode_id: int,
    task: str,
    save_images: bool,
) -> tuple[list[dict[str, Any]], bool]:
    pose = demo.reset()
    demo.set_camera("world_cam")
    instruction = choose_instruction(task, episode_id)
    angle = rng.uniform(-0.75, 0.75)
    distance = rng.uniform(0.34, 0.58)
    target_xy = np.array([distance * math.cos(angle), distance * math.sin(angle)], dtype=np.float64)
    demo.set_berry(np.array([target_xy[0], target_xy[1], 0.295], dtype=np.float64))

    for _ in range(100):
        start_xy = np.array([rng.uniform(-1.25, 1.25), rng.uniform(-1.85, 1.85)], dtype=np.float64)
        if np.linalg.norm(start_xy - target_xy) > 0.28:
            break
    current_pose = pose.copy()
    current_pose["root_x"] = float(start_xy[0])
    current_pose["root_y"] = float(start_xy[1])
    current_pose["root_yaw"] = math.atan2(float(target_xy[1] - start_xy[1]), float(target_xy[0] - start_xy[0]))
    demo.set_pose(current_pose)
    previous_action = coder.pose_to_action(current_pose)

    rows: list[dict[str, Any]] = []
    final_dist = float("inf")
    max_step_m = 0.035
    for step_index in range(170):
        root_xy = np.array([current_pose["root_x"], current_pose["root_y"]], dtype=np.float64)
        delta = target_xy - root_xy
        dist = float(np.linalg.norm(delta))
        final_dist = dist
        if dist > 1e-6:
            direction = delta / dist
        else:
            direction = np.zeros(2, dtype=np.float64)
        step_m = min(max_step_m, dist)
        next_xy = root_xy + direction * step_m
        heading = math.atan2(float(delta[1]), float(delta[0])) if dist > 1e-6 else current_pose["root_yaw"]
        next_pose = current_pose.copy()
        next_pose["root_x"] = float(next_xy[0])
        next_pose["root_y"] = float(next_xy[1])
        next_pose["root_yaw"] = heading
        phase = step_index * 0.25
        next_pose["spine_pitch"] = deg(3 + 1.5 * math.sin(phase))
        next_pose["chest_yaw"] = deg(4 * math.sin(phase))
        add_walk_cycle(next_pose, phase, speed=0.85)
        action = coder.pose_to_action(next_pose)
        observation = observe(demo, save_images)
        success = dist < 0.08
        rows.append(
            make_row(
                observation,
                episode_id,
                step_index,
                task,
                instruction,
                previous_action,
                action,
                success=success,
                grasped=False,
                eaten=False,
                stage="walk_to",
                min_mouth_dist=None,
            )
        )
        demo.step(next_pose, 3)
        previous_action = action
        current_pose = next_pose
        if success and step_index > 20:
            break
    return rows, final_dist < 0.08


def observe(demo: ArticulatedFireboyDemo, save_image: bool) -> dict[str, Any]:
    return {
        "qpos": np.asarray(demo.data.qpos, dtype=np.float32).copy(),
        "qvel": np.asarray(demo.data.qvel, dtype=np.float32).copy(),
        "ctrl": np.asarray(demo.data.ctrl, dtype=np.float32).copy(),
        "right_hand_pos": demo.site_pos("right_hand").astype(np.float32),
        "left_hand_pos": demo.site_pos("left_hand").astype(np.float32),
        "mouth_pos": demo.site_pos("mouth").astype(np.float32),
        "ball_pos": demo.berry_pos().astype(np.float32),
        "image": demo.render() if save_image else None,
    }


def make_row(
    observation: dict[str, Any],
    episode_id: int,
    step: int,
    task: str,
    instruction: str,
    previous_action: np.ndarray,
    action: np.ndarray,
    success: bool,
    grasped: bool,
    eaten: bool,
    stage: str,
    min_mouth_dist: float | None,
) -> dict[str, Any]:
    task_flags = task_one_hot(task)
    return {
        "episode_id": episode_id,
        "step": step,
        "task": task,
        "task_id": TASK_NAMES.index(task),
        "task_flags": task_flags,
        "stage_flags": stage_one_hot(stage),
        "stage": stage,
        "instruction": instruction,
        "image": observation["image"],
        "qpos": observation["qpos"],
        "qvel": observation["qvel"],
        "ctrl": observation["ctrl"],
        "previous_action": previous_action.astype(np.float32),
        "action": action.astype(np.float32),
        "reward": 1.0 if success else 0.0,
        "success": success,
        "grasped": grasped,
        "eaten": eaten,
        "right_hand_pos": observation["right_hand_pos"],
        "left_hand_pos": observation["left_hand_pos"],
        "mouth_pos": observation["mouth_pos"],
        "ball_pos": observation["ball_pos"],
        "min_mouth_dist": min_mouth_dist,
    }


def choose_instruction(task: str, episode_id: int) -> str:
    templates = TASK_INSTRUCTIONS[task]
    return templates[episode_id % len(templates)]


def task_one_hot(task: str) -> list[float]:
    return [1.0 if name == task else 0.0 for name in TASK_NAMES]


def stage_one_hot(stage: str) -> list[float]:
    return [1.0 if name == stage else 0.0 for name in STAGE_NAMES]


def parse_tasks(task: str) -> list[str]:
    if task == "all":
        return list(TASK_NAMES)
    raw_tasks = [part.strip() for part in task.replace(",", " ").split() if part.strip()]
    if not raw_tasks:
        raise ValueError("At least one task is required")
    unknown = [name for name in raw_tasks if name not in TASK_NAMES]
    if unknown:
        raise ValueError(f"Unknown task(s): {unknown}. Valid tasks: {TASK_NAMES} or all")
    return raw_tasks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-episodes", type=int, default=10, help="Episodes per task.")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--task", default="all", help="Task name, all, or comma/space-separated task list.")
    parser.add_argument("--save-images", action="store_true")
    parser.add_argument("--no-images", action="store_true")
    parser.add_argument("--image-stride", type=int, default=1)
    parser.add_argument("--go-to-point-recovery", action="store_true")
    args = parser.parse_args()
    out_dir = args.out_dir or Path(f"fireboy-vla-physics/build/datasets/fireboy_articulated_{args.task}")
    save_images = bool(args.save_images and not args.no_images)
    result = generate_articulated_dataset(
        args.num_episodes,
        out_dir,
        args.seed,
        args.task,
        save_images=save_images,
        image_stride=args.image_stride,
        go_to_point_recovery=args.go_to_point_recovery,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
