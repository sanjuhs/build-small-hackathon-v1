from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "fireboy-vla-physics" / "policy_registry.json"


def load_policy_registry(path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def skill_entry(skill: str, registry: dict[str, Any] | None = None) -> dict[str, Any] | None:
    registry = registry or load_policy_registry()
    skills = registry.get("skills", {})
    entry = skills.get(skill)
    if not isinstance(entry, dict):
        return None
    alias = entry.get("alias_of")
    if alias:
        return skill_entry(str(alias), registry)
    return entry


def resolve_repo_path(path_value: str | Path | None) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path
