from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from src.pet_profiles import normalize_pet


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MEMORY_PATH = ROOT / "data" / "memories" / "toy-room-v2.jsonl"


def memory_path() -> Path:
    configured = os.getenv("TOYBOX_MEMORY_PATH", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_MEMORY_PATH


def load_memories(pet: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    path = memory_path()
    if not path.exists():
        return []
    wanted_pet = normalize_pet(pet) if pet else None
    memories: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in reversed(lines[-240:]):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        item_pet = normalize_pet(item.get("pet"))
        if wanted_pet and item_pet not in {wanted_pet, "room"}:
            continue
        memories.append(compact_memory(item))
        if len(memories) >= limit:
            break
    return list(reversed(memories))


def clean_new_memory(value: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        concept, meaning = infer_concept(text), text
    elif isinstance(value, dict):
        concept = str(value.get("concept") or value.get("title") or "").strip()
        meaning = str(value.get("meaning") or value.get("description") or "").strip()
        if not concept and meaning:
            concept = infer_concept(meaning)
    else:
        return None

    concept = safe_text(concept, 48)
    meaning = safe_text(meaning, 180)
    if len(concept) < 2 or len(meaning) < 6:
        return None

    pet = normalize_pet(payload.get("pet"))
    message = safe_text(payload.get("message") or "", 180)
    return {
        "pet": pet,
        "concept": concept,
        "meaning": meaning,
        "source": "player-teaching" if message else "agent-reflection",
        "learnedFrom": message,
        "at": int(time.time()),
    }


def remember_from_action(action: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any] | None:
    memory = clean_new_memory(action.get("newMemory"), payload)
    if not memory:
        return None
    path = memory_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(memory, ensure_ascii=True, separators=(",", ":")) + "\n")
    except OSError:
        return None
    action["newMemory"] = compact_memory(memory)
    return action["newMemory"]


def compact_memory(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "pet": normalize_pet(item.get("pet")),
        "concept": safe_text(item.get("concept") or "", 48),
        "meaning": safe_text(item.get("meaning") or "", 180),
        "source": safe_text(item.get("source") or "", 40),
        "learnedFrom": safe_text(item.get("learnedFrom") or "", 120),
        "at": int(item.get("at") or 0),
    }


def infer_concept(text: str) -> str:
    quoted = re.search(r"['\"]([^'\"]{2,48})['\"]", text)
    if quoted:
        return quoted.group(1)
    called = re.search(r"\bcalled\s+['\"]?([a-zA-Z0-9 _-]{2,48}?)(?:['\"]|[:.,;!?]|$)", text, re.IGNORECASE)
    if called:
        return called.group(1)
    rule = re.search(r"\b(?:remember\s+)?(?:this\s+)?rule\s*:\s*([^.,;!?]{2,64})", text, re.IGNORECASE)
    if rule:
        return rule.group(1)
    remember = re.search(r"\bremember\s+(?:that\s+)?([^.,;!?]{2,64})", text, re.IGNORECASE)
    if remember:
        return remember.group(1)
    never = re.search(r"\bnever\s+([^.,;!?]{2,64})", text, re.IGNORECASE)
    if never:
        return "never " + never.group(1)
    always = re.search(r"\balways\s+([^.,;!?]{2,64})", text, re.IGNORECASE)
    if always:
        return "always " + always.group(1)
    words = re.sub(r"[^a-zA-Z0-9 _-]+", " ", text).strip().split()
    return " ".join(words[:5]) or "new lesson"


def safe_text(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]
