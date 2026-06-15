from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SKILL_NAMES = ["walk_to", "run_around", "pick_up", "find_and_eat_berry"]
TASK_TO_SKILL = {
    "go_to_point": "walk_to",
    "run_around": "run_around",
    "pick_up": "pick_up",
    "go_eat_berry": "find_and_eat_berry",
}
PARAM_NAMES = [
    "target_x",
    "target_y",
    "target_z",
    "radius",
    "speed_hint",
    "object_is_berry",
]


def build_skill_param_manifest(
    manifests: list[Path],
    out_path: Path,
    *,
    require_images: bool = True,
    limit_rows: int | None = None,
) -> dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    skipped = 0
    tasks: dict[str, int] = {}
    skills: dict[str, int] = {}
    sources: dict[str, int] = {}

    with out_path.open("w", encoding="utf-8") as out:
        for manifest in manifests:
            with manifest.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    raw = json.loads(line)
                    row = skill_param_row(raw)
                    image_path = row.get("image_path")
                    if require_images and (not image_path or not Path(str(image_path)).exists()):
                        skipped += 1
                        continue
                    task = str(row["task"])
                    skill = str(row["skill"])
                    tasks[task] = tasks.get(task, 0) + 1
                    skills[skill] = skills.get(skill, 0) + 1
                    sources[str(manifest)] = sources.get(str(manifest), 0) + 1
                    out.write(json.dumps(row, ensure_ascii=True) + "\n")
                    rows_written += 1
                    if limit_rows is not None and rows_written >= limit_rows:
                        break
            if limit_rows is not None and rows_written >= limit_rows:
                break

    summary = {
        "out_path": str(out_path),
        "rows_written": rows_written,
        "skipped": skipped,
        "require_images": require_images,
        "limit_rows": limit_rows,
        "skill_names": SKILL_NAMES,
        "param_names": PARAM_NAMES,
        "tasks": tasks,
        "skills": skills,
        "sources": sources,
        "action_type": "skill_parameters_v1",
    }
    summary_path = out_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def skill_param_row(raw: dict[str, Any]) -> dict[str, Any]:
    task = str(raw.get("task") or "unknown")
    skill = TASK_TO_SKILL.get(task, "walk_to")
    robot_state = raw.get("robot_state") if isinstance(raw.get("robot_state"), dict) else {}
    ball_pos = list(robot_state.get("ball_pos") or [0.0, 0.0, 0.0])
    target_x = float(ball_pos[0]) if len(ball_pos) > 0 else 0.0
    target_y = float(ball_pos[1]) if len(ball_pos) > 1 else 0.0
    target_z = float(ball_pos[2]) if len(ball_pos) > 2 else 0.0
    radius = 0.55 if skill == "run_around" else 0.0
    speed_hint = 1.0 if skill == "run_around" else 0.55 if skill == "walk_to" else 0.25
    object_is_berry = 1.0 if task in {"pick_up", "go_eat_berry", "go_to_point"} else 0.0
    params = [target_x, target_y, target_z, radius, speed_hint, object_is_berry]

    return {
        "source_action_type": raw.get("action_type"),
        "source_episode_file": raw.get("episode_file"),
        "episode_id": raw.get("episode_id"),
        "step": raw.get("step"),
        "task": task,
        "stage": raw.get("stage"),
        "instruction": raw.get("instruction") or task.replace("_", " "),
        "image_path": raw.get("image_path"),
        "robot_state": robot_state,
        "action_type": "skill_parameters_v1",
        "skill": skill,
        "skill_id": SKILL_NAMES.index(skill),
        "skill_names": SKILL_NAMES,
        "param_names": PARAM_NAMES,
        "target_params": params,
        "target": {
            "target_xy": [target_x, target_y],
            "target_z": target_z,
            "radius": radius,
            "speed_hint": speed_hint,
            "object_is_berry": bool(object_is_berry),
        },
        "dispatch": {
            "walk_to": "registry:walk_to",
            "run_around": "registry:run_around",
            "pick_up": "registry:pick_up",
            "find_and_eat_berry": "registry:find_and_eat_berry",
        }[skill],
        "success_so_far": bool(raw.get("success_so_far", False)),
        "grasped": bool(raw.get("grasped", False)),
        "eaten": bool(raw.get("eaten", False)),
    }


def parse_manifest_args(values: list[Path]) -> list[Path]:
    paths = [Path(value) for value in values]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing manifest(s): {missing}")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-missing-images", action="store_true")
    parser.add_argument("--limit-rows", type=int)
    args = parser.parse_args()
    result = build_skill_param_manifest(
        parse_manifest_args(args.manifest),
        args.out,
        require_images=not args.allow_missing_images,
        limit_rows=args.limit_rows,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
