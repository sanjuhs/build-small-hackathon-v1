from __future__ import annotations

import os
from typing import Any

from src.model_policy import model_status, try_model_policy
from src.pet_actions import fallback_policy, model_unavailable_policy
from src.pet_memory import remember_from_action
from src.pet_trace import write_trace
from src.trace_policy import try_trace_policy
from src.vision_action_policy import try_vision_action_policy
from src.vision_policy import try_vision_perception


def choose_pet_action(payload: dict[str, Any]) -> dict[str, Any]:
    status = model_status()
    strict_model = bool(status.get("configured")) and not allow_heuristic_fallback()

    if status.get("visionActionConfigured"):
        if status.get("visionActionEnabled"):
            action = try_vision_action_policy(payload)
            if action:
                remember_from_action(action, payload)
                write_trace(payload, action)
                return action
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
            remember_from_action(action, payload)
            write_trace(payload, action)
            return action

    if strict_model:
        action = model_unavailable_policy(payload)
        apply_vision_blendshape(action, vision)
        write_trace(payload, action)
        return action

    action = try_trace_policy(payload) or fallback_policy(payload)
    apply_vision_blendshape(action, vision)
    remember_from_action(action, payload)
    write_trace(payload, action)
    return action


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
