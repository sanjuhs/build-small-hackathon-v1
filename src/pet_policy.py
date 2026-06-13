from __future__ import annotations

import os
from typing import Any

from src.model_policy import model_status, try_model_policy
from src.pet_actions import fallback_policy, model_unavailable_policy
from src.pet_memory import remember_from_action
from src.pet_trace import write_trace
from src.trace_policy import try_trace_policy
from src.vision_policy import try_vision_perception


def choose_pet_action(payload: dict[str, Any]) -> dict[str, Any]:
    vision = try_vision_perception(payload)
    if vision:
        payload = {**payload, "vision": vision}

    endpoint = os.getenv("TOYBOX_LLM_ENDPOINT", "").strip()
    status = model_status()
    if endpoint and status.get("enabled"):
        action = try_model_policy(endpoint, payload)
        if action:
            apply_vision_blendshape(action, vision)
            remember_from_action(action, payload)
            write_trace(payload, action)
            return action

    if endpoint and status.get("configured") and not allow_heuristic_fallback():
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
    if not vision or action.get("blendshape"):
        return
    blendshape = vision.get("blendshape")
    if isinstance(blendshape, dict) and blendshape:
        action["blendshape"] = blendshape


def allow_heuristic_fallback() -> bool:
    return os.getenv("TOYBOX_ALLOW_HEURISTIC_FALLBACK", "").lower() in {"1", "true", "yes"}
