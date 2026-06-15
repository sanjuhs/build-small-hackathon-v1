from __future__ import annotations

from typing import Any

from src.pet_payload import target_from_payload
from src.pet_profiles import PET_PROFILES, normalize_pet


def coerce_fireboy_command_action(action: dict[str, Any], payload: dict[str, Any]) -> None:
    message = str(payload.get("message") or "").lower()
    pet = normalize_pet(action.get("pet") or payload.get("pet"))
    if pet != "fire_boy":
        return
    if is_stop_request(message):
        action["animation"] = "idle"
        action["intent"] = "grounded_stop_idle"
        action["power"] = {"name": "ember_jump", "targetId": "self", "strength": 0.0, "durationMs": 200}
        action["interaction"] = {"verb": "stop", "targetId": "self", "partnerPet": "", "durationMs": 300}
        action["spell"] = cosmetic_spell("stop marker", "self", "#ffd75a")
        action["speech"] = "Me stop."
        mark_grounded(action, "stop", "self")
    elif is_greeting_request(message):
        target_id = viewer_target_id(payload)
        action["animation"] = "look"
        action["intent"] = "grounded_greet_player"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.2, "durationMs": 650}
        action["interaction"] = {"verb": "look_at", "targetId": target_id, "partnerPet": "", "durationMs": 1200}
        action["spell"] = cosmetic_spell("tiny hello", "self", "#ffb347")
        action["speech"] = "Hi hi, me Fire Boy."
        mark_grounded(action, "greet_player", target_id)
        mark_combo(action, "wave")
    elif is_dance_request(message):
        target_id = viewer_target_id(payload)
        action["animation"] = "look"
        action["intent"] = "grounded_dance_player"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.24, "durationMs": 700}
        action["interaction"] = {"verb": "look_at", "targetId": target_id, "partnerPet": "", "durationMs": 900}
        action["spell"] = cosmetic_spell("dance marker", "self", "#ffb347")
        action["speech"] = "Me do tiny dance."
        mark_grounded(action, "dance_player", target_id)
        mark_combo(action, "dance")
    elif is_sit_request(message):
        target_id = command_target_id(payload, {"chair", "seat", "stool", "sit"})
        action["animation"] = "sit"
        action["intent"] = "grounded_sit_chair"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.18, "durationMs": 650}
        action["interaction"] = {"verb": "sit", "targetId": target_id, "partnerPet": "", "durationMs": 2200}
        action["spell"] = cosmetic_spell("sit marker", target_id, "#ffd75a")
        action["speech"] = "Me sit tiny."
        mark_grounded(action, "sit_chair", target_id)
        mark_combo(action, "sit")
    elif is_throw_request(message):
        target_id = command_target_id(payload, {"ball", "sphere", "orb", "toy"})
        action["animation"] = "throw"
        action["intent"] = "grounded_throw_to_player"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.3, "durationMs": 650}
        action["interaction"] = {"verb": "throw", "targetId": target_id, "partnerPet": "", "durationMs": 1400}
        action["spell"] = cosmetic_spell("catch throw marker", target_id, "#ffd75a")
        action["speech"] = "Me toss to you."
        mark_grounded(action, "throw_to_player", target_id)
        mark_combo(action, "throw")
    elif any(phrase in message for phrase in ["turn around", "turn back", "spin around", "face away"]):
        target_id = command_target_id(payload)
        action["animation"] = "turn" if "turn" in PET_PROFILES[pet]["animations"] else "bounce"
        action["intent"] = "grounded_turn"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.25, "durationMs": 700}
        action["interaction"] = {"verb": "turn", "targetId": target_id, "partnerPet": "", "durationMs": 1300}
        action["spell"] = cosmetic_spell("turn marker", "self", "#ffb347")
        action["speech"] = "Me turn round."
        mark_grounded(action, "turn", target_id)
    elif any(phrase in message for phrase in ["look at me", "look to me", "look toward me", "look towards me", "face me", "turn to me", "turn toward me", "turn towards me", "watch me"]):
        target_id = command_target_id(payload)
        action["animation"] = "look" if "look" in PET_PROFILES[pet]["animations"] else "look_left_right"
        action["intent"] = "grounded_look_at_player"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.22, "durationMs": 700}
        action["interaction"] = {"verb": "look_at", "targetId": target_id, "partnerPet": "", "durationMs": 1700}
        action["spell"] = cosmetic_spell("look marker", "self", "#ffd75a")
        action["speech"] = "Me looky."
        mark_grounded(action, "look_at_player", target_id)
    elif any(phrase in message for phrase in ["point at", "show me", "show the", "gesture at"]):
        target_id = command_target_id(payload, {"box", "cube", "block", "toy", "ball"})
        action["animation"] = "point" if "point" in PET_PROFILES[pet]["animations"] else "look_left_right"
        action["intent"] = "grounded_point"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.25, "durationMs": 700}
        action["interaction"] = {"verb": "point", "targetId": target_id, "partnerPet": "", "durationMs": 1800}
        action["spell"] = cosmetic_spell("point marker", target_id, "#ffd75a")
        action["speech"] = "Me pointy there."
        mark_grounded(action, "point", target_id)
    elif any(phrase in message for phrase in ["reach for", "touch the", "poke the", "tap the"]):
        target_id = command_target_id(payload, {"box", "cube", "block", "toy", "ball"})
        action["animation"] = "reach" if "reach" in PET_PROFILES[pet]["animations"] else "look_left_right"
        action["intent"] = "grounded_reach"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.25, "durationMs": 700}
        action["interaction"] = {"verb": "reach", "targetId": target_id, "partnerPet": "", "durationMs": 1900}
        action["spell"] = cosmetic_spell("reach marker", target_id, "#ffd75a")
        action["speech"] = "Me reach careful."
        mark_grounded(action, "reach", target_id)
    elif any(phrase in message for phrase in ["drop it", "put it down", "release", "let go"]):
        target_id = command_target_id(payload)
        action["animation"] = "reach" if "reach" in PET_PROFILES[pet]["animations"] else "bounce"
        action["intent"] = "grounded_release"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.2, "durationMs": 600}
        action["interaction"] = {"verb": "release", "targetId": target_id, "partnerPet": "", "durationMs": 1200}
        action["spell"] = cosmetic_spell("release marker", "self", "#ffb347")
        action["speech"] = "Me put down."
        mark_grounded(action, "release", target_id)
    elif any(phrase in message for phrase in ["look at", "face the", "watch the", "look toward", "look towards", "look to the", "turn toward", "turn towards", "turn to the", "face toward", "face towards"]):
        target_id = command_target_id(payload, {"box", "cube", "block", "toy", "ball", "chair", "table", "lamp", "plant", "book", "clock"})
        action["animation"] = "look" if "look" in PET_PROFILES[pet]["animations"] else "look_left_right"
        action["intent"] = "grounded_look_at"
        action["power"] = {"name": "ember_jump", "targetId": target_id, "strength": 0.22, "durationMs": 700}
        action["interaction"] = {"verb": "look_at", "targetId": target_id, "partnerPet": "", "durationMs": 1700}
        action["spell"] = cosmetic_spell("look marker", target_id, "#ffd75a")
        action["speech"] = "Me looky."
        mark_grounded(action, "look_at", target_id)
    elif command_has_any(message, ["walk", "stroll", "patrol"]):
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
    elif is_pickup_request(message):
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
        "turn",
        "spin",
        "face",
        "point",
        "reach",
        "touch",
        "tap",
        "poke",
        "release",
        "stop",
        "pause",
        "idle",
        "halt",
        "drop",
        "let go",
        "inspect",
        "look",
        "see",
        "create",
        "make",
        "spawn",
        "wish",
        "sit",
        "dance",
        "throw",
        "toss",
        "catch",
    ]
    if any(word in message for word in explicit):
        return False
    chat = ["hi", "hello", "hey", "what's up", "whats up", "how are", "talk", "say"]
    return not message.strip() or any(phrase in message for phrase in chat)


def is_greeting_request(message: str) -> bool:
    if any(word in message for word in ["walk", "run", "go to", "move to", "pick", "grab", "eat"]):
        return False
    return any(phrase in message for phrase in ["say hi", "say hello", "hello", "hi", "hey", "greet", "wave"])


def is_stop_request(message: str) -> bool:
    padded = f" {message} "
    return any(phrase in padded for phrase in [" stop ", " pause ", " idle ", " halt ", " stay "]) or "hold still" in message


def is_dance_request(message: str) -> bool:
    if any(phrase in message for phrase in ["go to", "move to", "walk to", "run to", "pick", "grab", "eat"]):
        return False
    return any(word in set(re_split_words(message)) for word in ["dance", "boogie", "celebrate"])


def is_sit_request(message: str) -> bool:
    padded = f" {message} "
    return " sit " in padded or "sit down" in message or "take a seat" in message


def is_throw_request(message: str) -> bool:
    return any(phrase in message for phrase in ["play catch", "catch", "throw", "toss"])


def is_pickup_request(message: str) -> bool:
    padded = f" {message} "
    return (
        " pick " in padded
        or "pick up" in message
        or "pickup" in message
        or " grab " in padded
        or " hold " in padded
        or "lift the" in message
        or "take the" in message
    )


def command_has_any(message: str, words: list[str]) -> bool:
    tokens = set(re_split_words(message))
    return any(word in tokens or f"{word} around" in message or f"{word} the room" in message for word in words)


def command_target_id(payload: dict[str, Any], preferred_words: set[str] | None = None) -> str:
    message = str(payload.get("message") or "").lower()
    scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else {}
    objects = scene.get("objects") if isinstance(scene.get("objects"), list) else []
    preferred_words = preferred_words or set()
    message_words = expanded_message_terms(message)
    requested_groups = requested_target_groups(message_words)
    grouped_objects = []
    if requested_groups:
        for item in objects:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            terms = object_terms(item)
            if any(terms & TARGET_GROUP_ALIASES.get(group, {group}) for group in requested_groups):
                grouped_objects.append(item)
    scan_objects = grouped_objects or objects
    explicit_best: tuple[int, float, dict[str, Any]] | None = None
    preferred_best: tuple[int, float, dict[str, Any]] | None = None
    for item in scan_objects:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        terms = object_terms(item)
        normalized = " ".join(sorted(terms))
        exact_score = sum(12 for word in message_words if word in terms)
        for color, aliases in TARGET_COLOR_ALIASES.items():
            if color in message_words or aliases & message_words:
                if aliases & terms:
                    exact_score += 14
        for group in requested_groups:
            if TARGET_GROUP_ALIASES.get(group, {group}) & terms:
                exact_score += 18
        if "soft ball" in message and {"soft", "ball"} <= terms:
            exact_score += 8
        if "reading lamp" in message and str(item.get("id")) == "reading-lamp":
            exact_score += 12
        if "tea table" in message and str(item.get("id")) == "tea-table":
            exact_score += 12
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


def viewer_target_id(payload: dict[str, Any]) -> str:
    scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else {}
    objects = scene.get("objects") if isinstance(scene.get("objects"), list) else []
    for item in objects:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        terms = object_terms(item)
        if {"viewer", "camera", "player", "me", "user", "here"} & terms or str(item.get("id")) == "player-camera":
            return str(item.get("id"))
    return "player-camera"


def re_split_words(value: str) -> list[str]:
    return [word for word in "".join(char if char.isalnum() else " " for char in value).split() if word]


TARGET_GROUP_ALIASES = {
    "berry": {"berry", "berries", "food", "snack"},
    "ball": {"ball", "sphere", "orb", "round"},
    "cube": {"cube", "block", "box"},
    "chair": {"chair", "seat", "stool", "sit"},
    "table": {"table", "desk"},
    "lamp": {"lamp", "light"},
    "plant": {"plant", "fern", "sprout", "pot"},
    "book": {"book", "notes", "story"},
    "clock": {"clock", "timer"},
    "bottle": {"bottle"},
    "can": {"can", "tin"},
    "paper": {"paper"},
    "waste": {"waste", "trash", "garbage", "peel"},
    "bin": {"bin", "recycle"},
    "ramp": {"ramp"},
    "domino": {"domino"},
    "viewer": {"me", "camera", "viewer", "player", "user", "here"},
}

TARGET_COLOR_ALIASES = {
    "blue": {"blue", "cyan", "teal"},
    "mint": {"mint", "green", "teal"},
    "green": {"green", "mint", "leaf", "fern"},
    "yellow": {"yellow", "amber", "honey", "gold", "golden"},
    "orange": {"orange", "coral", "ember", "fire"},
    "red": {"red", "rose", "pink"},
    "purple": {"purple", "violet", "moon"},
    "white": {"white", "pale", "cream"},
    "black": {"black", "dark"},
    "brown": {"brown", "wood", "wooden"},
}


def expanded_message_terms(message: str) -> set[str]:
    terms = {word for word in re_split_words(message) if len(word) >= 3}
    expanded = set(terms)
    for aliases in TARGET_GROUP_ALIASES.values():
        if aliases & terms:
            expanded |= aliases
    for aliases in TARGET_COLOR_ALIASES.values():
        if aliases & terms:
            expanded |= aliases
    return expanded


def requested_target_groups(message_words: set[str]) -> set[str]:
    return {group for group, aliases in TARGET_GROUP_ALIASES.items() if aliases & message_words}


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
    kind = str(item.get("kind") or "").lower()
    if kind == "ball":
        terms.update({"sphere", "orb", "round", "toy"})
    elif kind == "berry":
        terms.update({"berries", "food", "snack", "sphere", "round"})
    elif kind == "cube":
        terms.update({"block", "box"})
    elif kind == "chair":
        terms.update({"seat", "furniture"})
    elif kind == "table":
        terms.update({"desk", "furniture"})
    elif kind == "lamp":
        terms.update({"light"})
    elif kind == "plant":
        terms.update({"fern", "sprout", "pot", "green"})
    elif kind == "recycle-bin":
        terms.update({"bin", "recycle", "trash", "waste"})
    if object_id == "soft-ball":
        terms.update({"yellow", "gold", "golden", "soft", "ball", "sphere", "orb"})
    elif object_id == "moon-ball":
        terms.update({"moon", "pale", "mint", "blue", "purple", "ball", "sphere"})
    elif object_id == "beach-orb":
        terms.update({"beach", "white", "pale", "orb", "ball", "sphere"})
    if "blue" in object_id:
        terms.update({"blue", "cyan", "teal"})
    if "mint" in object_id:
        terms.update({"mint", "green", "teal"})
    if "coral" in object_id:
        terms.update({"coral", "orange", "red"})
    if "honey" in object_id:
        terms.update({"honey", "yellow", "gold", "golden"})
    if "amber" in object_id:
        terms.update({"amber", "yellow", "orange", "gold", "golden"})
    if "ember" in object_id or "fire" in object_id:
        terms.update({"ember", "fire", "orange", "red", "warm"})
    if "rose" in object_id:
        terms.update({"rose", "red", "pink"})
    if "reading-lamp" in object_id:
        terms.update({"reading", "blue", "cyan", "lamp", "light"})
    elif "lamp" in object_id:
        terms.update({"yellow", "warm", "lamp", "light"})
    if "fern" in object_id or "sprout" in object_id:
        terms.update({"green", "plant", "leaf"})
    if "paper" in object_id:
        terms.update({"paper", "white", "waste", "trash", "sphere"})
    if "can" in object_id:
        terms.update({"can", "tin", "metal", "waste"})
    if "bottle" in object_id:
        terms.update({"bottle", "blue", "waste"})
    if "peel" in object_id:
        terms.update({"peel", "banana", "yellow", "waste"})
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


def mark_combo(action: dict[str, Any], combo: str) -> None:
    debug = action.setdefault("debug", {})
    if isinstance(debug, dict):
        debug["postActionCombo"] = combo
