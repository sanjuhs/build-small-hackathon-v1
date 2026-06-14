from __future__ import annotations

import json
import os
import time
from typing import Any

from src.command_coercion import coerce_fireboy_command_action
from src.model_policy import (
    attach_model_debug,
    auth_headers,
    can_call_endpoint,
    elapsed_ms,
    endpoint_mode,
    endpoint_provider,
    extract_json,
    ollama_chat_endpoint,
)
from src.pet_actions import action_schema, validate_action
from src.pet_payload import compact_payload, target_ids_from_payload
from src.pet_profiles import PET_PROFILES, normalize_pet
from src.vision_policy import image_base64


_LAST_VISION_ACTION_ERROR: dict[str, Any] = {}


def vision_action_last_error() -> dict[str, Any]:
    return dict(_LAST_VISION_ACTION_ERROR)


def try_vision_action_policy(
    payload: dict[str, Any],
    endpoint_override: str | None = None,
    model_override: str | None = None,
) -> dict[str, Any] | None:
    endpoint = endpoint_override or os.getenv("TOYBOX_VISION_ENDPOINT", "").strip()
    model = model_override or os.getenv("TOYBOX_VISION_MODEL", "").strip()
    camera_frame = payload.get("cameraFrame")
    if not endpoint or not model or not isinstance(camera_frame, str) or not camera_frame.startswith("data:image/"):
        _record_vision_action_error(
            "preflight",
            "missing endpoint/model/cameraFrame data URL",
            endpoint,
            model,
            camera_frame,
            0,
        )
        return None

    try:
        import httpx
    except Exception as exc:
        _record_vision_action_error(type(exc).__name__, str(exc), endpoint, model, camera_frame, 0)
        return None

    if not can_call_endpoint(endpoint, "TOYBOX_VISION"):
        _record_vision_action_error("auth", "vision endpoint missing auth", endpoint, model, camera_frame, 0)
        return None

    prompt_payload = compact_payload(payload)
    pet = normalize_pet(prompt_payload.get("pet"))
    schema = action_schema(PET_PROFILES[pet], target_ids_from_payload(payload))
    native_endpoint = ollama_chat_endpoint(endpoint)
    started = time.perf_counter()

    try:
        if native_endpoint and endpoint.rstrip("/").endswith("/api/chat"):
            content, usage = post_ollama_vision_action(httpx, native_endpoint, model, prompt_payload, schema, camera_frame)
            mode = "ollama"
            provider = "ollama"
        else:
            content, usage = post_openai_vision_action(httpx, endpoint, model, prompt_payload, schema, camera_frame)
            mode = endpoint_mode(endpoint)
            provider = endpoint_provider(endpoint) or mode
        action = validate_action(extract_json(content), payload)
        coerce_fireboy_command_action(action, payload)
        debugged = attach_model_debug(action, model, provider=provider, latency_ms=elapsed_ms(started), usage=usage)
        debugged.setdefault("debug", {})["policy"] = "minicpm_v_action"
        debugged["debug"]["visionAction"] = True
        debugged["debug"]["visionMode"] = mode
        _LAST_VISION_ACTION_ERROR.clear()
        return debugged
    except Exception as exc:
        _record_vision_action_error(type(exc).__name__, str(exc), endpoint, model, camera_frame, elapsed_ms(started))
        if os.getenv("TOYBOX_VISION_DEBUG", "").lower() in {"1", "true", "yes"}:
            print(f"MiniCPM-V action policy failed: {str(exc)[:280]}", flush=True)
        return None


def _record_vision_action_error(
    error_type: str,
    message: str,
    endpoint: str,
    model: str,
    camera_frame: Any,
    elapsed_ms_value: float,
) -> None:
    image_prefix = ""
    image_bytes = 0
    if isinstance(camera_frame, str):
        image_prefix = camera_frame.split(",", 1)[0][:48]
        image_bytes = len(camera_frame.encode("utf-8"))
    _LAST_VISION_ACTION_ERROR.clear()
    _LAST_VISION_ACTION_ERROR.update(
        {
            "type": error_type,
            "message": str(message)[:500],
            "endpoint": endpoint,
            "model": model,
            "elapsedMs": elapsed_ms_value,
            "imagePrefix": image_prefix,
            "imageBytes": image_bytes,
        }
    )


def post_openai_vision_action(
    httpx: Any,
    endpoint: str,
    model: str,
    prompt_payload: dict[str, Any],
    schema: dict[str, Any],
    camera_frame: str,
) -> tuple[str, dict[str, Any] | None]:
    response = httpx.post(
        endpoint,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": vision_action_system_prompt()},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_action_user_prompt(prompt_payload, schema)},
                        {"type": "image_url", "image_url": {"url": camera_frame}},
                    ],
                },
            ],
            "temperature": float(os.getenv("TOYBOX_VISION_ACTION_TEMPERATURE", "0.25")),
            "max_tokens": int(os.getenv("TOYBOX_VISION_ACTION_MAX_TOKENS", "900")),
            "stream": False,
        },
        headers=auth_headers(endpoint, "TOYBOX_VISION"),
        timeout=float(os.getenv("TOYBOX_VISION_ACTION_TIMEOUT", os.getenv("TOYBOX_VISION_TIMEOUT", "24"))),
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"], data.get("usage") if isinstance(data, dict) else None


def post_ollama_vision_action(
    httpx: Any,
    endpoint: str,
    model: str,
    prompt_payload: dict[str, Any],
    schema: dict[str, Any],
    camera_frame: str,
) -> tuple[str, dict[str, Any] | None]:
    response = httpx.post(
        endpoint,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": vision_action_system_prompt()},
                {
                    "role": "user",
                    "content": vision_action_user_prompt(prompt_payload, schema),
                    "images": [image_base64(camera_frame)],
                },
            ],
            "format": "json",
            "think": False,
            "options": {
                "temperature": float(os.getenv("TOYBOX_VISION_ACTION_TEMPERATURE", "0.2")),
                "num_ctx": int(os.getenv("TOYBOX_VISION_NUM_CTX", "4096")),
                "num_predict": int(os.getenv("TOYBOX_VISION_ACTION_MAX_TOKENS", "900")),
            },
            "stream": False,
        },
        timeout=float(os.getenv("TOYBOX_VISION_ACTION_TIMEOUT", os.getenv("TOYBOX_VISION_TIMEOUT", "24"))),
    )
    response.raise_for_status()
    data = response.json()
    eval_count = data.get("eval_count")
    eval_duration = data.get("eval_duration")
    usage = {
        "completion_tokens": eval_count,
        "prompt_tokens": data.get("prompt_eval_count"),
    }
    if eval_count and eval_duration:
        duration_seconds = float(eval_duration) / 1_000_000_000
        usage["tokensPerSecond"] = round(float(eval_count) / max(duration_seconds, 0.001), 2)
    return data["message"]["content"], usage


def vision_action_system_prompt() -> str:
    return (
        "You are MiniCPM-V controlling a tiny embodied virtual pet. "
        "You receive the user's command, a compact toy-room state, and the pet camera image. "
        "Return only valid JSON for one immediate pet action. Do not explain."
    )


def vision_action_user_prompt(prompt_payload: dict[str, Any], schema: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Decide the next action for the pet.",
            "If the player says walk around, use interaction verb walk. If they say run around, use verb run. For pick up, carry, bring, inspect, talk, or fireball, choose the matching interaction/power.",
            "Use real object ids from the scene. Keep actions safe and visible.",
            "Return JSON matching this schema. Required top-level keys: pet, speech, emotion, animation, intent, blendshape, power, interaction, spell, newMemory, objectRecipe, sound, soundRecipe.",
            f"Action schema: {json.dumps(schema, ensure_ascii=True)[:6500]}",
            f"Scene payload: {json.dumps(prompt_payload, ensure_ascii=True)[:9000]}",
        ]
    )
