from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from eval_articulated_policy import EAT_DISTANCE, infer_stage, save_episode_media, state_from_demo
from generate_articulated_dataset import ActionCoder, TASK_INSTRUCTIONS, TASK_NAMES
from render_articulated_fireboy import ArticulatedFireboyDemo
from train_minicpm_vla_action_head import (
    MiniCPMStateActionHead,
    ROOT_X_ACTION_INDEX,
    ROOT_Y_ACTION_INDEX,
    build_minicpm_action_head,
    encode_minicpm_prompt,
    first_model_device,
    load_minicpm,
    make_vla_prompt,
)


DEFAULT_CHECKPOINT = Path("fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_action_head/minicpm_vla_action_head.pt")
DEFAULT_OUT_DIR = Path("fireboy-vla-physics/build/minicpm_vla_policy")


def eval_minicpm_vla_policy(
    checkpoint: Path = DEFAULT_CHECKPOINT,
    task: str = "pick_up",
    num_episodes: int = 1,
    seed: int = 19000,
    replan_interval: int = 10,
    smooth_alpha: float = 0.0,
    render: bool = True,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install torch before evaluating MiniCPM-V VLA policy") from exc

    payload = torch.load(checkpoint, map_location="cpu")
    processor, minicpm = load_minicpm(str(payload["model_id"]))
    adapter_dir = payload.get("lora_adapter_dir")
    if adapter_dir:
        from peft import PeftModel

        adapter_path = Path(str(adapter_dir))
        if not adapter_path.is_absolute():
            adapter_path = checkpoint.parent / adapter_path
        minicpm = PeftModel.from_pretrained(minicpm, str(adapter_path))
    minicpm.eval()
    for param in minicpm.parameters():
        param.requires_grad_(False)

    device = torch.device("cuda" if torch.cuda.is_available() else first_model_device(minicpm))
    head = build_minicpm_action_head(payload)
    head.load_state_dict(payload["head"])
    head.to(device)
    head.eval()

    rng = np.random.default_rng(seed)
    successes = 0
    reports = []
    for episode in range(num_episodes):
        report = rollout_episode(
            processor,
            minicpm,
            head,
            payload,
            task,
            rng,
            replan_interval=replan_interval,
            smooth_alpha=smooth_alpha,
            render=render and episode == 0,
            out_dir=out_dir,
            episode_id=episode,
        )
        successes += int(report["success"])
        reports.append(report)
    return {
        "checkpoint": str(checkpoint),
        "task": task,
        "episodes": num_episodes,
        "successes": successes,
        "success_rate": successes / max(1, num_episodes),
        "replan_interval": replan_interval,
        "smooth_alpha": smooth_alpha,
        "reports": reports,
    }


def rollout_episode(
    processor: Any,
    minicpm: Any,
    head: MiniCPMStateActionHead,
    payload: dict[str, Any],
    task: str,
    rng: np.random.Generator,
    replan_interval: int,
    smooth_alpha: float,
    render: bool,
    out_dir: Path,
    episode_id: int,
) -> dict[str, Any]:
    demo = ArticulatedFireboyDemo(camera="world_cam" if task in {"run_around", "go_to_point"} else "front_cam", render_enabled=True)
    coder = ActionCoder(demo)
    frames: list[np.ndarray] = []
    tmp_dir = out_dir / "tmp_minicpm_frames"
    tmp_dir.mkdir(parents=True, exist_ok=True)
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
        instruction = TASK_INSTRUCTIONS.get(task, [task])[0]

        for step in range(max_steps):
            stage = infer_stage(task, step, grasped, eaten, berry_attached, demo)
            should_replan = (
                action_plan is None
                or plan_index >= len(action_plan)
                or (replan_interval > 0 and step % replan_interval == 0)
            )
            if should_replan:
                frame_path = tmp_dir / f"{task}_ep{episode_id:03d}_step{step:04d}.jpg"
                Image.fromarray(demo.render()).save(frame_path, quality=88)
                state = state_from_demo(
                    demo,
                    previous_action,
                    task,
                    step,
                    grasped,
                    eaten,
                    int(payload["state_dim"]),
                    include_stage_flags=bool(payload.get("include_stage_flags", True)),
                    stage=stage,
                    state_mode=str(payload.get("state_mode", "clock")),
                )
                flat_plan = predict_action_chunk(
                    processor,
                    minicpm,
                    head,
                    payload,
                    frame_path,
                    instruction,
                    state,
                )
                action_plan = flat_plan.reshape(int(payload["chunk_steps"]), int(payload["action_dim"]))
                plan_index = 0

            action = action_plan[plan_index]
            plan_index += 1
            action = decode_action_target(action, previous_action, coder, payload)
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

        media = save_episode_media(frames, out_dir / f"minicpm_vla_{task}_policy_ep{episode_id:03d}") if render else {}
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


def predict_action_chunk(
    processor: Any,
    minicpm: Any,
    head: MiniCPMStateActionHead,
    payload: dict[str, Any],
    image_path: Path,
    instruction: str,
    state: np.ndarray,
) -> np.ndarray:
    import torch

    vl = encode_minicpm_prompt(
        processor,
        minicpm,
        image_path,
        instruction,
        downsample_mode=str(payload.get("downsample_mode", "16x")),
        max_slice_nums=int(payload.get("max_slice_nums", 9)),
    )
    vl_norm = (vl - np.asarray(payload["vl_mean"], dtype=np.float32)) / np.asarray(payload["vl_std"], dtype=np.float32)
    state_norm = (state - np.asarray(payload["state_mean"], dtype=np.float32)) / np.asarray(payload["state_std"], dtype=np.float32)
    x = np.concatenate([vl_norm, state_norm]).astype(np.float32)
    device = next(head.model.parameters()).device
    with torch.no_grad():
        pred = head(torch.tensor(x, dtype=torch.float32, device=device).unsqueeze(0)).squeeze(0).cpu().numpy()
    action = pred * np.asarray(payload["action_std"], dtype=np.float32) + np.asarray(payload["action_mean"], dtype=np.float32)
    return np.clip(action, -1.0, 1.0).astype(np.float32)


def decode_action_target(
    action: np.ndarray,
    previous_action: np.ndarray,
    coder: ActionCoder,
    payload: dict[str, Any],
) -> np.ndarray:
    mode = str(payload.get("action_target_mode", "absolute_joint_targets"))
    decoded = np.asarray(action, dtype=np.float32).copy()
    if mode == "absolute_joint_targets":
        return np.clip(decoded, -1.0, 1.0).astype(np.float32)
    if mode != "root_velocity_v1":
        raise ValueError(f"Unknown action target mode: {mode}")

    previous = np.asarray(previous_action, dtype=np.float32)
    max_step_m = max(float(payload.get("root_velocity_max_step_m", 0.035)), 1e-6)
    root_x_step = max_step_m / float(coder.half_ranges[ROOT_X_ACTION_INDEX])
    root_y_step = max_step_m / float(coder.half_ranges[ROOT_Y_ACTION_INDEX])
    decoded[ROOT_X_ACTION_INDEX] = previous[ROOT_X_ACTION_INDEX] + np.clip(decoded[ROOT_X_ACTION_INDEX], -1.0, 1.0) * root_x_step
    decoded[ROOT_Y_ACTION_INDEX] = previous[ROOT_Y_ACTION_INDEX] + np.clip(decoded[ROOT_Y_ACTION_INDEX], -1.0, 1.0) * root_y_step
    return np.clip(decoded, -1.0, 1.0).astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--task", choices=TASK_NAMES, default="pick_up")
    parser.add_argument("--num-episodes", type=int, default=1)
    parser.add_argument("--seed", type=int, default=19000)
    parser.add_argument("--replan-interval", type=int, default=10)
    parser.add_argument("--smooth-alpha", type=float, default=0.0)
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    result = eval_minicpm_vla_policy(
        checkpoint=args.checkpoint,
        task=args.task,
        num_episodes=args.num_episodes,
        seed=args.seed,
        replan_interval=args.replan_interval,
        smooth_alpha=args.smooth_alpha,
        render=not args.no_render,
        out_dir=args.out_dir,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
