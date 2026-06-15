from __future__ import annotations

import argparse
import json
from pathlib import Path

from pet_skills import PetSkillController
from rollout_numpy_policy import DEFAULT_POLICY_PATH, rollout


DEFAULT_OUT_DIR = Path("fireboy-vla-physics/build/submission")


def run_submission_check(
    policy: Path = DEFAULT_POLICY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    seed: int = 5000,
    smooth_alpha: float = 0.25,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    controller = PetSkillController()
    commands = [
        "walk around",
        "run around",
        "walk to me",
        "wave",
        "sit",
        "dance",
        "go find berry and eat it",
    ]
    routed = []
    for command in commands:
        result = controller.execute_text(command)
        routed.append(
            {
                "command": command,
                "skill": result.skill,
                "lane": result.lane,
                "success": result.success,
                "path_points": len(result.path),
            }
        )

    learned = rollout(
        policy_path=policy,
        out_gif=out_dir / "learned_berry_eat.gif",
        task="eat_berry",
        seed=seed,
        smooth_alpha=smooth_alpha,
        render=True,
    )
    success = all(item["success"] for item in routed) and learned["success"] and learned["eaten"]
    return {
        "success": bool(success),
        "policy": str(policy),
        "gif": learned["gif_path"],
        "smooth_alpha": smooth_alpha,
        "routed_commands": routed,
        "learned_berry_eat": learned,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed", type=int, default=5000)
    parser.add_argument("--smooth-alpha", type=float, default=0.25)
    args = parser.parse_args()
    result = run_submission_check(args.policy, args.out_dir, args.seed, args.smooth_alpha)
    print(json.dumps(result, indent=2))
    if not result["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
