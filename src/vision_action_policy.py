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
        image_error: Exception | None = None
        if native_endpoint and endpoint.rstrip("/").endswith("/api/chat"):
            provider = "ollama"
            try:
                content, usage = post_ollama_vision_action(
                    httpx,
                    native_endpoint,
                    model,
                    prompt_payload,
                    schema,
                    camera_frame,
                )
                mode = "ollama_vision"
            except Exception as exc:
                image_error = exc
                if os.getenv("TOYBOX_OLLAMA_VISION_TEXT_RETRY", "1").lower() in {"0", "false", "no"}:
                    raise
                content, usage = post_ollama_vision_action(
                    httpx,
                    native_endpoint,
                    model,
                    prompt_payload,
                    schema,
                    None,
                )
                mode = "ollama_text_retry"
                usage = dict(usage or {})
                usage["visionImageRejected"] = True
                usage["visionImageError"] = str(exc)[:500]
                usage["visionImageBytes"] = len(camera_frame.encode("utf-8"))
                usage["stateUpdatesRequested"] = 1
                usage["functionCalls"] = 1
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
        if image_error:
            debugged["debug"]["visionImageRejected"] = True
            debugged["debug"]["visionImageError"] = str(image_error)[:500]
            debugged["debug"]["visionImageBytes"] = len(camera_frame.encode("utf-8"))
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
    data = response_json_or_error(response, "Vision endpoint")
    return data["choices"][0]["message"]["content"], data.get("usage") if isinstance(data, dict) else None


def post_ollama_vision_action(
    httpx: Any,
    endpoint: str,
    model: str,
    prompt_payload: dict[str, Any],
    schema: dict[str, Any],
    camera_frame: str | None,
) -> tuple[str, dict[str, Any] | None]:
    user_message: dict[str, Any] = {
        "role": "user",
        "content": vision_action_user_prompt(prompt_payload, schema, has_image=bool(camera_frame)),
    }
    if camera_frame:
        user_message["images"] = [image_base64(camera_frame)]
    response = httpx.post(
        endpoint,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": vision_action_system_prompt()},
                user_message,
            ],
            "format": "json",
            "think": False,
            "options": {
                "temperature": float(os.getenv("TOYBOX_VISION_ACTION_TEMPERATURE", "0.2")),
                "num_ctx": int(os.getenv("TOYBOX_VISION_NUM_CTX", "8192")),
                "num_predict": int(os.getenv("TOYBOX_VISION_ACTION_MAX_TOKENS", "900")),
            },
            "stream": False,
        },
        timeout=float(os.getenv("TOYBOX_VISION_ACTION_TIMEOUT", os.getenv("TOYBOX_VISION_TIMEOUT", "24"))),
    )
    data = response_json_or_error(response, "Ollama")
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


def response_json_or_error(response: Any, label: str) -> dict[str, Any]:
    if int(getattr(response, "status_code", 200)) >= 400:
        body = str(getattr(response, "text", "") or "").replace("\n", " ").strip()
        if not body:
            body = getattr(response, "reason_phrase", "") or "empty response body"
        raise RuntimeError(f"{label} HTTP {response.status_code}: {body[:800]}")
    return response.json()


def vision_action_system_prompt() -> str:
    return (
        "You are MiniCPM-V controlling a tiny embodied virtual pet. "
        "You receive the user's command, a compact toy-room state, and the pet camera image. "
        "Return only valid JSON for one immediate pet action. Do not explain."
    )


def vision_action_user_prompt(prompt_payload: dict[str, Any], schema: dict[str, Any], has_image: bool = True) -> str:
    perception_line = (
        "Use the attached pet camera image plus the scene payload."
        if has_image
        else "The image payload was rejected by the local runtime; use detectedObjects, objects, arrangements, audio, and forces from the scene payload as Fire Boy's current view."
    )
    return "\n".join(
        [
            "Decide the next action for the pet.",
            perception_line,
            "If the player says walk around, use interaction verb walk. If they say run around, use verb run. For pick up, carry, bring, inspect, talk, or fireball, choose the matching interaction/power.",
            "Use real object ids from the scene. Keep actions safe and visible.",
            "Return one compact JSON object only. Use null for newMemory, objectRecipe, and soundRecipe when unused.",
            f"Action contract: {json.dumps(compact_action_contract(schema), ensure_ascii=True)}",
            f"Required shape: {json.dumps(action_shape_example(), ensure_ascii=True)}",
            f"Scene payload: {json.dumps(vision_prompt_payload(prompt_payload), ensure_ascii=True)[:4200]}",
        ]
    )


def action_shape_example() -> dict[str, Any]:
    return {
        "pet": "fire_boy",
        "speech": "baby voice",
        "emotion": "happy",
        "animation": "walk",
        "intent": "short",
        "blendshape": {},
        "power": {"name": "ember_jump", "targetId": "cube-red", "strength": 0.5, "durationMs": 900},
        "interaction": {"verb": "pickup", "targetId": "cube-red", "partnerPet": "", "durationMs": 2600},
        "spell": {
            "spellName": "warm pickup",
            "ops": [{"op": "spawn_particle", "targetId": "cube-red", "durationMs": 800, "color": "#ff9b45"}],
        },
        "newMemory": None,
        "objectRecipe": None,
        "sound": "happy_chirp",
        "soundRecipe": None,
    }


def vision_prompt_payload(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "pet": prompt_payload.get("pet"),
        "user_message": prompt_payload.get("user_message"),
        "cameraFrameSource": prompt_payload.get("cameraFrameSource"),
        "detectedObjects": (prompt_payload.get("detectedObjects") or [])[:8],
        "objects": (prompt_payload.get("objects") or [])[:10],
        "arrangements": (prompt_payload.get("arrangements") or [])[:3],
        "interactions": (prompt_payload.get("interactions") or [])[-4:],
        "recentForces": (prompt_payload.get("recentForces") or [])[-4:],
        "memories": (prompt_payload.get("memories") or [])[:4],
        "vision": prompt_payload.get("vision") or {},
        "audio": prompt_payload.get("audio") or {},
        "needs": prompt_payload.get("needs") or {},
        "balance": prompt_payload.get("balance") or {},
    }


def compact_action_contract(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    interaction = properties.get("interaction") if isinstance(properties.get("interaction"), dict) else {}
    interaction_props = interaction.get("properties") if isinstance(interaction.get("properties"), dict) else {}
    power = properties.get("power") if isinstance(properties.get("power"), dict) else {}
    power_props = power.get("properties") if isinstance(power.get("properties"), dict) else {}
    spell = properties.get("spell") if isinstance(properties.get("spell"), dict) else {}
    spell_props = spell.get("properties") if isinstance(spell.get("properties"), dict) else {}
    ops = spell_props.get("ops") if isinstance(spell_props.get("ops"), dict) else {}
    op_items = ops.get("items") if isinstance(ops.get("items"), dict) else {}
    op_props = op_items.get("properties") if isinstance(op_items.get("properties"), dict) else {}
    return {
        "pets": enum_values(properties.get("pet")),
        "emotions": enum_values(properties.get("emotion")),
        "animations": enum_values(properties.get("animation")),
        "powerNames": enum_values(power_props.get("name")),
        "interactionVerbs": enum_values(interaction_props.get("verb")),
        "targetIds": enum_values(interaction_props.get("targetId")),
        "spellOps": enum_values(op_props.get("op")),
        "sounds": enum_values(properties.get("sound")),
        "numbers": "strength 0.1-1.5, durations in ms",
    }


def enum_values(value: Any, limit: int = 32) -> list[str]:
    if not isinstance(value, dict) or not isinstance(value.get("enum"), list):
        return []
    return [str(item) for item in value["enum"][:limit]]
