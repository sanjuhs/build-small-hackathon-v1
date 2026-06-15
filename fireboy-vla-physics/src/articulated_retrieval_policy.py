from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np

from eval_articulated_policy import EAT_DISTANCE, infer_stage
from generate_articulated_dataset import ActionCoder, STAGE_NAMES, TASK_NAMES
from render_articulated_fireboy import ArticulatedFireboyDemo


DEFAULT_DATASET = Path("fireboy-vla-physics/build/datasets/fireboy_articulated_go_eat_berry_retrieval")
DEFAULT_POLICY = Path("fireboy-vla-physics/checkpoints/fireboy_articulated_go_eat_berry_retrieval/retrieval_policy.npz")
DEFAULT_OUT_DIR = Path("fireboy-vla-physics/build/articulated_policy_retrieval")
STAGE_START = {
    "approach": 0,
    "reach_above": 38,
    "descend": 80,
    "close": 114,
    "lift": 142,
    "mouth": 184,
    "run_loop": 0,
}
STAGE_END = {
    "approach": 38,
    "reach_above": 80,
    "descend": 114,
    "close": 142,
    "lift": 184,
    "mouth": 242,
    "run_loop": 160,
}


def train_retrieval_policy(
    dataset_dir: Path,
    out_path: Path,
    task: str = "go_eat_berry",
    max_rows: int | None = None,
) -> dict[str, Any]:
    features = []
    actions = []
    stage_ids = []
    rows_seen = 0
    for path in sorted((dataset_dir / "episodes").glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = json.loads(line)
                if raw.get("task") != task:
                    continue
                stage = str(raw.get("stage", "approach"))
                features.append(feature_from_row(raw, stage))
                actions.append(np.asarray(raw["action"], dtype=np.float32))
                stage_ids.append(STAGE_NAMES.index(stage))
                rows_seen += 1
                if max_rows and rows_seen >= max_rows:
                    break
        if max_rows and rows_seen >= max_rows:
            break
    if not features:
        raise RuntimeError(f"No {task} rows found under {dataset_dir}")

    x = np.asarray(features, dtype=np.float32)
    y = np.asarray(actions, dtype=np.float32)
    stages = np.asarray(stage_ids, dtype=np.int16)
    mean = x.mean(axis=0)
    std = x.std(axis=0) + 1e-6
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        out_path,
        features=x,
        actions=y,
        stage_ids=stages,
        feature_mean=mean.astype(np.float32),
        feature_std=std.astype(np.float32),
        task=np.asarray(task),
        stage_names=np.asarray(STAGE_NAMES),
        policy_type=np.asarray("stage_knn_retrieval"),
    )
    return {
        "dataset_dir": str(dataset_dir),
        "out_path": str(out_path),
        "task": task,
        "rows": int(x.shape[0]),
        "feature_dim": int(x.shape[1]),
        "action_dim": int(y.shape[1]),
        "stage_counts": {name: int((stages == index).sum()) for index, name in enumerate(STAGE_NAMES)},
    }


def rollout_retrieval_policy(
    policy_path: Path,
    task: str = "go_eat_berry",
    out_dir: Path = DEFAULT_OUT_DIR,
    seed: int = 12100,
    k: int = 12,
    smooth_alpha: float = 0.10,
    render: bool = True,
) -> dict[str, Any]:
    policy = {key: value for key, value in np.load(policy_path).items()}
    demo = ArticulatedFireboyDemo(camera="front_cam", render_enabled=render)
    coder = ActionCoder(demo)
    rng = np.random.default_rng(seed)
    frames: list[np.ndarray] = []
    try:
        pose = demo.reset()
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
        success = False
        for step in range(242):
            stage = infer_stage(task, step, grasped, eaten, berry_attached, demo)
            query = feature_from_demo(demo, stage, step)
            action = retrieval_action(policy, stage, query, k=k)
            action = np.clip(smooth_alpha * previous_action + (1.0 - smooth_alpha) * action, -1.0, 1.0)
            target_pose = coder.action_to_pose(action)
            closing = target_pose.get("finger_R_a", 0.060) < 0.032 and target_pose.get("finger_R_b", 0.060) < 0.032
            demo.set_right_gripper_collision(closing)
            demo.step(target_pose, 4)

            hand = demo.site_pos("right_hand")
            berry_pos = demo.berry_pos()
            if closing and not berry_attached and np.linalg.norm(hand - berry_pos) < 0.14:
                grasped = True
                berry_attached = True
                attach_offset = berry_pos - hand
                attach_offset[2] = np.clip(attach_offset[2], -0.018, 0.026)
            if berry_attached:
                berry_target = hand + attach_offset
                berry_target[2] = max(berry_target[2], 0.29)
                demo.set_berry(berry_target)
            min_mouth_dist = min(min_mouth_dist, float(np.linalg.norm(demo.berry_pos() - demo.site_pos("mouth"))))
            if min_mouth_dist < EAT_DISTANCE:
                eaten = True
            success = bool(eaten)
            previous_action = action.astype(np.float32, copy=True)
            if render and step % 2 == 0:
                frames.append(demo.render())
            if success and step > 40:
                break

        media = save_media(frames, out_dir / "faithful_retrieval_go_eat_berry") if render else {}
        return {
            "policy_path": str(policy_path),
            "task": task,
            "success": success,
            "grasped": grasped,
            "eaten": eaten,
            "final_berry_pos": demo.berry_pos().round(4).tolist(),
            "min_mouth_dist": round(min_mouth_dist, 4) if math.isfinite(min_mouth_dist) else None,
            "gif_path": media.get("gif"),
            "mp4_path": media.get("mp4"),
        }
    finally:
        demo.close()


def evaluate_retrieval_policy(
    policy_path: Path,
    num_episodes: int = 30,
    seed: int = 12100,
    k: int = 12,
    smooth_alpha: float = 0.10,
) -> dict[str, Any]:
    successes = 0
    reports = []
    for episode in range(num_episodes):
        report = rollout_retrieval_policy(
            policy_path,
            seed=seed + episode,
            k=k,
            smooth_alpha=smooth_alpha,
            render=False,
        )
        successes += int(report["success"])
        reports.append(report)
    return {
        "policy_path": str(policy_path),
        "episodes": num_episodes,
        "successes": successes,
        "success_rate": successes / max(1, num_episodes),
        "k": k,
        "smooth_alpha": smooth_alpha,
        "reports": reports,
    }


def feature_from_row(raw: dict[str, Any], stage: str) -> np.ndarray:
    return make_feature(
        stage=stage,
        step=int(raw.get("step", 0)),
        right_hand=np.asarray(raw.get("right_hand_pos", [0.0, 0.0, 0.0]), dtype=np.float32),
        left_hand=np.asarray(raw.get("left_hand_pos", [0.0, 0.0, 0.0]), dtype=np.float32),
        berry=np.asarray(raw.get("ball_pos", [0.0, 0.0, 0.0]), dtype=np.float32),
        mouth=np.asarray(raw.get("mouth_pos", [0.0, 0.0, 0.0]), dtype=np.float32),
    )


def feature_from_demo(demo: ArticulatedFireboyDemo, stage: str, step: int) -> np.ndarray:
    return make_feature(
        stage=stage,
        step=step,
        right_hand=demo.site_pos("right_hand"),
        left_hand=demo.site_pos("left_hand"),
        berry=demo.berry_pos(),
        mouth=demo.site_pos("mouth"),
    )


def make_feature(
    stage: str,
    step: int,
    right_hand: np.ndarray,
    left_hand: np.ndarray,
    berry: np.ndarray,
    mouth: np.ndarray,
) -> np.ndarray:
    start = STAGE_START.get(stage, 0)
    end = max(STAGE_END.get(stage, start + 1), start + 1)
    stage_progress = np.clip((step - start) / (end - start), 0.0, 1.0)
    berry = np.asarray(berry, dtype=np.float32)
    mouth = np.asarray(mouth, dtype=np.float32)
    right_hand = np.asarray(right_hand, dtype=np.float32)
    left_hand = np.asarray(left_hand, dtype=np.float32)
    return np.concatenate(
        [
            np.asarray([step / 250.0, stage_progress], dtype=np.float32),
            right_hand,
            left_hand,
            berry,
            mouth,
            berry - right_hand,
            mouth - berry,
            mouth - right_hand,
        ]
    ).astype(np.float32)


def retrieval_action(policy: dict[str, np.ndarray], stage: str, query: np.ndarray, k: int) -> np.ndarray:
    stage_id = STAGE_NAMES.index(stage)
    mask = policy["stage_ids"] == stage_id
    if not np.any(mask):
        mask = np.ones_like(policy["stage_ids"], dtype=bool)
    features = policy["features"][mask]
    actions = policy["actions"][mask]
    mean = policy["feature_mean"]
    std = policy["feature_std"]
    normalized_features = (features - mean) / std
    normalized_query = (query.astype(np.float32) - mean) / std
    dists = np.einsum("ij,ij->i", normalized_features - normalized_query, normalized_features - normalized_query)
    count = min(k, len(dists))
    nearest = np.argpartition(dists, count - 1)[:count]
    weights = 1.0 / (dists[nearest] + 1e-4)
    weights = weights / weights.sum()
    return np.clip(weights @ actions[nearest], -1.0, 1.0).astype(np.float32)


def save_media(frames: list[np.ndarray], stem: Path) -> dict[str, str | None]:
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
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    train_parser.add_argument("--out", type=Path, default=DEFAULT_POLICY)
    train_parser.add_argument("--task", choices=TASK_NAMES, default="go_eat_berry")
    train_parser.add_argument("--max-rows", type=int)

    eval_parser = subparsers.add_parser("eval")
    eval_parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    eval_parser.add_argument("--num-episodes", type=int, default=30)
    eval_parser.add_argument("--seed", type=int, default=12100)
    eval_parser.add_argument("--k", type=int, default=12)
    eval_parser.add_argument("--smooth-alpha", type=float, default=0.10)

    rollout_parser = subparsers.add_parser("rollout")
    rollout_parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    rollout_parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    rollout_parser.add_argument("--seed", type=int, default=12100)
    rollout_parser.add_argument("--k", type=int, default=12)
    rollout_parser.add_argument("--smooth-alpha", type=float, default=0.10)
    rollout_parser.add_argument("--no-render", action="store_true")

    args = parser.parse_args()
    if args.command == "train":
        result = train_retrieval_policy(args.dataset_dir, args.out, args.task, args.max_rows)
    elif args.command == "eval":
        result = evaluate_retrieval_policy(args.policy, args.num_episodes, args.seed, args.k, args.smooth_alpha)
    else:
        result = rollout_retrieval_policy(
            args.policy,
            out_dir=args.out_dir,
            seed=args.seed,
            k=args.k,
            smooth_alpha=args.smooth_alpha,
            render=not args.no_render,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
