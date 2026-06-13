from __future__ import annotations

import copy
import os
import re
from functools import lru_cache
from typing import Any

from src.pet_actions import validate_action
from src.pet_payload import compact_payload
from src.pet_profiles import normalize_pet
from src.trace_dataset import is_usable_trace, iter_trace_records, output_policy, trace_path


STOPWORDS = {
    "the",
    "and",
    "you",
    "your",
    "with",
    "that",
    "this",
    "room",
    "toy",
    "toys",
    "agent",
    "please",
    "use",
    "what",
    "from",
    "into",
    "for",
    "are",
    "was",
    "were",
}


def trace_policy_enabled() -> bool:
    return os.getenv("TOYBOX_TRACE_POLICY", "1").lower() not in {"0", "false", "no"}


def try_trace_policy(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not trace_policy_enabled():
        return None
    compact = compact_payload(payload)
    match = best_trace_match(compact)
    if not match:
        return None
    record, score = match
    if score < float(os.getenv("TOYBOX_TRACE_POLICY_MIN_SCORE", "3.2")):
        return None
    output = copy.deepcopy(record.get("output") or {})
    output["pet"] = normalize_pet(payload.get("pet"))
    try:
        action = validate_action(output, payload)
    except Exception:
        return None
    if not action_satisfies_request(compact, action):
        return None
    action["debug"] = {
        "policy": "trace_retrieval",
        "score": round(score, 3),
        "sourcePolicy": output_policy(record.get("output")),
        "sourceTimestamp": str(record.get("timestamp") or "")[:48],
    }
    return action


def best_trace_match(compact: dict[str, Any]) -> tuple[dict[str, Any], float] | None:
    candidates = usable_trace_records()
    if not candidates:
        return None
    scored: list[tuple[float, dict[str, Any]]] = []
    for record in candidates:
        score = score_record(compact, record)
        if score > 0:
            scored.append((score, record))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1], scored[0][0]


@lru_cache(maxsize=4)
def usable_trace_records_cached(path: str, mtime_ns: int, size: int) -> tuple[dict[str, Any], ...]:
    _ = (mtime_ns, size)
    records = iter_trace_records(trace_path_from_string(path))
    usable = [record for record in records if is_usable_trace(record)]
    usable.sort(key=lambda record: trace_priority(record), reverse=True)
    return tuple(usable[: int(os.getenv("TOYBOX_TRACE_POLICY_MAX_RECORDS", "700"))])


def usable_trace_records() -> tuple[dict[str, Any], ...]:
    path = trace_path()
    try:
        stat = path.stat()
        return usable_trace_records_cached(str(path), stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        return usable_trace_records_cached(str(path), 0, 0)


def trace_path_from_string(value: str):
    from pathlib import Path

    return Path(value)


def trace_priority(record: dict[str, Any]) -> float:
    policy = output_policy(record.get("output"))
    if policy == "model":
        return 4
    if policy == "seed":
        return 3
    if policy == "trace_retrieval":
        return 1
    return 2


def score_record(current: dict[str, Any], record: dict[str, Any]) -> float:
    previous = record.get("input") if isinstance(record.get("input"), dict) else {}
    output = record.get("output") if isinstance(record.get("output"), dict) else {}
    score = 0.0
    if normalize_pet(previous.get("pet")) == normalize_pet(current.get("pet")):
        score += 2.4
    elif output.get("pet") and normalize_pet(output.get("pet")) != normalize_pet(current.get("pet")):
        score -= 0.8

    score += overlap_score(tokens(current.get("user_message")), tokens(previous.get("user_message")), 4.5)
    score += overlap_score(object_terms(current), object_terms(previous), 3.2)
    score += overlap_score(affordance_terms(current), affordance_terms(previous), 2.4)
    score += overlap_score(context_terms(current), context_terms(previous), 2.0)

    current_message = str(current.get("user_message") or "").lower()
    previous_message = str(previous.get("user_message") or "").lower()
    output_text = " ".join(
        [
            str(output.get("intent") or ""),
            str((output.get("interaction") or {}).get("verb") or "") if isinstance(output.get("interaction"), dict) else "",
            str((output.get("objectRecipe") or {}).get("name") or "") if isinstance(output.get("objectRecipe"), dict) else "",
        ]
    ).lower()
    for cue in ("wish", "recycle", "vision", "camera", "talk", "play", "comfort", "force", "dropped", "sound", "heard"):
        if cue in current_message and (cue in previous_message or cue in output_text):
            score += 1.1
    if "what did i build" in current_message and ("charade" in previous_message or "parade" in str(output.get("speech") or "").lower()):
        score += 2.0
    if current.get("cameraFrameSource") == previous.get("cameraFrameSource") and current.get("cameraFrameSource"):
        score += 0.5
    return score


def action_satisfies_request(compact: dict[str, Any], action: dict[str, Any]) -> bool:
    message = str(compact.get("user_message") or "").lower()
    interaction = action.get("interaction") if isinstance(action.get("interaction"), dict) else {}
    verb = str(interaction.get("verb") or "")
    power = action.get("power") if isinstance(action.get("power"), dict) else {}
    power_name = str(power.get("name") or "")
    spell = action.get("spell") if isinstance(action.get("spell"), dict) else {}
    spell_name = str(spell.get("spellName") or "").lower()
    intent = str(action.get("intent") or "").lower()
    speech = str(action.get("speech") or "").lower()

    if any(phrase in message for phrase in ("pick up", "pickup", "grab", "hold", "lift the", "carry", "bring me", "bring the", "fetch")):
        if verb not in {"pickup", "carry", "bring"}:
            return False
        if power_name == "fireball" or "fireball" in spell_name or "comet" in spell_name:
            return False
    if any(phrase in message for phrase in ("run around", "run in circles", "go around", "zoom around", "dash around", "race around")):
        if verb != "run":
            return False
    if "fireball" in message or "fire ball" in message:
        if power_name != "fireball":
            return False
    if any(word in message for word in ("remember", "learn", "lesson", "rule")):
        memory = action.get("newMemory") if isinstance(action.get("newMemory"), dict) else None
        if not memory or not memory.get("concept"):
            return False
    if any(word in message for word in ("wish", "create", "spawn", "summon", "add a", "add an")):
        recipe = action.get("objectRecipe") if isinstance(action.get("objectRecipe"), dict) else None
        if not recipe or not recipe.get("name"):
            return False
    if any(word in message for word in ("vision", "camera", "what do you see", "inspect it")):
        if intent != "vision_grounded":
            return False
    if any(word in message for word in ("recycle", "tidy", "waste", "trash")):
        if verb not in {"recycle", "clean"}:
            return False
    if any(word in message for word in ("talk", "play", "invite", "friend", "together", "comfort", "share")):
        if verb not in {"talk", "play", "comfort", "share", "gather"}:
            return False
    if any(phrase in message for phrase in ("what did i build", "what did i make", "guess", "charade")):
        if not any(word in speech for word in ("parade", "tower", "huddle", "stack", "line", "domino")):
            return False
    return True


def overlap_score(left: set[str], right: set[str], weight: float) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left & right)
    union = len(left | right)
    if not union:
        return 0.0
    return weight * (intersection / union)


def tokens(value: Any) -> set[str]:
    return {
        item
        for item in re.findall(r"[a-z0-9_]+", str(value or "").lower())
        if len(item) > 2 and item not in STOPWORDS
    }


def object_terms(payload: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    for item in list_payload(payload, "objects") + list_payload(payload, "detectedObjects"):
        for key in ("id", "kind", "name"):
            terms.update(tokens(item.get(key)))
    return terms


def affordance_terms(payload: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    for item in list_payload(payload, "objects"):
        for value in item.get("affordances") or []:
            terms.update(tokens(value))
        for value in item.get("tags") or []:
            terms.update(tokens(value))
    return terms


def context_terms(payload: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    for force in list_payload(payload, "recentForces"):
        terms.update(tokens(force.get("kind")))
        terms.update(tokens(force.get("objectId")))
    for interaction in list_payload(payload, "interactions"):
        terms.update(tokens(interaction.get("kind")))
        terms.update(tokens(interaction.get("objectId")))
        terms.update(tokens(interaction.get("partnerPet")))
    audio = payload.get("audio") if isinstance(payload.get("audio"), dict) else {}
    input_audio = audio.get("input") if isinstance(audio.get("input"), dict) else {}
    if audio.get("active") or input_audio.get("active"):
        terms.add("audio")
    arrangements = payload.get("arrangements") if isinstance(payload.get("arrangements"), list) else []
    for arrangement in arrangements:
        terms.update(tokens(arrangement.get("kind")))
        terms.update(tokens(arrangement.get("label")))
    return terms


def list_payload(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
