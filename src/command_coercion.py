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
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.45, "durationMs": 900}
        action["interaction"] = {"verb": "walk", "targetId": target_id, "partnerPet": "", "durationMs": 4200}
        action["spell"] = {
            "spellName": "tiny walk loop",
            "ops": [
                {"op": "nudge_pet", "targetId": "self", "vec": [0.55, 0.0, 0.35], "durationMs": 480},
                {"op": "spawn_particle", "targetId": "self", "durationMs": 850, "color": "#ff9b45"},
            ],
        }
        action["speech"] = "Me walky loop."
    elif command_has_any(message, ["run", "zoom", "dash", "race"]):
        target_id = command_target_id(payload)
        action["animation"] = "run"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.7, "durationMs": 900}
        action["interaction"] = {"verb": "run", "targetId": target_id, "partnerPet": "", "durationMs": 2800}
        action["spell"] = {
            "spellName": "tiny zoom loop",
            "ops": [
                {"op": "nudge_pet", "targetId": "self", "vec": [1.0, 0.0, 0.65], "durationMs": 360},
                {"op": "spawn_particle", "targetId": "self", "durationMs": 1050, "color": "#ff6b3d"},
            ],
        }
        action["speech"] = "Me do zoom loop."
    elif any(phrase in message for phrase in ["pick up", "pickup", "grab", "hold", "lift the", "take the"]):
        target_id = command_target_id(payload, {"box", "cube", "block", "toy", "ball"})
        action["animation"] = "walk" if "walk" in PET_PROFILES[pet]["animations"] else action.get("animation", "flame_wiggle")
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.35, "durationMs": 800}
        action["interaction"] = {"verb": "pickup", "targetId": target_id, "partnerPet": "", "durationMs": 2600}
        action["spell"] = {
            "spellName": "warm little pickup",
            "ops": [
                {"op": "spawn_particle", "targetId": target_id, "durationMs": 900, "color": "#ffd75a"},
                {"op": "set_light", "targetId": target_id, "intensity": 54, "durationMs": 220, "color": "#ffd75a"},
            ],
        }
        action["speech"] = "Me hold it, hehe."
    elif any(phrase in message for phrase in ["bring", "fetch", "carry"]):
        target_id = command_target_id(payload, {"box", "cube", "block", "toy", "ball"})
        verb = "bring" if any(phrase in message for phrase in ["bring", "fetch"]) else "carry"
        action["animation"] = "walk" if "walk" in PET_PROFILES[pet]["animations"] else action.get("animation", "flame_wiggle")
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.35, "durationMs": 800}
        action["interaction"] = {"verb": verb, "targetId": target_id, "partnerPet": "", "durationMs": 3000}
        action["speech"] = "Me bring tiny thing."
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
    for item in objects:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        haystack = " ".join(
            [
                str(item.get("id") or ""),
                str(item.get("kind") or ""),
                str(item.get("name") or ""),
                " ".join(str(tag) for tag in (item.get("tags") or [])),
            ]
        ).lower()
        if preferred_words and any(word in haystack for word in preferred_words):
            return str(item["id"])
        if any(word and len(word) > 2 and word in haystack for word in re_split_words(message)):
            return str(item["id"])
    return target_from_payload(payload)


def re_split_words(value: str) -> list[str]:
    return [word for word in "".join(char if char.isalnum() else " " for char in value).split() if word]
