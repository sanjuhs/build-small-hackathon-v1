from __future__ import annotations

import random
import re
from typing import Any

from src.pet_memory import clean_new_memory
from src.pet_payload import detect_scene_arrangements, latest_touch, object_label, target_from_payload, target_ids_from_payload
from src.pet_profiles import FACE_BLENDSHAPE_KEYS, PET_PROFILES, VALID_EMOTIONS, line_for, normalize_pet, valid_choice


INTERACTION_VERBS = [
    "none",
    "eat",
    "read",
    "sit",
    "gather",
    "sniff",
    "inspect",
    "water",
    "share",
    "clean",
    "recycle",
    "play",
    "comfort",
    "talk",
    "pickup",
    "carry",
    "bring",
    "walk",
    "run",
]

SPELL_OPS = ["impulse", "freeze", "scale", "attract", "spawn_particle", "set_light", "nudge_pet"]
SPELL_TARGETS = ["self", "all-moving", "all-toys", "all-agents"]
SOUND_WAVES = ["sine", "triangle", "square", "sawtooth"]
OBJECT_KINDS = ["toy", "instrument", "furniture", "food", "plant", "waste", "tool", "creature", "decor"]
OBJECT_SHAPES = ["box", "sphere", "cylinder", "composite"]
OBJECT_AFFORDANCES = [
    "play",
    "inspect",
    "read",
    "eat",
    "sniff",
    "sit",
    "gather",
    "light",
    "roll",
    "stack",
    "music",
    "clean",
    "recycle",
    "throw",
    "hide",
]


def action_schema(profile: dict[str, Any], target_ids: list[str]) -> dict[str, Any]:
    spell_targets = list(dict.fromkeys(target_ids + SPELL_TARGETS))
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "pet": {"type": "string", "enum": list(PET_PROFILES)},
            "speech": {"type": "string"},
            "emotion": {"type": "string", "enum": VALID_EMOTIONS},
            "animation": {"type": "string", "enum": profile["animations"]},
            "intent": {"type": "string"},
            "blendshape": {
                "type": "object",
                "additionalProperties": False,
                "properties": {key: {"type": "number", "minimum": -1.5, "maximum": 1.5} for key in FACE_BLENDSHAPE_KEYS},
            },
            "power": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string", "enum": profile["powers"]},
                    "targetId": {"type": "string", "enum": target_ids},
                    "strength": {"type": "number", "minimum": 0.1, "maximum": 1.5},
                    "durationMs": {"type": "integer", "minimum": 400, "maximum": 5000},
                },
                "required": ["name", "targetId", "strength", "durationMs"],
            },
            "interaction": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "verb": {"type": "string", "enum": INTERACTION_VERBS},
                    "targetId": {"type": "string", "enum": target_ids},
                    "partnerPet": {"type": "string"},
                    "durationMs": {"type": "integer", "minimum": 400, "maximum": 6000},
                },
                "required": ["verb", "targetId", "partnerPet", "durationMs"],
            },
            "spell": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "spellName": {"type": "string"},
                    "ops": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "op": {"type": "string", "enum": SPELL_OPS},
                                "targetId": {"type": "string", "enum": spell_targets},
                                "vec": {
                                    "type": "array",
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "items": {"type": "number", "minimum": -6, "maximum": 6},
                                },
                                "factor": {"type": "number", "minimum": 0.25, "maximum": 2.25},
                                "radius": {"type": "number", "minimum": 0.2, "maximum": 7},
                                "strength": {"type": "number", "minimum": -2.5, "maximum": 2.5},
                                "durationMs": {"type": "integer", "minimum": 120, "maximum": 6000},
                                "intensity": {"type": "number", "minimum": 0, "maximum": 100},
                                "color": {"type": "string"},
                            },
                            "required": ["op", "targetId", "durationMs"],
                        },
                    },
                },
                "required": ["spellName", "ops"],
            },
            "newMemory": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "properties": {
                    "concept": {"type": "string"},
                    "meaning": {"type": "string"},
                },
                "required": ["concept", "meaning"],
            },
            "objectRecipe": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "kind": {"type": "string", "enum": OBJECT_KINDS},
                    "shape": {"type": "string", "enum": OBJECT_SHAPES},
                    "color": {"type": "string"},
                    "accentColor": {"type": "string"},
                    "size": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "x": {"type": "number", "minimum": 0.12, "maximum": 1.8},
                            "y": {"type": "number", "minimum": 0.12, "maximum": 1.8},
                            "z": {"type": "number", "minimum": 0.12, "maximum": 1.8},
                        },
                        "required": ["x", "y", "z"],
                    },
                    "radius": {"type": "number", "minimum": 0.08, "maximum": 0.9},
                    "mass": {"type": "number", "minimum": 0.08, "maximum": 4},
                    "affordances": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {"type": "string", "enum": OBJECT_AFFORDANCES},
                    },
                    "tags": {"type": "array", "maxItems": 6, "items": {"type": "string"}},
                    "parts": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "shape": {"type": "string", "enum": ["box", "sphere", "cylinder"]},
                                "color": {"type": "string"},
                                "size": {
                                    "type": "array",
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "items": {"type": "number", "minimum": 0.04, "maximum": 1.8},
                                },
                                "radius": {"type": "number", "minimum": 0.03, "maximum": 0.9},
                                "height": {"type": "number", "minimum": 0.04, "maximum": 1.8},
                                "offset": {
                                    "type": "array",
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "items": {"type": "number", "minimum": -1.4, "maximum": 1.4},
                                },
                                "rotation": {
                                    "type": "array",
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "items": {"type": "number", "minimum": -3.2, "maximum": 3.2},
                                },
                            },
                            "required": ["shape", "color", "offset"],
                        },
                    },
                },
                "required": ["id", "name", "kind", "shape", "color", "size", "mass", "affordances", "tags"],
            },
            "sound": {"type": "string", "enum": profile["sounds"]},
            "soundRecipe": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string"},
                    "gain": {"type": "number", "minimum": 0.05, "maximum": 1.2},
                    "tones": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 6,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "frequency": {"type": "number", "minimum": 80, "maximum": 1800},
                                "offsetMs": {"type": "integer", "minimum": 0, "maximum": 1200},
                                "durationMs": {"type": "integer", "minimum": 24, "maximum": 900},
                                "gain": {"type": "number", "minimum": 0.04, "maximum": 1.0},
                                "wave": {"type": "string", "enum": SOUND_WAVES},
                            },
                            "required": ["frequency", "offsetMs", "durationMs"],
                        },
                    },
                },
                "required": ["label", "tones"],
            },
        },
        "required": ["pet", "speech", "emotion", "animation", "intent", "power", "interaction", "spell", "sound"],
    }


def validate_action(action: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    pet = normalize_pet(action.get("pet") or payload.get("pet"))
    profile = PET_PROFILES[pet]
    power = action.get("power") if isinstance(action.get("power"), dict) else {}
    power_name = str(power.get("name") or profile["powers"][0])
    if power_name not in profile["powers"]:
        power_name = profile["powers"][0]

    target_id = str(power.get("targetId") or target_from_payload(payload))
    if target_id not in target_ids_from_payload(payload):
        target_id = target_from_payload(payload)

    emotion = valid_choice(action.get("emotion"), VALID_EMOTIONS, "happy")
    animation = valid_choice(action.get("animation"), profile["animations"], profile["animations"][0])
    sound = valid_choice(action.get("sound"), profile["sounds"], profile["sounds"][0])
    touch = latest_touch(payload)
    if touch and touch.get("kind") == "pet":
        emotion = "petted"
        animation = "nuzzle" if "nuzzle" in profile["animations"] else animation
        sound = "pet_touch" if "pet_touch" in profile["sounds"] else sound
    elif touch:
        emotion = "startled"
        animation = "startle" if "startle" in profile["animations"] else animation
        sound = "startle" if "startle" in profile["sounds"] else sound

    blendshape = expressive_blendshape(emotion, power_name, touch)
    blendshape.update(clean_blendshape(action.get("blendshape")))

    return {
        "pet": pet,
        "speech": clean_speech(action.get("speech"), payload, power_name),
        "emotion": emotion,
        "animation": animation,
        "intent": str(action.get("intent") or "playful_intervention")[:64],
        "blendshape": blendshape,
        "power": {
            "name": power_name,
            "targetId": target_id,
            "strength": max(0.1, min(1.5, float(power.get("strength") or 0.8))),
            "durationMs": max(400, min(5000, int(power.get("durationMs") or 1800))),
        },
        "interaction": clean_interaction(action.get("interaction"), payload),
        "spell": clean_spell(action.get("spell"), payload, pet, power_name),
        "newMemory": clean_new_memory(action.get("newMemory"), payload),
        "objectRecipe": clean_object_recipe(action.get("objectRecipe"), payload),
        "sound": sound,
        "soundRecipe": clean_sound_recipe(action.get("soundRecipe"), sound, power_name, payload),
    }


def fallback_policy(payload: dict[str, Any]) -> dict[str, Any]:
    pet = normalize_pet(payload.get("pet"))
    profile = PET_PROFILES[pet]
    message = str(payload.get("message") or "").lower()
    forces = payload.get("forces") or []
    scene = payload.get("scene") or {}
    pet_state = scene.get("pet") if isinstance(scene.get("pet"), dict) else {}
    needs = pet_state.get("needs") if isinstance(pet_state.get("needs"), dict) else {}
    audio = payload.get("audio") if isinstance(payload.get("audio"), dict) else {}
    input_audio = audio.get("input") if isinstance(audio.get("input"), dict) else {}
    audio_peak = max(float(audio.get("peak") or 0), float(input_audio.get("peak") or 0))
    audio_rms = max(float(audio.get("rms") or 0), float(input_audio.get("rms") or 0))
    objects = scene.get("objects", [])
    arrangements = detect_scene_arrangements(objects)
    moving_objects = [
        item
        for item in objects
        if float(item.get("speed") or 0) > 0.8 or item.get("moving")
    ]
    berry_target = nearest_object_with_affordance(objects, "eat")
    book_target = nearest_object_with_affordance(objects, "read")
    chair_target = nearest_object_with_affordance(objects, "sit") or nearest_object_with_affordance(objects, "gather")
    waste_target = nearest_object_with_affordance(objects, "recycle") or nearest_object_with_affordance(objects, "clean")
    food_request = any(word in message for word in ["hungry", "hunger", "eat", "berry", "berries", "snack", "food"])
    read_request = any(word in message for word in ["read", "book", "story", "study"])
    social_request = any(word in message for word in ["chair", "sit", "table", "rest", "social"])
    agent_social_request = any(word in message for word in ["talk", "play", "share", "comfort", "gather", "invite", "friend", "partner", "together", "council", "team"])
    social_partner = partner_pet_from_message(payload, pet)
    clean_request = any(word in message for word in ["clean", "tidy", "recycle", "trash", "waste", "paper", "can", "bottle", "peel"])
    sound_request = any(word in message for word in ["sound", "heard", "hear", "listen", "noise", "clap", "sing", "loud"])
    loud_audio = audio_peak > 0.68 or audio_rms > 0.38
    wish_request = any(word in message for word in ["wish", "create", "spawn", "make a", "make me", "add a", "add an", "summon"])
    pickup_request = any(phrase in message for phrase in ["pick up", "pickup", "grab", "hold", "lift the", "take the"])
    carry_request = any(phrase in message for phrase in ["carry", "bring me", "bring the", "fetch", "take it to"])
    walk_request = any(phrase in message for phrase in ["walk around", "walk in circles", "walk the room", "stroll around"])
    run_request = any(phrase in message for phrase in ["run around", "run in circles", "go around", "zoom around", "dash around", "race around"])
    charade_request = any(
        phrase in message
        for phrase in [
            "what did i build",
            "what did i make",
            "what is this",
            "guess",
            "charade",
            "arrangement",
            "pattern",
            "tower",
            "stack",
            "line",
            "parade",
            "huddle",
        ]
    )
    requested_power = requested_power_from_message(pet, message)
    learned = learned_behavior_from_memories(payload, message, objects, pet, profile)
    vision_request = asks_for_vision(message)
    vision_target = vision_target_from_payload(payload, objects) if vision_request else None

    touch = latest_touch(payload)
    power_target_id = target_from_payload(payload)
    speech_override = ""
    spell_override = None
    memory_applied = ""
    vision_applied = ""
    interaction = {"verb": "none", "targetId": target_from_payload(payload), "partnerPet": "", "durationMs": 1200}
    if touch:
        if touch.get("kind") == "pet":
            power_name = "clock_bubble" if pet == "squeaky" else profile["powers"][0]
            emotion = "petted"
            animation = "nuzzle"
        else:
            power_name = "shrink" if pet == "squeaky" else profile["powers"][0]
            emotion = "startled"
            animation = "startle"
    elif walk_request or run_request:
        power_name = "ember_jump" if pet == "fire_boy" else social_power_for(pet, message)
        emotion = "glee"
        animation = "walk" if walk_request and "walk" in profile["animations"] else ("bounce" if "bounce" in profile["animations"] else social_animation_for(pet))
        interaction = {
            "verb": "walk" if walk_request else "run",
            "targetId": target_from_payload(payload),
            "partnerPet": "",
            "durationMs": 4200 if walk_request else 2800,
        }
        power_target_id = "self"
        speech_override = (
            "Me walky loop."
            if pet == "fire_boy" and walk_request
            else ("Me do zoom loop." if pet == "fire_boy" else "I will run a tiny loop.")
        )
        spell_override = {
            "spellName": "tiny room zoom",
            "ops": [
                {"op": "nudge_pet", "targetId": "self", "vec": [0.6, 0.45, 0.4], "durationMs": 460, "color": "#ff9b45"},
                {"op": "spawn_particle", "targetId": "self", "durationMs": 1100, "color": "#ff9b45"},
            ],
        }
    elif pickup_request or carry_request:
        preferred_target = object_from_message(objects, message, preferred={"box", "cube", "block", "toy", "ball"})
        target = preferred_target or nearest_object_with_affordance(objects, "play") or nearest_object_by_distance(objects)
        target_id = str((target or {}).get("id") or target_from_payload(payload))
        verb = "bring" if carry_request and any(word in message for word in ["bring", "fetch"]) else ("carry" if carry_request else "pickup")
        power_name = "ember_jump" if pet == "fire_boy" else social_power_for(pet, message)
        emotion = "focused"
        animation = focus_animation_for(pet)
        interaction = {"verb": verb, "targetId": target_id, "partnerPet": "", "durationMs": 2600}
        power_target_id = target_id
        label = object_label(target or {"id": target_id})
        speech_override = f"Me hold {shorten(label, 18)}." if pet == "fire_boy" else f"I picked up {shorten(label, 22)}."
        spell_override = {
            "spellName": "warm little pickup",
            "ops": [
                {"op": "spawn_particle", "targetId": target_id, "durationMs": 900, "color": "#ffd75a"},
                {"op": "set_light", "targetId": target_id, "intensity": 54, "durationMs": 220, "color": "#ffd75a"},
            ],
        }
    elif requested_power and not (social_partner and agent_social_request):
        power_name = requested_power
        emotion = "focused" if requested_power in {"time_freeze", "rewind", "magnet_pull", "tide_pull"} else "glee"
        animation = focus_animation_for(pet) if emotion == "focused" else social_animation_for(pet)
        target = object_from_message(objects, message)
        if target:
            power_target_id = str(target.get("id") or power_target_id)
    elif learned:
        power_name = str(learned.get("powerName") or profile["powers"][0])
        emotion = str(learned.get("emotion") or "focused")
        animation = str(learned.get("animation") or focus_animation_for(pet))
        interaction = learned.get("interaction") or interaction
        power_target_id = str(learned.get("targetId") or power_target_id)
        speech_override = str(learned.get("speech") or "")
        spell_override = learned.get("spell") if isinstance(learned.get("spell"), dict) else None
        memory_applied = str(learned.get("concept") or "")
    elif vision_target:
        target_id = str(vision_target.get("id") or target_from_payload(payload))
        label = object_label(vision_target)
        distance = vision_target.get("visionDistance", vision_target.get("distanceToPet", "?"))
        power_name = "clock_bubble" if pet == "squeaky" else profile["powers"][0]
        emotion = "curious"
        animation = focus_animation_for(pet)
        interaction = {"verb": "inspect", "targetId": target_id, "partnerPet": "", "durationMs": 2200}
        power_target_id = target_id
        speech_override = f"I see {label} at {distance}m."
        vision_applied = f"agent-view:{target_id}"
        spell_override = {
            "spellName": "agent view focus",
            "ops": [
                {"op": "spawn_particle", "targetId": target_id, "durationMs": 850, "color": "#8bd5e5"},
                {"op": "set_light", "targetId": target_id, "intensity": 48, "durationMs": 260, "color": "#8bd5e5"},
            ],
        }
    elif arrangements and charade_request:
        arrangement = arrangements[0]
        power_name = "clock_bubble" if pet == "squeaky" else profile["powers"][0]
        emotion = "curious"
        animation = focus_animation_for(pet)
        target_id = str((arrangement.get("objectIds") or [target_from_payload(payload)])[0])
        interaction = {"verb": "inspect", "targetId": target_id, "partnerPet": "", "durationMs": 2800}
    elif social_partner and agent_social_request:
        power_name = social_power_for(pet, message)
        emotion = "happy"
        animation = social_animation_for(pet)
        interaction = {
            "verb": social_verb_from_message(message),
            "targetId": str(chair_target.get("id")) if chair_target else target_from_payload(payload),
            "partnerPet": social_partner,
            "durationMs": 3000,
        }
    elif book_target and read_request:
        power_name = "clock_bubble" if pet == "squeaky" else profile["powers"][0]
        emotion = "focused"
        animation = focus_animation_for(pet)
        interaction = {"verb": "read", "targetId": str(book_target.get("id")), "partnerPet": "", "durationMs": 3200}
    elif chair_target and social_request:
        power_name = "clock_bubble" if pet == "squeaky" else profile["powers"][0]
        emotion = "happy"
        animation = social_animation_for(pet)
        interaction = {"verb": "sit", "targetId": str(chair_target.get("id")), "partnerPet": "", "durationMs": 2200}
    elif waste_target and clean_request:
        power_name = "clock_bubble" if pet == "squeaky" else profile["powers"][0]
        emotion = "focused"
        animation = focus_animation_for(pet)
        verb = "recycle" if "recycle" in (waste_target.get("affordances") or []) else "clean"
        interaction = {"verb": verb, "targetId": str(waste_target.get("id")), "partnerPet": "", "durationMs": 2600}
    elif loud_audio or sound_request:
        if pet == "squeaky":
            power_name = "clock_bubble"
        elif pet == "electraica":
            power_name = "lamp_burst"
        elif pet == "fire_boy":
            power_name = "smoke_poof"
        else:
            power_name = "bubble_lift"
        emotion = "startled" if audio_peak > 0.82 else "curious"
        animation = "startle" if emotion == "startled" and "startle" in profile["animations"] else focus_animation_for(pet)
    elif berry_target and (food_request or (float(needs.get("hunger") or 0) > 62 and not read_request and not social_request)):
        power_name = "clock_bubble" if pet == "squeaky" else profile["powers"][0]
        emotion = "glee"
        animation = "tiny_scamper" if pet == "squeaky" else "bounce"
        interaction = {"verb": "eat", "targetId": str(berry_target.get("id")), "partnerPet": "", "durationMs": 1800}
    elif pet == "squeaky":
        if book_target and read_request:
            power_name = "clock_bubble"
            emotion = "focused"
            animation = "trunk_wiggle"
            interaction = {"verb": "read", "targetId": str(book_target.get("id")), "partnerPet": "", "durationMs": 3200}
        elif chair_target and social_request:
            power_name = "clock_bubble"
            emotion = "happy"
            animation = "bounce"
            interaction = {"verb": "sit", "targetId": str(chair_target.get("id")), "partnerPet": "", "durationMs": 2200}
        elif any(word in message for word in ["small", "tiny", "shrink", "little"]):
            power_name = "shrink"
            emotion = "glee"
            animation = "tiny_scamper"
        elif any(word in message for word in ["rewind", "again", "back", "undo"]):
            power_name = "rewind"
            emotion = "focused"
            animation = "trunk_wiggle"
        elif moving_objects or forces or any(word in message for word in ["stop", "freeze", "pause", "time"]):
            power_name = "time_freeze"
            emotion = "focused"
            animation = "trunk_wiggle"
        else:
            power_name = random.choice(["clock_bubble", "shrink", "time_freeze"])
            emotion = random.choice(["happy", "curious", "glee"])
            animation = random.choice(profile["animations"])
    elif pet == "electraica":
        power_name = "magnet_pull" if "metal" in message else "shock"
        emotion = "glee"
        animation = "spark_spin"
    elif pet == "fire_boy":
        power_name = "smoke_poof" if "hide" in message else "fireball"
        emotion = "glee"
        animation = "flame_wiggle"
    else:
        if book_target and read_request:
            power_name = "bubble_lift" if pet == "shark_girl" else profile["powers"][0]
            emotion = "focused"
            animation = "look_left_right"
            interaction = {"verb": "read", "targetId": str(book_target.get("id")), "partnerPet": "", "durationMs": 3000}
        elif chair_target and social_request:
            power_name = "tide_pull" if pet == "shark_girl" else profile["powers"][0]
            emotion = "happy"
            animation = "fin_sway" if pet == "shark_girl" else "bounce"
            interaction = {"verb": "sit", "targetId": str(chair_target.get("id")), "partnerPet": "", "durationMs": 2200}
        else:
            power_name = "bubble_lift" if "float" in message else "wave"
            emotion = "happy"
            animation = "fin_sway"

    object_recipe = heuristic_object_recipe_from_message(payload) if wish_request else None
    speech = line_for_interaction(interaction["verb"]) if interaction["verb"] != "none" else line_for(power_name)
    if speech_override:
        speech = speech_override
    elif object_recipe:
        speech = f"I wished in {object_recipe['name']}."
    elif arrangements and charade_request:
        speech = line_for_arrangement(arrangements[0])
    elif loud_audio or sound_request:
        speech = "I heard that tiny thunder." if audio_peak > 0.82 else "I heard the room."

    action = {
        "pet": pet,
        "speech": speech,
        "emotion": emotion,
        "animation": animation,
        "intent": "memory_transfer" if memory_applied else ("vision_grounded" if vision_applied else "fallback_playful_intervention"),
        "blendshape": expressive_blendshape(emotion, power_name, touch),
        "power": {
            "name": power_name,
            "targetId": power_target_id,
            "strength": 0.9,
            "durationMs": 2200 if power_name == "time_freeze" else 1700,
        },
        "interaction": interaction,
        "spell": spell_override or fallback_spell(power_name, payload, pet),
        "newMemory": heuristic_memory_from_message(payload),
        "objectRecipe": object_recipe,
        "sound": random.choice(profile["sounds"]),
        "soundRecipe": fallback_sound_recipe(power_name, payload),
        "debug": {"policy": "heuristic", "memoryApplied": memory_applied, "visionApplied": vision_applied},
    }
    if touch and touch.get("kind") == "pet":
        action["speech"] = random.choice(
            ["Hehe, warm pat.", "Me feel cozy now.", "Tiny ember happy."]
            if pet == "fire_boy"
            else ["That was a very official pat.", "I accept this tiny kindness.", "My timeline feels softer now."]
        )
        action["sound"] = "pet_touch"
        action["soundRecipe"] = fallback_sound_recipe("pet_touch", payload)
    return action


def model_unavailable_policy(payload: dict[str, Any]) -> dict[str, Any]:
    pet = normalize_pet(payload.get("pet"))
    profile = PET_PROFILES[pet]
    power_name = profile["powers"][0]
    target_id = target_from_payload(payload)
    sound = "purr" if "purr" in profile["sounds"] else profile["sounds"][0]
    return {
        "pet": pet,
        "speech": "zz... connect my model brain.",
        "emotion": "sleepy",
        "animation": profile["animations"][0],
        "intent": "model_unavailable",
        "blendshape": {
            "eye": -0.55,
            "smile": -0.08,
            "mouth": -0.15,
            "brow": 0.2,
            "cheek": 0.1,
            "squash": 0.08,
            "tilt": -0.12,
            "sparkle": -0.35,
        },
        "power": {
            "name": power_name,
            "targetId": target_id,
            "strength": 0.1,
            "durationMs": 600,
        },
        "interaction": {
            "verb": "none",
            "targetId": target_id,
            "partnerPet": "",
            "durationMs": 1200,
        },
        "spell": {
            "spellName": "sleeping transformer",
            "ops": [{"op": "spawn_particle", "targetId": "self", "durationMs": 900, "color": "#b9c1c9"}],
        },
        "newMemory": None,
        "objectRecipe": None,
        "sound": sound,
        "soundRecipe": {
            "label": "sleepy carrier",
            "gain": 0.28,
            "tones": [
                {"frequency": 180, "offsetMs": 0, "durationMs": 220, "gain": 0.32, "wave": "sine"},
                {"frequency": 146, "offsetMs": 160, "durationMs": 280, "gain": 0.2, "wave": "sine"},
            ],
        },
        "debug": {"policy": "model_unavailable"},
    }


def clean_object_recipe(value: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    raw_name = shorten(str(value.get("name") or value.get("id") or "new toy"), 54)
    recipe_id = slugify(str(value.get("id") or raw_name or "new-toy"))
    if not recipe_id:
        recipe_id = "new-toy"
    existing_ids = set(target_ids_from_payload(payload))
    while recipe_id in existing_ids:
        recipe_id = f"{recipe_id[:42]}-new"
        if recipe_id not in existing_ids:
            break

    shape = valid_choice(value.get("shape"), OBJECT_SHAPES, "composite")
    kind = valid_choice(value.get("kind"), OBJECT_KINDS, "toy")
    size = clean_size(value.get("size"), shape)
    radius = clamped_number(value.get("radius"), 0.08, 0.9, max(size["x"], size["y"], size["z"]) * 0.5)
    mass = clamped_number(value.get("mass"), 0.08, 4, 0.9)
    color = clean_hex_color(value.get("color"), "#8bd5e5")
    accent = clean_hex_color(value.get("accentColor"), "#ffd75a")
    affordances = clean_choice_list(value.get("affordances"), OBJECT_AFFORDANCES, ["play", "inspect"])
    tags = clean_text_list(value.get("tags"), [kind, "generated"])
    parts = clean_recipe_parts(value.get("parts"), color, accent)

    return {
        "id": recipe_id[:48],
        "name": raw_name[:54],
        "kind": kind,
        "shape": shape,
        "color": color,
        "accentColor": accent,
        "size": size,
        "radius": radius,
        "mass": mass,
        "affordances": affordances,
        "tags": tags,
        "parts": parts,
    }


def clean_spell(value: Any, payload: dict[str, Any], pet: str, power_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return fallback_spell(power_name, payload, pet)
    spell_name = shorten(str(value.get("spellName") or line_for(power_name))).lower()
    ops = value.get("ops") if isinstance(value.get("ops"), list) else []
    cleaned = [op for op in (clean_spell_op(item, payload) for item in ops[:5]) if op]
    if not cleaned:
        return fallback_spell(power_name, payload, pet)
    return {
        "spellName": spell_name[:54],
        "ops": cleaned,
    }


def clean_spell_op(value: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    op = valid_choice(value.get("op"), SPELL_OPS, "")
    if not op:
        return None
    target_id = str(value.get("targetId") or target_from_payload(payload))
    allowed_targets = set(target_ids_from_payload(payload) + SPELL_TARGETS)
    if target_id not in allowed_targets:
        target_id = target_from_payload(payload)
    cleaned: dict[str, Any] = {
        "op": op,
        "targetId": target_id,
        "durationMs": max(120, min(6000, int(value.get("durationMs") or 900))),
    }
    vec = value.get("vec")
    if isinstance(vec, list) and len(vec) >= 3:
        cleaned["vec"] = [
            max(-6, min(6, float(vec[index] or 0)))
            for index in range(3)
        ]
    if "factor" in value:
        cleaned["factor"] = max(0.25, min(2.25, float(value.get("factor") or 1)))
    if "radius" in value:
        cleaned["radius"] = max(0.2, min(7, float(value.get("radius") or 2.5)))
    if "strength" in value:
        cleaned["strength"] = max(-2.5, min(2.5, float(value.get("strength") or 0)))
    if "intensity" in value:
        cleaned["intensity"] = max(0, min(100, float(value.get("intensity") or 0)))
    if "color" in value:
        color = str(value.get("color") or "")[:16]
        if re.match(r"^#[0-9a-fA-F]{6}$", color):
            cleaned["color"] = color
    return cleaned


def clean_sound_recipe(value: Any, sound: str, power_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return fallback_sound_recipe(sound or power_name, payload)

    raw_tones = value.get("tones") if isinstance(value.get("tones"), list) else []
    tones = []
    for item in raw_tones[:6]:
        if not isinstance(item, dict):
            continue
        frequency = clamped_number(item.get("frequency"), 80, 1800, 440)
        offset_ms = int(clamped_number(item.get("offsetMs"), 0, 1200, len(tones) * 70))
        duration_ms = int(clamped_number(item.get("durationMs"), 24, 900, 120))
        gain = clamped_number(item.get("gain"), 0.04, 1.0, 0.36)
        wave = valid_choice(item.get("wave"), SOUND_WAVES, "sine")
        tones.append({
            "frequency": round(frequency, 1),
            "offsetMs": offset_ms,
            "durationMs": duration_ms,
            "gain": round(gain, 3),
            "wave": wave,
        })

    if not tones:
        return fallback_sound_recipe(sound or power_name, payload)

    label = re.sub(r"[^a-zA-Z0-9 _-]", "", str(value.get("label") or sound or power_name)).strip()[:48]
    return {
        "label": label or "tiny sound",
        "gain": round(clamped_number(value.get("gain"), 0.05, 1.2, 0.72), 3),
        "tones": tones,
    }


def fallback_sound_recipe(seed: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    message = str(payload.get("message") or "").lower()
    audio = payload.get("audio") if isinstance(payload.get("audio"), dict) else {}
    input_audio = audio.get("input") if isinstance(audio.get("input"), dict) else {}
    peak = max(float(audio.get("peak") or 0), float(input_audio.get("peak") or 0))
    key = str(seed or "").lower()

    if "piano" in message:
        return tone_recipe("wished piano plink", [(523, 0, 120, 0.42, "triangle"), (659, 95, 140, 0.38, "triangle"), (784, 205, 170, 0.3, "sine")], 0.74)
    if "drum" in message:
        return tone_recipe("pocket drum thump", [(136, 0, 130, 0.64, "sine"), (92, 80, 220, 0.42, "sine")], 0.8)
    if "clap" in message or peak > 0.82:
        return tone_recipe("startled room ping", [(320, 0, 70, 0.48, "square"), (920, 40, 90, 0.3, "triangle"), (580, 120, 110, 0.24, "sine")], 0.68)

    recipes = {
        "pet_touch": tone_recipe("soft pat chime", [(420, 0, 70, 0.34, "sine"), (680, 52, 120, 0.28, "triangle")], 0.62),
        "clock_chime": tone_recipe("pocket clock song", [(660, 0, 190, 0.3, "sine"), (990, 44, 170, 0.22, "triangle")], 0.72),
        "tick_tock": tone_recipe("tick tock stitch", [(880, 0, 40, 0.35, "square"), (420, 135, 50, 0.28, "square")], 0.58),
        "time_freeze": tone_recipe("frozen second", [(510, 0, 230, 0.25, "sine"), (760, 90, 260, 0.18, "sine")], 0.62),
        "lamp_burst": tone_recipe("lamp applause", [(820, 0, 120, 0.36, "triangle"), (1320, 54, 140, 0.25, "sine"), (1040, 160, 120, 0.2, "triangle")], 0.74),
        "shock": tone_recipe("polite spark glyph", [(1180, 0, 52, 0.42, "square"), (1520, 46, 56, 0.32, "sawtooth"), (860, 96, 80, 0.22, "triangle")], 0.66),
        "fireball": tone_recipe("supervised ember", [(180, 0, 150, 0.42, "sawtooth"), (310, 80, 160, 0.28, "triangle")], 0.68),
        "smoke_poof": tone_recipe("soft curtain hush", [(210, 0, 180, 0.32, "sine"), (160, 120, 260, 0.22, "sine")], 0.55),
        "wave": tone_recipe("plush tide", [(420, 0, 130, 0.28, "sine"), (520, 100, 150, 0.24, "triangle"), (380, 220, 180, 0.18, "sine")], 0.64),
        "bubble_lift": tone_recipe("bubble elevator", [(520, 0, 105, 0.24, "sine"), (690, 94, 125, 0.22, "triangle"), (840, 196, 160, 0.2, "sine")], 0.62),
    }
    return recipes.get(key)


def tone_recipe(label: str, tones: list[tuple[float, int, int, float, str]], gain: float) -> dict[str, Any]:
    return {
        "label": label,
        "gain": gain,
        "tones": [
            {
                "frequency": frequency,
                "offsetMs": offset,
                "durationMs": duration,
                "gain": tone_gain,
                "wave": wave,
            }
            for frequency, offset, duration, tone_gain, wave in tones[:6]
        ],
    }


def fallback_spell(power_name: str, payload: dict[str, Any], pet: str) -> dict[str, Any]:
    target_id = target_from_payload(payload)
    spell_name = {
        "time_freeze": "pocket pause",
        "shrink": "tiny self theorem",
        "rewind": "retake sparkle",
        "clock_bubble": "round second",
        "shock": "polite zap",
        "magnet_pull": "friendly magnet",
        "lamp_burst": "lamp applause",
        "fireball": "supervised comet",
        "ember_jump": "candle hop",
        "smoke_poof": "soft curtain",
        "wave": "plush tide",
        "bubble_lift": "bubble elevator",
        "tide_pull": "room current",
    }.get(power_name, f"{pet} improvises")
    ops_by_power = {
        "time_freeze": [{"op": "freeze", "targetId": target_id, "durationMs": 1800}, {"op": "spawn_particle", "targetId": target_id, "durationMs": 900, "color": "#8bd5e5"}],
        "shrink": [{"op": "scale", "targetId": "self", "factor": 0.62, "durationMs": 1700}, {"op": "spawn_particle", "targetId": "self", "durationMs": 900, "color": "#b4edf2"}],
        "rewind": [{"op": "impulse", "targetId": target_id, "vec": [0, 2.4, -1.2], "durationMs": 600}, {"op": "spawn_particle", "targetId": target_id, "durationMs": 900, "color": "#9ed4ff"}],
        "clock_bubble": [{"op": "attract", "targetId": "all-toys", "radius": 2.8, "strength": -0.35, "durationMs": 1300}, {"op": "spawn_particle", "targetId": "self", "durationMs": 900, "color": "#8bd5e5"}],
        "shock": [{"op": "impulse", "targetId": target_id, "vec": [0.8, 3.8, -0.6], "durationMs": 420}, {"op": "set_light", "targetId": "all-toys", "intensity": 78, "durationMs": 260, "color": "#fff071"}],
        "magnet_pull": [{"op": "attract", "targetId": "all-toys", "radius": 5.5, "strength": 0.9, "durationMs": 1200, "color": "#ffd855"}],
        "lamp_burst": [{"op": "set_light", "targetId": "all-toys", "intensity": 86, "durationMs": 420, "color": "#ffeb91"}, {"op": "spawn_particle", "targetId": target_id, "durationMs": 900, "color": "#ffeb91"}],
        "fireball": [{"op": "impulse", "targetId": target_id, "vec": [1.4, 2.8, -1.4], "durationMs": 520, "color": "#ff704d"}, {"op": "spawn_particle", "targetId": target_id, "durationMs": 900, "color": "#ff704d"}],
        "ember_jump": [{"op": "nudge_pet", "targetId": "self", "vec": [0, 2.2, 0], "durationMs": 420}, {"op": "spawn_particle", "targetId": "self", "durationMs": 900, "color": "#ff9b45"}],
        "smoke_poof": [{"op": "spawn_particle", "targetId": "self", "durationMs": 1100, "color": "#9aa1a2"}, {"op": "attract", "targetId": "all-toys", "radius": 2.2, "strength": -0.25, "durationMs": 700}],
        "wave": [{"op": "impulse", "targetId": "all-toys", "vec": [0, 1.1, 2.6], "durationMs": 620, "color": "#75d7ea"}, {"op": "spawn_particle", "targetId": "all-toys", "durationMs": 900, "color": "#75d7ea"}],
        "bubble_lift": [{"op": "impulse", "targetId": target_id, "vec": [0, 4.4, 0], "durationMs": 640}, {"op": "spawn_particle", "targetId": target_id, "durationMs": 900, "color": "#9aeaf5"}],
        "tide_pull": [{"op": "attract", "targetId": "all-toys", "radius": 6, "strength": 0.52, "durationMs": 1100, "color": "#75d7ea"}],
    }
    return {"spellName": spell_name, "ops": ops_by_power.get(power_name, [{"op": "spawn_particle", "targetId": "self", "durationMs": 900}])}


def heuristic_memory_from_message(payload: dict[str, Any]) -> dict[str, str] | None:
    message = str(payload.get("message") or "").strip()
    lower = message.lower()
    teaching = any(phrase in lower for phrase in ["called ", "remember ", "means ", "never ", "always ", "this is "])
    if not teaching:
        return None
    concept = "player lesson"
    called = re.search(r"\bcalled\s+['\"]?([a-zA-Z0-9 _-]{2,48}?)(?:['\"]|[:.,;!?]|$)", message, re.IGNORECASE)
    if called:
        concept = called.group(1).strip()
    elif rule := re.search(r"\b(?:remember\s+)?(?:this\s+)?rule\s*:\s*([^.,;!?]{2,64})", message, re.IGNORECASE):
        concept = rule.group(1).strip()
    elif remember := re.search(r"\bremember\s+(?:that\s+)?([^.,;!?]{2,64})", message, re.IGNORECASE):
        concept = remember.group(1).strip()
    elif "never" in lower:
        concept = "never " + message.split("never", 1)[1].strip()[:38]
    elif "always" in lower:
        concept = "always " + message.split("always", 1)[1].strip()[:38]
    return {"concept": concept[:48], "meaning": message[:180]}


def learned_behavior_from_memories(
    payload: dict[str, Any],
    message: str,
    objects: list[dict[str, Any]],
    pet: str,
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    if is_teaching_message(message):
        return None
    memories = [item for item in payload.get("memories", []) if isinstance(item, dict)]
    if not memories:
        return None

    for memory in reversed(memories[-8:]):
        concept = str(memory.get("concept") or "").lower().strip()
        meaning = str(memory.get("meaning") or "").lower().strip()
        combined = f"{concept} {meaning}".strip()
        if not combined:
            continue

        domino_lesson = "domino" in combined and any(word in combined for word in ["sacred", "never knock", "never topple", "protect"])
        domino_request = "domino" in message or any(word in message for word in ["knock", "topple", "sacred", "protect"])
        if domino_lesson and domino_request:
            target = object_from_message(objects, message, preferred={"domino"}) or nearest_object_by_kind(objects, "domino")
            target_id = str((target or {}).get("id") or target_from_payload(payload))
            return {
                "concept": concept or "domino lesson",
                "speech": "I remember: dominos are sacred.",
                "emotion": "focused",
                "animation": focus_animation_for(pet),
                "powerName": "clock_bubble" if pet == "squeaky" else profile["powers"][0],
                "targetId": target_id,
                "interaction": {"verb": "inspect", "targetId": target_id, "partnerPet": "", "durationMs": 2400},
                "spell": {
                    "spellName": "sacred domino guard",
                    "ops": [
                        {"op": "freeze", "targetId": target_id, "durationMs": 1300, "color": "#8bd5e5"},
                        {"op": "spawn_particle", "targetId": target_id, "durationMs": 900, "color": "#8bd5e5"},
                    ],
                },
            }

        concept_used = concept and concept in message
        boop_lesson = "boop" in combined or ("gentle" in combined and any(word in combined for word in ["poke", "bounce", "tap"]))
        if concept_used or (boop_lesson and "boop" in message):
            target = object_from_message(objects, message) or nearest_object_with_affordance(objects, "boop") or nearest_object_with_affordance(objects, "play")
            target_id = str((target or {}).get("id") or target_from_payload(payload))
            if boop_lesson:
                return {
                    "concept": concept or "boop",
                    "speech": "I learned booping means gentle bounce.",
                    "emotion": "glee",
                    "animation": social_animation_for(pet),
                    "powerName": "clock_bubble" if pet == "squeaky" else profile["powers"][0],
                    "targetId": target_id,
                    "interaction": {"verb": "play", "targetId": target_id, "partnerPet": "", "durationMs": 1600},
                    "spell": {
                        "spellName": "learned boop bounce",
                        "ops": [
                            {"op": "impulse", "targetId": target_id, "vec": [0, 1.65, 0], "durationMs": 420, "color": "#ffd75a"},
                            {"op": "spawn_particle", "targetId": target_id, "durationMs": 850, "color": "#ffd75a"},
                        ],
                    },
                }
            return {
                "concept": concept,
                "speech": f"I remember {concept[:32]}.",
                "emotion": "focused",
                "animation": focus_animation_for(pet),
                "powerName": "clock_bubble" if pet == "squeaky" else profile["powers"][0],
                "targetId": target_id,
                "interaction": {"verb": "inspect", "targetId": target_id, "partnerPet": "", "durationMs": 1800},
            }
    return None


def is_teaching_message(message: str) -> bool:
    return any(phrase in message for phrase in ["called ", "remember ", "means ", "never ", "always ", "this is ", "rule:"])


def asks_for_vision(message: str) -> bool:
    phrases = [
        "what do you see",
        "what can you see",
        "what are you seeing",
        "look from",
        "agent-view",
        "agent view",
        "your camera",
        "vision",
        "see closest",
        "nearest thing",
        "in front of you",
    ]
    return any(phrase in message for phrase in phrases)


def vision_target_from_payload(payload: dict[str, Any], objects: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_id = {str(item.get("id")): item for item in objects if item.get("id")}
    detected = [
        item
        for item in payload.get("detectedObjects", [])
        if isinstance(item, dict) and item.get("id")
    ]
    detected = sorted(detected, key=lambda item: float(item.get("distance") or 999))
    for item in detected:
        target = dict(by_id.get(str(item.get("id"))) or {})
        if not target:
            target = {
                "id": item.get("id"),
                "kind": item.get("kind") or "object",
                "name": item.get("id"),
                "distanceToPet": item.get("distance"),
            }
        target["visionDistance"] = round(float(item.get("distance") or target.get("distanceToPet") or 0), 2)
        target["visionMoving"] = bool(item.get("moving"))
        return target
    if not objects:
        return None
    target = sorted(objects, key=lambda item: float(item.get("distanceToPet") or 999))[0]
    fallback = dict(target)
    fallback["visionDistance"] = round(float(target.get("distanceToPet") or 0), 2)
    return fallback


def object_from_message(
    objects: list[dict[str, Any]],
    message: str,
    preferred: set[str] | None = None,
) -> dict[str, Any] | None:
    preferred = preferred or set()
    best: tuple[int, float, dict[str, Any]] | None = None
    for item in objects:
        fields = [
            str(item.get("id") or ""),
            str(item.get("kind") or ""),
            str(item.get("name") or ""),
            " ".join(str(value) for value in item.get("tags", []) if value),
            " ".join(str(value) for value in item.get("affordances", []) if value),
        ]
        normalized = " ".join(fields).lower().replace("-", " ")
        score = 0
        if preferred and any(word in normalized for word in preferred):
            score += 5
        for token in set(re.findall(r"[a-z0-9]+", message)):
            if len(token) >= 3 and token in normalized:
                score += 1
        if score <= 0:
            continue
        distance = float(item.get("distanceToPet") or 999)
        candidate = (score, -distance, item)
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    return best[2] if best else None


def nearest_object_by_kind(objects: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    matches = [item for item in objects if str(item.get("kind") or "").lower() == kind]
    if not matches:
        return None
    return sorted(matches, key=lambda item: float(item.get("distanceToPet") or 999))[0]


def heuristic_object_recipe_from_message(payload: dict[str, Any]) -> dict[str, Any]:
    message = str(payload.get("message") or "").lower()
    if "piano" in message:
        name = "tiny piano"
        recipe = {
            "id": "wish-tiny-piano",
            "name": name,
            "kind": "instrument",
            "shape": "composite",
            "color": "#1d2424",
            "accentColor": "#fff1c8",
            "size": {"x": 0.9, "y": 0.42, "z": 0.46},
            "mass": 1.1,
            "affordances": ["music", "play", "inspect", "gather"],
            "tags": ["piano", "music", "generated"],
            "parts": [
                {"shape": "box", "color": "#1d2424", "size": [0.84, 0.3, 0.4], "offset": [0, 0, 0]},
                {"shape": "box", "color": "#fff1c8", "size": [0.62, 0.045, 0.16], "offset": [0, 0.19, 0.13]},
                {"shape": "box", "color": "#1d2424", "size": [0.08, 0.08, 0.18], "offset": [-0.24, 0.23, 0.13]},
                {"shape": "box", "color": "#1d2424", "size": [0.08, 0.08, 0.18], "offset": [0.0, 0.23, 0.13]},
                {"shape": "box", "color": "#1d2424", "size": [0.08, 0.08, 0.18], "offset": [0.24, 0.23, 0.13]},
            ],
        }
    elif "drum" in message:
        recipe = {
            "id": "wish-pocket-drum",
            "name": "pocket drum",
            "kind": "instrument",
            "shape": "cylinder",
            "color": "#d95b59",
            "accentColor": "#fff1c8",
            "size": {"x": 0.48, "y": 0.44, "z": 0.48},
            "radius": 0.24,
            "mass": 0.78,
            "affordances": ["music", "play", "inspect", "throw"],
            "tags": ["drum", "music", "generated"],
            "parts": [
                {"shape": "cylinder", "color": "#d95b59", "radius": 0.24, "height": 0.36, "offset": [0, 0, 0]},
                {"shape": "cylinder", "color": "#fff1c8", "radius": 0.25, "height": 0.035, "offset": [0, 0.2, 0]},
                {"shape": "cylinder", "color": "#fff1c8", "radius": 0.25, "height": 0.035, "offset": [0, -0.2, 0]},
            ],
        }
    elif "plant" in message or "flower" in message:
        recipe = {
            "id": "wish-moon-flower",
            "name": "moon flower",
            "kind": "plant",
            "shape": "composite",
            "color": "#6bbf75",
            "accentColor": "#d7eee8",
            "size": {"x": 0.48, "y": 0.76, "z": 0.48},
            "mass": 0.8,
            "affordances": ["sniff", "water", "inspect"],
            "tags": ["plant", "flower", "generated"],
            "parts": [
                {"shape": "cylinder", "color": "#c9794b", "radius": 0.17, "height": 0.24, "offset": [0, -0.24, 0]},
                {"shape": "cylinder", "color": "#3f7d4c", "radius": 0.035, "height": 0.42, "offset": [0, 0.0, 0]},
                {"shape": "sphere", "color": "#d7eee8", "radius": 0.14, "offset": [0, 0.27, 0]},
                {"shape": "sphere", "color": "#6bbf75", "radius": 0.1, "offset": [-0.13, 0.12, 0]},
                {"shape": "sphere", "color": "#6bbf75", "radius": 0.1, "offset": [0.13, 0.1, 0]},
            ],
        }
    else:
        item = object_name_from_wish(message)
        recipe = {
            "id": f"wish-{slugify(item)}",
            "name": item,
            "kind": "toy",
            "shape": "composite",
            "color": "#8bd5e5",
            "accentColor": "#ffd75a",
            "size": {"x": 0.58, "y": 0.48, "z": 0.58},
            "mass": 0.72,
            "affordances": ["play", "inspect", "throw"],
            "tags": [item[:28], "generated"],
            "parts": [
                {"shape": "box", "color": "#8bd5e5", "size": [0.52, 0.34, 0.52], "offset": [0, 0, 0]},
                {"shape": "sphere", "color": "#ffd75a", "radius": 0.13, "offset": [0.0, 0.24, 0.0]},
                {"shape": "sphere", "color": "#fff1c8", "radius": 0.06, "offset": [-0.16, 0.08, 0.28]},
                {"shape": "sphere", "color": "#fff1c8", "radius": 0.06, "offset": [0.16, 0.08, 0.28]},
            ],
        }
    return clean_object_recipe(recipe, payload) or recipe


def object_name_from_wish(message: str) -> str:
    patterns = [
        r"\b(?:wish|wished)\s+(?:for\s+)?(?:a|an|the)?\s*([a-z0-9 -]{2,42})",
        r"\b(?:create|spawn|summon|add|make)\s+(?:me\s+)?(?:a|an|the)?\s*([a-z0-9 -]{2,42})",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            name = re.sub(r"\b(in|inside|for|with|and|please)\b.*$", "", match.group(1)).strip(" .,!?:;")
            if name:
                return shorten(name, 42).lower()
    return "mystery toy"


def clean_size(value: Any, shape: str) -> dict[str, float]:
    if isinstance(value, dict):
        default = 0.46 if shape == "sphere" else 0.58
        return {
            "x": clamped_number(value.get("x"), 0.12, 1.8, default),
            "y": clamped_number(value.get("y"), 0.12, 1.8, default),
            "z": clamped_number(value.get("z"), 0.12, 1.8, default),
        }
    return {"x": 0.58, "y": 0.5, "z": 0.58}


def clean_recipe_parts(value: Any, color: str, accent: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    parts = []
    for item in value[:6]:
        if not isinstance(item, dict):
            continue
        shape = valid_choice(item.get("shape"), ["box", "sphere", "cylinder"], "box")
        part: dict[str, Any] = {
            "shape": shape,
            "color": clean_hex_color(item.get("color"), accent if len(parts) % 2 else color),
            "offset": clean_vector(item.get("offset"), -1.4, 1.4, [0, 0, 0]),
            "rotation": clean_vector(item.get("rotation"), -3.2, 3.2, [0, 0, 0]),
        }
        if shape == "box":
            part["size"] = clean_vector(item.get("size"), 0.04, 1.8, [0.32, 0.24, 0.32])
        elif shape == "sphere":
            part["radius"] = clamped_number(item.get("radius"), 0.03, 0.9, 0.16)
        else:
            part["radius"] = clamped_number(item.get("radius"), 0.03, 0.9, 0.14)
            part["height"] = clamped_number(item.get("height"), 0.04, 1.8, 0.32)
        parts.append(part)
    return parts


def clean_vector(value: Any, low: float, high: float, fallback: list[float]) -> list[float]:
    if not isinstance(value, list) or len(value) < 3:
        return fallback
    return [clamped_number(value[index], low, high, fallback[index]) for index in range(3)]


def clean_choice_list(value: Any, choices: list[str], fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    cleaned = []
    for item in value[:6]:
        text = valid_choice(item, choices, "")
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned or fallback


def clean_text_list(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    cleaned = []
    for item in value[:6]:
        text = re.sub(r"[^a-zA-Z0-9 _-]", "", str(item or "")).strip().lower()[:32]
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned or fallback


def clean_hex_color(value: Any, fallback: str) -> str:
    color = str(value or "").strip()[:16]
    return color if re.match(r"^#[0-9a-fA-F]{6}$", color) else fallback


def clamped_number(value: Any, low: float, high: float, fallback: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return fallback


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:48]


def clean_interaction(value: Any, payload: dict[str, Any]) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    verb = valid_choice(raw.get("verb"), INTERACTION_VERBS, "none")
    target_id = str(raw.get("targetId") or target_from_payload(payload))
    if target_id not in target_ids_from_payload(payload):
        target_id = target_from_payload(payload)
    if verb == "eat":
        scene = payload.get("scene") or {}
        objects = scene.get("objects") or []
        target = next((item for item in objects if str(item.get("id")) == target_id), None)
        affordances = target.get("affordances") if isinstance(target, dict) else []
        if not target or (target.get("kind") not in {"berry", "food"} and "eat" not in affordances):
            berry_target = nearest_object_with_affordance(objects, "eat")
            if berry_target:
                target_id = str(berry_target.get("id"))
            else:
                verb = "none"
    return {
        "verb": verb,
        "targetId": target_id,
        "partnerPet": normalize_partner_pet(str(raw.get("partnerPet") or "")),
        "durationMs": max(400, min(6000, int(raw.get("durationMs") or 1600))),
    }


def partner_pet_from_message(payload: dict[str, Any], pet: str) -> str:
    message = str(payload.get("message") or "").lower()
    aliases = {
        "squeaky": ["squeaky", "elephant", "time"],
        "fire_boy": ["fire boy", "fire_boy", "fireboy", "fire"],
        "shark_girl": ["shark girl", "shark_girl", "sharkgirl", "shark"],
        "electraica": ["electraica", "electricia", "electric", "electric girl", "lightning"],
    }
    for kind, names in aliases.items():
        if kind == pet:
            continue
        if any(name in message for name in names):
            return kind

    if not any(word in message for word in ["friend", "partner", "another", "other", "together", "council", "team", "someone"]):
        return ""
    scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else {}
    agents = scene.get("agents") if isinstance(scene.get("agents"), list) else []
    candidates = [
        item
        for item in agents
        if isinstance(item, dict) and normalize_partner_pet(str(item.get("pet") or "")) and normalize_partner_pet(str(item.get("pet") or "")) != pet
    ]
    if candidates:
        closest = sorted(candidates, key=lambda item: float(item.get("distanceToPet") or 999))[0]
        return normalize_partner_pet(str(closest.get("pet") or ""))
    return next((kind for kind in PET_PROFILES if kind != pet), "")


def normalize_partner_pet(value: str) -> str:
    key = value.lower().replace("-", "_").replace(" ", "_")[:48]
    aliases = {
        "fireboy": "fire_boy",
        "fire": "fire_boy",
        "sharkgirl": "shark_girl",
        "shark": "shark_girl",
        "electricia": "electraica",
        "electric": "electraica",
    }
    key = aliases.get(key, key)
    return key if key in PET_PROFILES else ""


def social_power_for(pet: str, message: str) -> str:
    if pet == "squeaky":
        return "time_freeze" if any(word in message for word in ["pause", "freeze", "wait"]) else "clock_bubble"
    if pet == "electraica":
        return "magnet_pull" if "magnet" in message else "lamp_burst"
    if pet == "fire_boy":
        return "smoke_poof" if "hide" in message else "ember_jump"
    if pet == "shark_girl":
        if "bubble" in message or "lift" in message:
            return "bubble_lift"
        if "tide" in message or "pull" in message:
            return "tide_pull"
        return "wave"
    return PET_PROFILES[pet]["powers"][0]


def social_verb_from_message(message: str) -> str:
    if "comfort" in message or "help" in message:
        return "comfort"
    if "share" in message:
        return "share"
    if "gather" in message or "council" in message or "team" in message:
        return "gather"
    if "talk" in message:
        return "talk"
    return "play"


def nearest_object_with_affordance(objects: list[dict[str, Any]], affordance: str) -> dict[str, Any] | None:
    matches = [
        item
        for item in objects
        if affordance in (item.get("affordances") or [])
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda item: float(item.get("distanceToPet") or 999))[0]


def nearest_object_by_distance(objects: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not objects:
        return None
    return sorted(objects, key=lambda item: float(item.get("distanceToPet") or 999))[0]


def requested_power_from_message(pet: str, message: str) -> str:
    aliases = {
        "time freeze": "time_freeze",
        "freeze": "time_freeze",
        "tiny self": "shrink",
        "small mode": "shrink",
        "clock bubble": "clock_bubble",
        "fire ball": "fireball",
        "ember": "ember_jump",
        "ember jump": "ember_jump",
        "smoke": "smoke_poof",
        "smoke poof": "smoke_poof",
        "bubble": "bubble_lift" if pet == "shark_girl" else "clock_bubble",
        "bubble lift": "bubble_lift",
        "tide": "tide_pull",
        "tide pull": "tide_pull",
        "lamp": "lamp_burst",
        "lamp burst": "lamp_burst",
        "magnet": "magnet_pull",
        "zap": "shock",
        "spark": "shock",
    }
    allowed = set(PET_PROFILES[pet]["powers"])
    for power in PET_PROFILES[pet]["powers"]:
        if power in message or power.replace("_", " ") in message:
            return power
    for phrase, power in aliases.items():
        if phrase in message and power in allowed:
            return power
    return ""


def line_for_interaction(verb: str) -> str:
    lines = {
        "eat": ["Berry quest accepted.", "Tiny snack located.", "My tummy chose this berry."],
        "read": ["Story inspection begins.", "I found a book-shaped thought.", "Reading with tiny seriousness."],
        "sit": ["A small sit seems wise.", "Chair time, very official.", "I found the gathering spot."],
        "gather": ["Everyone should meet here.", "Tiny table conference.", "This spot feels friendly."],
        "sniff": ["Leaf smells like quiet.", "I am politely sniffing.", "This plant has secrets."],
        "inspect": ["Tiny inspection mode.", "I found a curious thing.", "Let me study this."],
        "water": ["Sip for the leaves.", "Plant care protocol.", "A little drink for green friends."],
        "share": ["I can share this.", "Tiny generosity activated.", "A snack for friendship."],
        "clean": ["Tidying the tiny mess.", "Cleanup spell, very practical.", "I found a small chore."],
        "recycle": ["Recycle quest accepted.", "This belongs in the blue bin.", "Tiny cleanup crew, reporting."],
        "play": ["Play protocol engaged.", "A tiny game begins.", "I found the fun part."],
        "comfort": ["Soft comfort delivered.", "I will be gentle here.", "Tiny care mode."],
        "talk": ["Tiny conversation time.", "I have words for my friend.", "Council voice activated."],
        "pickup": ["Me got it.", "Tiny pickup job.", "I can hold this."],
        "carry": ["Carry mode, careful feet.", "I will move it gently.", "Tiny delivery paws."],
        "bring": ["I bring it close.", "Delivery coming softly.", "I fetched the toy."],
        "walk": ["Me walky loop.", "Tiny feet go slow.", "I walk around now."],
        "run": ["Zoom loop time.", "Tiny feet go fast.", "I run around now."],
    }
    return random.choice(lines.get(verb, ["I found a tiny plan."]))


def line_for_arrangement(arrangement: dict[str, Any]) -> str:
    label = str(arrangement.get("label") or "toy pattern")
    lines = {
        "stack": [f"Is this a {label}?", "I see a careful little tower.", "That stack looks intentional."],
        "line": [f"That looks like a {label}.", "I see a parade of tiny things.", "This line has marching energy."],
        "cluster": [f"Is this a {label}?", "The toys are huddling together.", "This looks like a meeting pile."],
        "generated_object": ["I recognize the wished toy.", "The new toy is part of the story.", "That made object is now real here."],
    }
    return random.choice(lines.get(str(arrangement.get("kind") or ""), [f"I think this is a {label}."]))


def focus_animation_for(pet: str) -> str:
    if pet == "squeaky":
        return "trunk_wiggle"
    if pet == "electraica":
        return "spark_spin"
    if pet == "fire_boy":
        return "flame_wiggle"
    return "fin_sway"


def social_animation_for(pet: str) -> str:
    if pet == "shark_girl":
        return "fin_sway"
    return "bounce"


def clean_blendshape(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    cleaned = {}
    for key in FACE_BLENDSHAPE_KEYS:
        if key in value:
            cleaned_value = clamped_float(value[key])
            if cleaned_value is not None:
                cleaned[key] = cleaned_value
    return cleaned


def expressive_blendshape(emotion: str, power_name: str, touch: dict[str, Any] | None = None) -> dict[str, float]:
    if touch and touch.get("kind") == "pet":
        return {"eye": 0.48, "smile": 1.1, "cheek": 1.35, "squash": 0.2, "tilt": -0.18, "sparkle": 1.1}
    if touch:
        return {"eye": 1.45, "mouth": 0.72, "brow": 0.8, "squash": -0.08, "tilt": 0.22, "sparkle": 0.95}
    if power_name in {"time_freeze", "rewind", "magnet_pull"} or emotion == "focused":
        return {"eye": 0.88, "smile": 0.12, "brow": -0.58, "cheek": 0.66, "sparkle": 0.25}
    if power_name in {"shock", "fireball", "ember_jump", "wave"}:
        return {"eye": 1.24, "smile": 0.82, "mouth": 0.22, "cheek": 1.05, "squash": 0.12, "sparkle": 1.2}
    if emotion == "curious":
        return {"eye": 1.1, "smile": 0.42, "brow": 0.3, "tilt": -0.12, "sparkle": 0.58}
    return {"eye": 0.96, "smile": 0.76, "cheek": 0.86, "sparkle": 0.5}


def clamped_float(value: Any) -> float | None:
    try:
        return max(-1.5, min(1.5, float(value or 0)))
    except (TypeError, ValueError):
        return None


def clean_speech(value: Any, payload: dict[str, Any], power_name: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().strip('"')
    words = text.split()
    bad_fragments = [
        "schema",
        "json",
        "instruction",
        "allowed",
        "traits:",
        "user_message",
        "the user",
        "i petted",
        "i'll pet",
        "i will pet",
        "pet you",
        "gently pet you",
    ]
    if not text or len(words) > 12 or any(fragment in text.lower() for fragment in bad_fragments):
        touch = latest_touch(payload)
        if touch and touch.get("kind") == "pet":
            if normalize_pet(payload.get("pet")) == "fire_boy":
                text = random.choice(["Hehe, warm pat.", "Me feel cozy now.", "Tiny ember happy."])
            else:
                text = random.choice(["That pat fixed my tiny timeline.", "I feel very officially petted.", "My little clock-heart softened."])
        elif touch:
            if normalize_pet(payload.get("pet")) == "fire_boy":
                text = random.choice(["Oop! Tiny jump.", "Me got booped.", "Careful, lil spark."])
            else:
                text = random.choice(["Oh! Tiny startle sparkle.", "I jumped a very small amount.", "Careful, my whiskers heard that."])
        else:
            text = line_for(power_name)
    elif latest_touch(payload) and latest_touch(payload).get("kind") == "pet":
        lower = text.lower()
        if not any(word in lower for word in ["pat", "pet", "touch", "soft", "kind"]):
            if normalize_pet(payload.get("pet")) == "fire_boy":
                text = random.choice(["Hehe, warm pat.", "Me feel cozy now.", "Tiny ember happy."])
            else:
                text = random.choice(["That pat fixed my tiny timeline.", "I feel very officially petted.", "My little clock-heart softened."])
    if normalize_pet(payload.get("pet")) == "fire_boy":
        text = fire_boy_baby_speech(text, power_name)
    return shorten(text)


def fire_boy_baby_speech(text: str, power_name: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    lower = clean.lower()
    if re.search(r"\b(me|tiny|lil|hehe|boop|baby|warm)\b", lower) and len(clean) <= 64:
        return clean
    if any(word in lower for word in ["walk", "stroll", "patrol"]):
        return "Me walky loop."
    if any(word in lower for word in ["run", "zoom", "dash", "race"]):
        return "Me do zoom loop."
    if any(word in lower for word in ["pick", "pickup", "hold", "carry", "bring", "fetch", "grab"]):
        return "Me hold it, hehe."
    if power_name == "fireball" or any(word in lower for word in ["fireball", "comet", "whoosh"]):
        return "Me make warm sparkle."
    if power_name == "smoke_poof" or "smoke" in lower or "poof" in lower:
        return "Poof, hidey cloud."
    if power_name == "ember_jump" or any(word in lower for word in ["jump", "hop", "bounce"]):
        return "Boop, warm hop."
    return "Me tiny Fire Boy."


def shorten(text: str, max_words: int = 18) -> str:
    words = re.sub(r"\s+", " ", text).strip().split(" ")
    return " ".join(words[:max_words])
