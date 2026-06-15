from __future__ import annotations

import argparse
import json
from pathlib import Path

from pet_skills import PetSkillController
from policy_registry import resolve_repo_path, skill_entry
from rollout_articulated_numpy_policy import rollout as rollout_articulated
from rollout_numpy_policy import DEFAULT_POLICY_PATH, rollout as rollout_berry


ARTICULATED_POLICY_FALLBACKS = {
    "pick_up": Path("Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_pick_up/faithful_articulated_policy.npz"),
    "find_and_eat_berry": Path("Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_go_eat_berry/faithful_articulated_policy.npz"),
}


def run_pet_command(
    command: str,
    policy: Path = DEFAULT_POLICY_PATH,
    out_dir: Path = Path("fireboy-vla-physics/build/pet_runtime"),
    seed: int = 5000,
    smooth_alpha: float = 0.25,
    render: bool = True,
) -> dict:
    controller = PetSkillController()
    skill, params = controller.route_text(command)
    routed = controller.execute(skill, **params)

    result = {
        "command": command,
        "skill": routed.skill,
        "lane": routed.lane,
        "success": routed.success,
        "path": routed.path,
        "details": routed.details,
    }

    articulated_task = articulated_task_for_skill(routed.skill)
    if articulated_task:
        entry = required_skill_entry(routed.skill)
        policy_path = articulated_policy_path(routed.skill, entry)
        result["articulated_policy_rollout"] = rollout_articulated(
            policy_path=policy_path,
            task=articulated_task,
            out_dir=out_dir / "articulated",
            seed=seed,
            smooth_alpha=smooth_alpha,
            render=render,
        )
        result["lane"] = "mujoco_articulated_policy"
        result["policy_path"] = str(policy_path)
        result["policy_registry_entry"] = compact_registry_entry(entry)
        result["success"] = bool(result["articulated_policy_rollout"]["success"])

    elif routed.skill == "find_and_eat_berry":
        entry = skill_entry(routed.skill) or {}
        fallback_policy = resolve_repo_path(entry.get("local_fallback_policy_path")) or policy
        out_dir.mkdir(parents=True, exist_ok=True)
        result["policy_rollout"] = rollout_berry(
            policy_path=fallback_policy,
            out_gif=out_dir / "learned_berry_eat.gif",
            task="eat_berry",
            seed=seed,
            smooth_alpha=smooth_alpha,
            render=render,
        )
        result["policy_path"] = str(fallback_policy)
        if entry:
            result["policy_registry_entry"] = compact_registry_entry(entry)
        result["success"] = bool(result["policy_rollout"]["success"] and result["policy_rollout"]["eaten"])

    elif routed.skill == "pick_up":
        entry = skill_entry(routed.skill) or {}
        out_dir.mkdir(parents=True, exist_ok=True)
        result["policy_rollout"] = rollout_berry(
            policy_path=policy,
            out_gif=out_dir / "learned_pick_up.gif",
            task="pick_ball",
            seed=seed,
            smooth_alpha=smooth_alpha,
            render=render,
        )
        result["policy_path"] = str(policy)
        if entry:
            result["policy_registry_entry"] = compact_registry_entry(entry)
        result["success"] = bool(result["policy_rollout"]["success"] and result["policy_rollout"]["grasped"])

    return result


def articulated_task_for_skill(skill: str) -> str | None:
    if skill in {"walk_to", "run_to"}:
        return "go_to_point"
    if skill in {"walk_around", "run_around"}:
        return "run_around"
    return None


def required_skill_entry(skill: str) -> dict:
    entry = skill_entry(skill)
    if not entry:
        raise KeyError(f"No policy registry entry for skill: {skill}")
    return entry


def required_registry_path(entry: dict, key: str) -> Path:
    path = resolve_repo_path(entry.get(key))
    if path is None or not path.exists():
        raise FileNotFoundError(f"Registry path for {key} does not exist: {entry.get(key)}")
    return path


def articulated_policy_path(skill: str, entry: dict) -> Path:
    registry_path = resolve_repo_path(entry.get("policy_path"))
    if registry_path and registry_path.exists():
        return registry_path
    fallback = resolve_repo_path(ARTICULATED_POLICY_FALLBACKS.get(skill))
    if fallback and fallback.exists():
        return fallback
    raise FileNotFoundError(f"No articulated policy checkpoint exists for skill: {skill}")


def compact_registry_entry(entry: dict) -> dict:
    keep = [
        "task",
        "lane",
        "runtime",
        "policy_path",
        "checkpoint_path",
        "adapter_path",
        "eval_path",
        "proof_mp4",
        "successes",
        "episodes",
        "success_rate",
        "status",
    ]
    return {key: entry[key] for key in keep if key in entry}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--out-dir", type=Path, default=Path("fireboy-vla-physics/build/pet_runtime"))
    parser.add_argument("--seed", type=int, default=5000)
    parser.add_argument("--smooth-alpha", type=float, default=0.25)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    result = run_pet_command(
        command=args.command,
        policy=args.policy,
        out_dir=args.out_dir,
        seed=args.seed,
        smooth_alpha=args.smooth_alpha,
        render=not args.no_render,
    )
    print(json.dumps(result, indent=2))
    if not result["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
