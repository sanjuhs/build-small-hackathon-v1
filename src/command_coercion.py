from __future__ import annotations

from typing import Any

from src.pet_payload import target_from_payload
from src.pet_profiles import PET_PROFILES, normalize_pet


def coerce_fireboy_command_action(action: dict[str, Any], payload: dict[str, Any]) -> None:
    message = str(payload.get("message") or "").lower()
    pet = normalize_pet(action.get("pet") or payload.get("pet"))
    if pet != "fire_boy":
        return
    if command_has_any(message, ["walk", "stroll", "patrol"]):
        target_id = command_target_id(payload)
        action["animation"] = "walk"
        action["intent"] = "grounded_walk"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.45, "durationMs": 900}
        action["interaction"] = {"verb": "walk", "targetId": target_id, "partnerPet": "", "durationMs": 5200}
        action["spell"] = cosmetic_spell("walk marker", "self", "#ff9b45")
        action["speech"] = "Me walky loop."
        mark_grounded(action, "walk", target_id)
    elif command_has_any(message, ["run", "zoom", "dash", "race"]):
        target_id = command_target_id(payload)
        action["animation"] = "run"
        action["intent"] = "grounded_run"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.7, "durationMs": 900}
        action["interaction"] = {"verb": "run", "targetId": target_id, "partnerPet": "", "durationMs": 3600}
        action["spell"] = cosmetic_spell("run marker", "self", "#ff6b3d")
        action["speech"] = "Me do zoom loop."
        mark_grounded(action, "run", target_id)
    elif any(phrase in message for phrase in ["pick up", "pickup", "grab", "hold", "lift the", "take the"]):
        target_id = command_target_id(payload, {"box", "cube", "block", "toy", "ball"})
        action["animation"] = "walk" if "walk" in PET_PROFILES[pet]["animations"] else action.get("animation", "flame_wiggle")
        action["intent"] = "grounded_pickup"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.35, "durationMs": 800}
        action["interaction"] = {"verb": "pickup", "targetId": target_id, "partnerPet": "", "durationMs": 2600}
        action["spell"] = cosmetic_spell("pickup marker", target_id, "#ffd75a")
        action["speech"] = "Me hold it, hehe."
        mark_grounded(action, "pickup", target_id)
    elif any(phrase in message for phrase in ["bring", "fetch", "carry"]):
        target_id = command_target_id(payload, {"box", "cube", "block", "toy", "ball"})
        verb = "bring" if any(phrase in message for phrase in ["bring", "fetch"]) else "carry"
        action["animation"] = "walk" if "walk" in PET_PROFILES[pet]["animations"] else action.get("animation", "flame_wiggle")
        action["intent"] = f"grounded_{verb}"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.35, "durationMs": 800}
        action["interaction"] = {"verb": verb, "targetId": target_id, "partnerPet": "", "durationMs": 3000}
        action["spell"] = cosmetic_spell("carry marker", target_id, "#ffd75a")
        action["speech"] = "Me bring tiny thing."
        mark_grounded(action, verb, target_id)
    elif "fireball" in message:
        target_id = command_target_id(payload, {"box", "cube", "block", "toy", "ball"})
        action["animation"] = "flame_wiggle"
        action["power"] = {"name": "fireball", "targetId": target_id, "strength": 0.95, "durationMs": 1400}
        action["interaction"] = {"verb": "none", "targetId": target_id, "partnerPet": "", "durationMs": 1000}
        action["spell"] = {
            "spellName": "supervised ember",
            "ops": [
                {"op": "spawn_particle", "targetId": target_id, "durationMs": 1100, "color": "#ff7a33"},
                {"op": "set_light", "targetId": target_id, "intensity": 70, "durationMs": 260, "color": "#ffb347"},
            ],
        }
        action["speech"] = "Me make warm sparkle."
    elif is_generic_chat_message(message):
        target_id = command_target_id(payload)
        action["animation"] = "bounce"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.25, "durationMs": 700}
        action["interaction"] = {"verb": "talk", "targetId": target_id, "partnerPet": "", "durationMs": 1400}
        action["spell"] = {
            "spellName": "tiny hello",
            "ops": [{"op": "spawn_particle", "targetId": "self", "durationMs": 700, "color": "#ffb347"}],
        }
        action["speech"] = "Me here, hehe."


def is_generic_chat_message(message: str) -> bool:
    explicit = [
        "walk",
        "run",
        "pick",
        "grab",
        "hold",
        "bring",
        "fetch",
        "carry",
        "fireball",
        "smoke",
        "jump",
        "inspect",
        "look",
        "see",
        "create",
        "make",
        "spawn",
        "wish",
    ]
    if any(word in message for word in explicit):
        return False
    chat = ["hi", "hello", "hey", "what's up", "whats up", "how are", "talk", "say"]
    return not message.strip() or any(phrase in message for phrase in chat)


def command_has_any(message: str, words: list[str]) -> bool:
    tokens = set(re_split_words(message))
    return any(word in tokens or f"{word} around" in message or f"{word} the room" in message for word in words)


def command_target_id(payload: dict[str, Any], preferred_words: set[str] | None = None) -> str:
    message = str(payload.get("message") or "").lower()
    scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else {}
    objects = scene.get("objects") if isinstance(scene.get("objects"), list) else []
    preferred_words = preferred_words or set()
    message_words = {word for word in re_split_words(message) if len(word) >= 3}
    detected_ids = {
        str(item.get("id"))
        for item in payload.get("detectedObjects", [])
        if isinstance(item, dict) and item.get("id")
    }
    explicit_best: tuple[int, float, dict[str, Any]] | None = None
    preferred_best: tuple[int, float, dict[str, Any]] | None = None
    for item in objects:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        terms = object_terms(item)
        normalized = " ".join(sorted(terms))
        exact_score = sum(12 for word in message_words if word in terms)
        if "yellow" in message_words and {"yellow", "amber"} & terms:
            exact_score += 10
        if "soft ball" in message and {"soft", "ball"} <= terms:
            exact_score += 8
        if str(item["id"]) in detected_ids:
            exact_score += 2
        preferred_score = sum(1 for word in preferred_words if word in terms or word in normalized)
        distance = -float(item.get("distanceToPet") or 999)
        if exact_score > 0:
            candidate = (exact_score + preferred_score, distance, item)
            if explicit_best is None or candidate[:2] > explicit_best[:2]:
                explicit_best = candidate
        elif preferred_score > 0:
            candidate = (preferred_score, distance, item)
            if preferred_best is None or candidate[:2] > preferred_best[:2]:
                preferred_best = candidate
    if explicit_best:
        return str(explicit_best[2]["id"])
    if preferred_best:
        return str(preferred_best[2]["id"])
    return target_from_payload(payload)


def re_split_words(value: str) -> list[str]:
    return [word for word in "".join(char if char.isalnum() else " " for char in value).split() if word]


def object_terms(item: dict[str, Any]) -> set[str]:
    fields = [
        str(item.get("id") or ""),
        str(item.get("kind") or ""),
        str(item.get("name") or ""),
        " ".join(str(tag) for tag in (item.get("tags") or [])),
        " ".join(str(affordance) for affordance in (item.get("affordances") or [])),
    ]
    terms = set(re_split_words(" ".join(fields).lower().replace("-", " ")))
    object_id = str(item.get("id") or "").lower()
    if object_id == "soft-ball":
        terms.update({"yellow", "amber", "gold", "golden", "soft", "ball"})
    elif object_id == "moon-ball":
        terms.update({"moon", "pale", "mint", "ball"})
    elif object_id == "beach-orb":
        terms.update({"beach", "white", "orb", "ball"})
    return terms


def cosmetic_spell(name: str, target_id: str, color: str) -> dict[str, Any]:
    return {
        "spellName": name,
        "ops": [{"op": "spawn_particle", "targetId": target_id, "durationMs": 700, "color": color}],
    }


def mark_grounded(action: dict[str, Any], command: str, target_id: str) -> None:
    debug = action.setdefault("debug", {})
    if isinstance(debug, dict):
        debug["commandCoercion"] = command
        debug["groundedTargetId"] = target_id
