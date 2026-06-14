from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.parse import urlparse, urlunparse

from src.command_coercion import coerce_fireboy_command_action
from src.model_policy import attach_model_debug, elapsed_ms, extract_json
from src.pet_actions import validate_action
from src.pet_payload import compact_payload, object_label, target_from_payload, target_ids_from_payload
from src.pet_profiles import PET_PROFILES, VALID_EMOTIONS, normalize_pet
from src.vision_policy import image_base64


DEFAULT_MODAL_MODEL = "openbmb/MiniCPM-o-4_5"
_LAST_MODAL_ERROR: dict[str, Any] = {}


def modal_omni_action_configured() -> bool:
    return os.getenv("TOYBOX_MODAL_OMNI_ACTION", "").lower() in {"1", "true", "yes"}


def modal_omni_base_url() -> str:
    return os.getenv("TOYBOX_MODAL_OMNI_URL", "").strip().rstrip("/")


def modal_omni_model() -> str:
    return os.getenv("TOYBOX_MODAL_OMNI_MODEL", DEFAULT_MODAL_MODEL).strip() or DEFAULT_MODAL_MODEL


def warm_modal_omni_health() -> dict[str, Any] | None:
    base_url = modal_omni_base_url()
    if not modal_omni_action_configured() or not base_url:
        return None
    try:
        import httpx

        started = time.perf_counter()
        response = httpx.get(
            f"{base_url}/health",
            timeout=float(os.getenv("TOYBOX_MODAL_OMNI_WARMUP_TIMEOUT", "45")),
        )
        return {"ok": response.is_success, "statusCode": response.status_code, "latencyMs": elapsed_ms(started)}
    except Exception as exc:
        return {"ok": False, "errorType": type(exc).__name__, "error": str(exc)[:180]}


def modal_omni_last_error() -> dict[str, Any]:
    return dict(_LAST_MODAL_ERROR)


def try_modal_omni_policy(payload: dict[str, Any]) -> dict[str, Any] | None:
    global _LAST_MODAL_ERROR
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
    content, image_sent = modal_user_content(prompt_payload, payload)
    response_text = ""
    usage: dict[str, Any] = {}
    event_count = 0
    _LAST_MODAL_ERROR = {}

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
        coerce_fireboy_command_action(action, payload)
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
            debug["modalImageSent"] = image_sent
            debug["modalEvents"] = event_count
            debug["functionCalls"] = 1
            debug["stateUpdatesRequested"] = 1
            if usage.get("modalRecordingSessionId"):
                debug["modalRecordingSessionId"] = usage["modalRecordingSessionId"]
        return debugged
    except Exception as exc:
        _LAST_MODAL_ERROR = {
            "type": type(exc).__name__,
            "message": str(exc)[:360],
            "elapsedMs": elapsed_ms(started),
            "baseUrl": base_url,
            "wsPath": "/ws/chat",
            "imageSent": image_sent,
        }
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


def modal_user_content(prompt_payload: dict[str, Any], payload: dict[str, Any]) -> tuple[str | list[dict[str, Any]], bool]:
    text = modal_action_prompt(prompt_payload, payload)
    camera_frame = payload.get("cameraFrame")
    send_image = should_send_modal_image(payload)
    if send_image and isinstance(camera_frame, str) and camera_frame.startswith("data:image/"):
        return [
            {"type": "text", "text": text},
            {"type": "image", "data": image_base64(camera_frame)},
        ], True
    return text, False


def should_send_modal_image(payload: dict[str, Any]) -> bool:
    mode = os.getenv("TOYBOX_MODAL_OMNI_SEND_IMAGE", "auto").strip().lower()
    if mode in {"1", "true", "yes", "always"}:
        return True
    if mode in {"0", "false", "no", "never"}:
        return False
    message = str(payload.get("message") or "").lower()
    visual_words = [
        "see",
        "look",
        "vision",
        "camera",
        "inspect",
        "closest",
        "nearby",
        "what is",
        "what's",
        "where",
        "show",
    ]
    return any(word in message for word in visual_words)


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
    coerce_fireboy_command_action(action, payload)
