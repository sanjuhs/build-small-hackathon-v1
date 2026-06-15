from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STATE_KEYS = [
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
]


def build_manifest(
    dataset_dir: Path,
    out_path: Path,
    chunk_steps: int = 10,
    stride: int = 1,
    require_images: bool = True,
) -> dict[str, Any]:
    episode_paths = sorted((dataset_dir / "episodes").glob("*.jsonl"))
    if not episode_paths:
        raise RuntimeError(f"No episode JSONL files found under {dataset_dir / 'episodes'}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    skipped_no_image = 0
    tasks: dict[str, int] = {}
    with out_path.open("w", encoding="utf-8") as out:
        for episode_path in episode_paths:
            rows = load_episode(episode_path)
            for index in range(0, len(rows), max(1, stride)):
                row = rows[index]
                image_path = row.get("image_path")
                if require_images and not image_path:
                    skipped_no_image += 1
                    continue
                task = str(row.get("task", "unknown"))
                tasks[task] = tasks.get(task, 0) + 1
                action_chunk = [
                    rows[min(index + offset, len(rows) - 1)]["action"]
                    for offset in range(chunk_steps)
                ]
                manifest_row = {
                    "dataset_dir": str(dataset_dir),
                    "episode_file": str(episode_path.relative_to(dataset_dir)),
                    "episode_id": row.get("episode_id"),
                    "step": row.get("step"),
                    "task": task,
                    "stage": row.get("stage"),
                    "instruction": row.get("instruction"),
                    "image_path": str((dataset_dir / image_path).resolve()) if image_path else None,
                    "robot_state": {key: row.get(key) for key in STATE_KEYS if key in row},
                    "action_type": "normalized_joint_targets",
                    "action_chunk_steps": chunk_steps,
                    "action_chunk": action_chunk,
                    "success_so_far": bool(row.get("success", False)),
                    "grasped": bool(row.get("grasped", False)),
                    "eaten": bool(row.get("eaten", False)),
                }
                out.write(json.dumps(manifest_row, ensure_ascii=True) + "\n")
                rows_written += 1

    return {
        "dataset_dir": str(dataset_dir),
        "out_path": str(out_path),
        "episodes": len(episode_paths),
        "rows_written": rows_written,
        "skipped_no_image": skipped_no_image,
        "chunk_steps": chunk_steps,
        "stride": stride,
        "require_images": require_images,
        "tasks": tasks,
    }


def load_episode(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--chunk-steps", type=int, default=10)
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--allow-missing-images", action="store_true")
    args = parser.parse_args()
    result = build_manifest(
        args.dataset_dir,
        args.out,
        chunk_steps=args.chunk_steps,
        stride=args.stride,
        require_images=not args.allow_missing_images,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
