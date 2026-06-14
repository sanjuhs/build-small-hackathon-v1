from __future__ import annotations

import os
from typing import Any

from src.modal_omni_policy import modal_omni_last_error, try_modal_omni_policy
from src.model_policy import (
    local_ollama_chat_endpoint,
    local_ollama_text_model,
    local_ollama_vision_model,
    model_status,
    try_model_policy,
)
from src.pet_actions import fallback_policy, model_unavailable_policy
from src.pet_memory import remember_from_action
from src.pet_trace import write_trace
from src.trace_policy import try_trace_policy
from src.vision_action_policy import try_vision_action_policy
from src.vision_policy import try_vision_perception


def choose_pet_action(payload: dict[str, Any]) -> dict[str, Any]:
    status = model_status()
    requested_mode = requested_brain_mode(payload)
    strict_model = bool(status.get("configured")) and not allow_heuristic_fallback()

    if requested_mode != "auto":
        action = try_requested_brain_mode(requested_mode, payload, status)
        if action:
            return finish_action(action, payload, requested_mode)
        action = unavailable_for_requested_mode(requested_mode, payload, status)
        write_trace(payload, action)
        return action

    if status.get("modalOmniConfigured"):
        if status.get("modalOmniEnabled"):
            action = try_modal_omni_policy(payload)
            if action:
                return finish_action(action, payload, requested_mode)
        if strict_model:
            action = model_unavailable_policy(payload)
            debug = action.setdefault("debug", {})
            if isinstance(debug, dict):
                debug["reason"] = "modal_omni_action_unavailable"
                debug["modalOmniUrl"] = status.get("modalOmniUrl")
                last_error = modal_omni_last_error()
                if last_error:
                    debug["modalLastError"] = last_error.get("message")
                    debug["modalLastErrorType"] = last_error.get("type")
                    debug["modalErrorElapsedMs"] = last_error.get("elapsedMs")
                    debug["modalImageSent"] = last_error.get("imageSent")
            write_trace(payload, action)
            return action

    if status.get("visionActionConfigured"):
        if status.get("visionActionEnabled"):
            action = try_vision_action_policy(payload)
            if action:
                return finish_action(action, payload, requested_mode)
        if strict_model:
            action = model_unavailable_policy(payload)
            debug = action.setdefault("debug", {})
            if isinstance(debug, dict):
                debug["reason"] = "minicpm_v_action_unavailable"
                debug["visionAuthConfigured"] = status.get("visionAuthConfigured")
                debug["visionEndpoint"] = status.get("visionEndpoint")
            write_trace(payload, action)
            return action

    vision = try_vision_perception(payload)
    if vision:
        payload = {**payload, "vision": vision}

    endpoint = os.getenv("TOYBOX_LLM_ENDPOINT", "").strip()
    if endpoint and status.get("enabled"):
        action = try_model_policy(endpoint, payload)
        if action:
            apply_vision_blendshape(action, vision)
            return finish_action(action, payload, requested_mode)

    if strict_model:
        action = model_unavailable_policy(payload)
        apply_vision_blendshape(action, vision)
        write_trace(payload, action)
        return action

    action = try_trace_policy(payload) or fallback_policy(payload)
    apply_vision_blendshape(action, vision)
    return finish_action(action, payload, requested_mode)


def try_requested_brain_mode(mode: str, payload: dict[str, Any], status: dict[str, Any]) -> dict[str, Any] | None:
    if mode == "modal":
        if status.get("modalOmniEnabled"):
            return try_modal_omni_policy(payload)
        return None
    if mode == "ollama-vision":
        return try_vision_action_policy(
            payload,
            endpoint_override=local_ollama_chat_endpoint(),
            model_override=local_ollama_vision_model(),
        )
    if mode == "ollama-text":
        return try_model_policy(local_ollama_chat_endpoint(), payload, model_override=local_ollama_text_model())
    return None


def finish_action(action: dict[str, Any], payload: dict[str, Any], requested_mode: str) -> dict[str, Any]:
    debug = action.setdefault("debug", {})
    if isinstance(debug, dict):
        debug["requestedBrainMode"] = requested_mode
    remember_from_action(action, payload)
    write_trace(payload, action)
    return action


def unavailable_for_requested_mode(mode: str, payload: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    action = model_unavailable_policy(payload)
    debug = action.setdefault("debug", {})
    if not isinstance(debug, dict):
        return action
    debug["requestedBrainMode"] = mode
    if mode == "modal":
        debug["reason"] = "modal_selected_unavailable"
        debug["modalOmniUrl"] = status.get("modalOmniUrl")
        last_error = modal_omni_last_error()
        if last_error:
            debug["modalLastError"] = last_error.get("message")
            debug["modalLastErrorType"] = last_error.get("type")
            debug["modalErrorElapsedMs"] = last_error.get("elapsedMs")
            debug["modalImageSent"] = last_error.get("imageSent")
    elif mode == "ollama-vision":
        debug["reason"] = "ollama_vision_selected_unavailable"
        debug["provider"] = "ollama"
        debug["model"] = local_ollama_vision_model()
        debug["ollamaEndpoint"] = local_ollama_chat_endpoint()
        debug["ollamaAvailable"] = status.get("localOllamaAvailable")
        debug["ollamaVisionInstalled"] = status.get("localOllamaVisionInstalled")
        if not payload.get("cameraFrame"):
            debug["ollamaError"] = "cameraFrame missing"
    elif mode == "ollama-text":
        debug["reason"] = "ollama_text_selected_unavailable"
        debug["provider"] = "ollama"
        debug["model"] = local_ollama_text_model()
        debug["ollamaEndpoint"] = local_ollama_chat_endpoint()
        debug["ollamaAvailable"] = status.get("localOllamaAvailable")
        debug["ollamaTextInstalled"] = status.get("localOllamaTextInstalled")
    else:
        debug["reason"] = "unknown_brain_mode"
    return action


def requested_brain_mode(payload: dict[str, Any]) -> str:
    value = str(payload.get("brainMode") or "").strip().lower().replace("_", "-")
    aliases = {
        "local": "ollama-vision",
        "ollama": "ollama-vision",
        "minicpm-v": "ollama-vision",
        "local-vision": "ollama-vision",
        "vision": "ollama-vision",
        "minicpm5": "ollama-text",
        "local-text": "ollama-text",
        "text": "ollama-text",
        "modal-omni": "modal",
    }
    value = aliases.get(value, value)
    if value in {"modal", "ollama-vision", "ollama-text"}:
        return value
    return "auto"


def apply_vision_blendshape(action: dict[str, Any], vision: dict[str, Any] | None) -> None:
    if not vision:
        return
    debug = action.setdefault("debug", {})
    if isinstance(debug, dict):
        debug.update(vision.get("debug") if isinstance(vision.get("debug"), dict) else {})
        if vision.get("summary"):
            debug["visionSummary"] = str(vision.get("summary"))[:160]
    if action.get("blendshape"):
        return
    blendshape = vision.get("blendshape")
    if isinstance(blendshape, dict) and blendshape:
        action["blendshape"] = blendshape


def allow_heuristic_fallback() -> bool:
    return os.getenv("TOYBOX_ALLOW_HEURISTIC_FALLBACK", "").lower() in {"1", "true", "yes"}
