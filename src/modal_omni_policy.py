from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.parse import urlparse, urlunparse

from src.model_policy import attach_model_debug, elapsed_ms, extract_json
from src.pet_actions import validate_action
from src.pet_payload import compact_payload, object_label, target_from_payload, target_ids_from_payload
from src.pet_profiles import PET_PROFILES, VALID_EMOTIONS, normalize_pet
from src.vision_policy import image_base64


DEFAULT_MODAL_MODEL = "openbmb/MiniCPM-o-4_5"


def modal_omni_action_configured() -> bool:
    return os.getenv("TOYBOX_MODAL_OMNI_ACTION", "").lower() in {"1", "true", "yes"}


def modal_omni_base_url() -> str:
    return os.getenv("TOYBOX_MODAL_OMNI_URL", "").strip().rstrip("/")


def modal_omni_model() -> str:
    return os.getenv("TOYBOX_MODAL_OMNI_MODEL", DEFAULT_MODAL_MODEL).strip() or DEFAULT_MODAL_MODEL


def try_modal_omni_policy(payload: dict[str, Any]) -> dict[str, Any] | None:
    base_url = modal_omni_base_url()
    if not modal_omni_action_configured() or not base_url:
        return None

    try:
        from websockets.sync.client import connect
    except Exception:
        return None

    started = time.perf_counter()
    ws_url = modal_omni_ws_url(base_url)
    prompt_payload = compact_payload(payload)
    pet = normalize_pet(prompt_payload.get("pet"))
    content = modal_user_content(prompt_payload, payload)
    response_text = ""
    usage: dict[str, Any] = {}
    event_count = 0

    try:
        with connect(
            ws_url,
            open_timeout=float(os.getenv("TOYBOX_MODAL_OMNI_CONNECT_TIMEOUT", "45")),
            close_timeout=2,
            compression=None,
            user_agent_header="Codex-Toy-Room/3 Modal-MiniCPM",
        ) as websocket:
            websocket.send(json.dumps(modal_chat_payload(content, pet)))
            deadline = time.monotonic() + float(os.getenv("TOYBOX_MODAL_OMNI_TIMEOUT", "120"))
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Modal MiniCPM-o action timed out")
                raw = websocket.recv(timeout=remaining)
                event_count += 1
                message = json.loads(raw)
                event_type = message.get("type")
                if event_type == "prefill_done":
                    usage["prompt_tokens"] = message.get("input_tokens")
                    continue
                if event_type == "chunk":
                    response_text += str(message.get("text_delta") or "")
                    continue
                if event_type == "done":
                    response_text = str(message.get("text") or response_text)
                    usage["prompt_tokens"] = message.get("input_tokens", usage.get("prompt_tokens"))
                    usage["completion_tokens"] = message.get("generated_tokens")
                    usage["modalRecordingSessionId"] = message.get("recording_session_id")
                    break
                if event_type == "error":
                    raise RuntimeError(str(message.get("error") or "Modal MiniCPM-o returned an error"))

        action = validate_action(extract_json(response_text), payload)
        coerce_modal_command_action(action, payload)
        debugged = attach_model_debug(
            action,
            modal_omni_model(),
            provider="modal",
            latency_ms=elapsed_ms(started),
            usage=usage,
        )
        debug = debugged.setdefault("debug", {})
        if isinstance(debug, dict):
            debug["policy"] = "modal_omni_action"
            debug["modalOmni"] = True
            debug["modalBaseUrl"] = base_url
            debug["modalWsPath"] = "/ws/chat"
            debug["modalEvents"] = event_count
            debug["functionCalls"] = 1
            debug["stateUpdatesRequested"] = 1
            if usage.get("modalRecordingSessionId"):
                debug["modalRecordingSessionId"] = usage["modalRecordingSessionId"]
        return debugged
    except Exception as exc:
        if os.getenv("TOYBOX_MODAL_OMNI_DEBUG", "").lower() in {"1", "true", "yes"}:
            print(f"Modal MiniCPM-o action policy failed: {str(exc)[:360]}", flush=True)
        return None


def modal_omni_ws_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, "/ws/chat", "", "", ""))


def modal_chat_payload(content: str | list[dict[str, Any]], pet: str) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": modal_system_prompt(pet)},
            {"role": "user", "content": content},
        ],
        "streaming": True,
        "generation": {
            "max_new_tokens": int(os.getenv("TOYBOX_MODAL_OMNI_MAX_TOKENS", "520")),
            "temperature": float(os.getenv("TOYBOX_MODAL_OMNI_TEMPERATURE", "0.2")),
            "top_p": float(os.getenv("TOYBOX_MODAL_OMNI_TOP_P", "0.8")),
        },
        "tts": {"enabled": False, "mode": "text_only"},
        "image": {"max_slice_nums": None, "use_image_id": True},
        "omni_mode": False,
        "enable_thinking": False,
    }


def modal_user_content(prompt_payload: dict[str, Any], payload: dict[str, Any]) -> str | list[dict[str, Any]]:
    text = modal_action_prompt(prompt_payload, payload)
    camera_frame = payload.get("cameraFrame")
    send_image = os.getenv("TOYBOX_MODAL_OMNI_SEND_IMAGE", "1").lower() not in {"0", "false", "no"}
    if send_image and isinstance(camera_frame, str) and camera_frame.startswith("data:image/"):
        return [
            {"type": "text", "text": text},
            {"type": "image", "data": image_base64(camera_frame)},
        ]
    return text


def modal_system_prompt(pet: str) -> str:
    profile = PET_PROFILES[pet]
    return (
        "You are MiniCPM-o running on Modal and controlling a Three.js virtual pet. "
        "You are the action brain, not a chatbot. Read the command, toy-room state, and optional image. "
        "Return only one valid JSON object. No markdown, no explanations, no chain-of-thought. "
        f"Pet profile: {profile['name']} is {profile['traits']}. "
        "For Fire Boy, speech is a babyish warm toy voice under 10 words."
    )


def modal_action_prompt(prompt_payload: dict[str, Any], payload: dict[str, Any]) -> str:
    pet = normalize_pet(prompt_payload.get("pet"))
    profile = PET_PROFILES[pet]
    object_lines = [
        (
            f"- {item.get('id')}: {object_label(item)} kind={item.get('kind')} "
            f"distance={item.get('distanceToPet')} affordances={','.join(item.get('affordances') or []) or 'none'} "
            f"tags={','.join(item.get('tags') or []) or 'none'}"
        )
        for item in (prompt_payload.get("objects") or [])[:12]
    ]
    target_id = target_from_payload(payload)
    target_ids = target_ids_from_payload(payload)
    allowed = {
        "pet": pet,
        "emotions": VALID_EMOTIONS,
        "animations": profile["animations"],
        "powers": profile["powers"],
        "interactionVerbs": ["none", "pickup", "carry", "bring", "walk", "run", "inspect", "play", "talk", "sit", "read", "eat"],
        "targetIds": target_ids,
        "defaultTargetId": target_id,
    }
    return "\n".join(
        [
            "Choose one immediate visible pet action for the renderer.",
            f"User command: {prompt_payload.get('user_message') or '(ambient update)'}",
            f"Allowed/action vocabulary: {json.dumps(allowed, ensure_ascii=True)}",
            "Objects near the pet:",
            "\n".join(object_lines) if object_lines else "- none",
            f"Detected visual objects: {json.dumps(prompt_payload.get('detectedObjects') or [], ensure_ascii=True)[:1000]}",
            f"Recent interactions: {json.dumps(prompt_payload.get('interactions') or [], ensure_ascii=True)[:1200]}",
            f"Needs: {json.dumps(prompt_payload.get('needs') or {}, ensure_ascii=True)}",
            "Decision rules:",
            "- 'walk around' -> interaction.verb='walk', animation='walk', power.name='ember_jump', targetId must be listed.",
            "- 'run around' -> interaction.verb='run', animation='run', power.name='ember_jump'.",
            "- 'pick up/grab/hold the box' -> interaction.verb='pickup' and target the box object id.",
            "- 'bring/fetch/carry' -> interaction.verb='bring' or 'carry'.",
            "- 'fireball' -> power.name='fireball' and use a visible spell with spawn_particle.",
            "- ordinary looking or camera questions -> interaction.verb='inspect'.",
            "Return one JSON object with these keys: pet, speech, emotion, animation, intent, blendshape, power, interaction, spell, newMemory, objectRecipe, sound, soundRecipe.",
            "power must contain name, targetId, strength, durationMs. interaction must contain verb, targetId, partnerPet, durationMs.",
            "spell must contain spellName and ops. Ops use op in impulse/freeze/scale/attract/spawn_particle/set_light/nudge_pet, targetId, durationMs, and optional vec/factor/radius/strength/intensity/color.",
            "Use null for newMemory, objectRecipe, or soundRecipe unless the command specifically teaches, creates an object, or needs a custom sound.",
            "Use command-specific values. Do not copy a walk action unless the player asked to walk.",
        ]
    )


def coerce_modal_command_action(action: dict[str, Any], payload: dict[str, Any]) -> None:
    message = str(payload.get("message") or "").lower()
    pet = normalize_pet(action.get("pet") or payload.get("pet"))
    if pet != "fire_boy":
        return
    if any(phrase in message for phrase in ["walk around", "walk in circles", "walk the room", "stroll around"]):
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
    elif any(phrase in message for phrase in ["run around", "run in circles", "zoom around", "dash around", "race around"]):
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
