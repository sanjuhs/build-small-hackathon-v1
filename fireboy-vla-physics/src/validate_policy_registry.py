from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from policy_registry import DEFAULT_REGISTRY_PATH, load_policy_registry, resolve_repo_path


PATH_KEYS = [
    "policy_path",
    "checkpoint_path",
    "local_checkpoint_path",
    "seed_checkpoint_path",
    "adapter_path",
    "eval_path",
    "train_path",
    "manifest_path",
    "manifest_summary_path",
    "local_manifest_path",
    "local_manifest_summary_path",
    "proof_mp4",
    "proof_gif",
    "local_demo_mp4",
    "local_fallback_policy_path",
    "report_path",
    "artifact_archive",
]


def validate_policy_registry(path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    registry = load_policy_registry(path)
    missing: list[dict[str, str]] = []
    checked = 0

    fireboy_glb = registry.get("fireboy_glb")
    if fireboy_glb:
        checked += 1
        resolved = resolve_repo_path(fireboy_glb)
        if resolved is None or not resolved.exists():
            missing.append({"section": "registry", "entry": "fireboy_glb", "key": "fireboy_glb", "path": str(fireboy_glb)})

    for section_name in ("body_proofs", "skills", "vla_models", "failed_experiments"):
        section = registry.get(section_name, {})
        if not isinstance(section, dict):
            missing.append({"section": section_name, "key": "<section>", "path": "not a mapping"})
            continue
        for entry_name, entry in section.items():
            if not isinstance(entry, dict) or entry.get("alias_of"):
                continue
            for key in PATH_KEYS:
                value = entry.get(key)
                if not value:
                    continue
                checked += 1
                resolved = resolve_repo_path(value)
                if resolved is None or not resolved.exists():
                    missing.append({"section": section_name, "entry": entry_name, "key": key, "path": str(value)})

    return {
        "registry": str(path),
        "checked_paths": checked,
        "missing_count": len(missing),
        "missing": missing,
        "ok": not missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    args = parser.parse_args()
    result = validate_policy_registry(args.registry)
    print(json.dumps(result, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
