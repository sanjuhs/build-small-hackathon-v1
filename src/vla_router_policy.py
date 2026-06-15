from __future__ import annotations

import os
import time
from typing import Any

from src.mujoco_policy_bridge import run_mujoco_pet_action
from src.redaction import redact_endpoint_text, redact_endpoint_url


_LAST_VLA_ROUTER_ERROR: dict[str, Any] = {}


def vla_router_base_url() -> str:
    return os.getenv("TOYBOX_VLA_ROUTER_URL", "").strip().rstrip("/")


def vla_router_action_configured() -> bool:
    return os.getenv("TOYBOX_VLA_ROUTER_ACTION", "").lower() in {"1", "true", "yes"}


def vla_router_last_error() -> dict[str, Any]:
    return dict(_LAST_VLA_ROUTER_ERROR)


def vla_router_status() -> dict[str, Any]:
    base_url = vla_router_base_url()
    status = {
        "configured": bool(base_url),
        "enabled": vla_router_action_configured() and bool(base_url),
        "url": redact_endpoint_url(base_url),
        "lastError": vla_router_last_error(),
    }
    if not base_url:
        return status
    try:
        import httpx

        started = time.perf_counter()
        response = httpx.get(f"{base_url}/health", timeout=float(os.getenv("TOYBOX_VLA_ROUTER_HEALTH_TIMEOUT", "8")))
        status.update(
            {
                "healthOk": response.is_success,
                "healthStatusCode": response.status_code,
                "latencyMs": round((time.perf_counter() - started) * 1000, 1),
            }
        )
        if response.headers.get("content-type", "").startswith("application/json"):
            status["health"] = response.json()
    except Exception as exc:
        status.update({"healthOk": False, "healthError": str(exc)[:220], "healthErrorType": type(exc).__name__})
    return status


def route_vla(payload: dict[str, Any]) -> dict[str, Any]:
    global _LAST_VLA_ROUTER_ERROR
    base_url = vla_router_base_url()
    if not base_url:
        raise RuntimeError("TOYBOX_VLA_ROUTER_URL is not configured")
    request = {
        "command": payload.get("message") or payload.get("command") or "",
        "message": payload.get("message") or payload.get("command") or "",
        "scene": payload.get("scene") if isinstance(payload.get("scene"), dict) else {},
        "cameraFrame": payload.get("cameraFrame") or payload.get("image") or "",
        "cameraFrameSource": payload.get("cameraFrameSource") or "",
        "robot_state": payload.get("robot_state") if isinstance(payload.get("robot_state"), dict) else {},
    }
    started = time.perf_counter()
    try:
        import httpx

        response = httpx.post(
            f"{base_url}/route",
            json=request,
            timeout=float(os.getenv("TOYBOX_VLA_ROUTER_TIMEOUT", "180")),
        )
        response.raise_for_status()
        result = response.json()
        result["clientLatencyMs"] = round((time.perf_counter() - started) * 1000, 1)
        _LAST_VLA_ROUTER_ERROR = {}
        return result
    except Exception as exc:
        _LAST_VLA_ROUTER_ERROR = {
            "type": type(exc).__name__,
            "message": redact_endpoint_text(exc)[:360],
            "elapsedMs": round((time.perf_counter() - started) * 1000, 1),
            "url": redact_endpoint_url(base_url),
        }
        raise


def run_vla_router_pet_action(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not should_use_vla_router(payload):
        return None
    try:
        routed = route_vla(payload)
    except Exception:
        return None
    skill = str(routed.get("skill") or "")
    if command_requests_sit(payload):
        routed = dict(routed)
        routed["neural_skill"] = routed.get("skill")
        routed["skill"] = "walk_to"
        routed["dispatch"] = "registry:walk_to"
        routed["localOverride"] = "sit_requires_navigation_then_pose"
        skill = "walk_to"
    elif command_requests_pickup(payload):
        routed = dict(routed)
        routed["neural_skill"] = routed.get("skill")
        routed["skill"] = "pick_up"
        routed["dispatch"] = "registry:pick_up"
        routed["localOverride"] = "go_pick_requires_pickup"
        skill = "pick_up"
    dispatch_payload = dict(payload)
    dispatch_payload["message"] = command_for_skill(skill, payload)
    action = run_mujoco_pet_action(dispatch_payload)
    if not action:
        return None
    debug = action.setdefault("debug", {})
    if isinstance(debug, dict):
        debug["policy"] = "modal_minicpm_vla_router_plus_mujoco"
        debug["vlaRouter"] = compact_vla_result(routed)
        debug["vlaRouterUrl"] = redact_endpoint_url(vla_router_base_url())
        debug["vlaRouterDispatchMessage"] = dispatch_payload["message"]
        debug["clientCommand"] = str(payload.get("message") or "")
    action["intent"] = f"vla_router_{action.get('intent') or 'mujoco_policy'}"
    return action


def command_requests_sit(payload: dict[str, Any]) -> bool:
    message = f" {str(payload.get('message') or payload.get('command') or '').lower()} "
    return " sit " in message or " sit down " in message or " take a seat " in message


def command_requests_pickup(payload: dict[str, Any]) -> bool:
    message = f" {str(payload.get('message') or payload.get('command') or '').lower()} "
    if any(word in message for word in (" eat ", " berry ", " berries ", " grape ", " grapes ", " food ")):
        return False
    return any(
        phrase in message
        for phrase in (
            " pick ",
            " pick up ",
            " pickup ",
            " grab ",
            " hold ",
            " lift ",
            " take ",
            " fetch ",
            " bring ",
        )
    )


def should_use_vla_router(payload: dict[str, Any]) -> bool:
    if not vla_router_base_url():
        return False
    message = str(payload.get("message") or "").lower()
    orientation_only = any(
        phrase in message
        for phrase in ("turn toward", "turn towards", "turn to", "look at", "look toward", "look towards", "face", "watch")
    ) and not any(word in message for word in ("walk", "run", "go ", "move", "come", "pick", "grab", "eat", "berry"))
    if orientation_only:
        return False
    social_only = any(
        phrase in message
        for phrase in ("say hi", "say hello", "hello", "hi", "hey", "greet", "wave", "dance", "boogie", "celebrate", "play catch", "catch", "throw", "toss")
    ) and not any(word in message for word in ("walk", "run", "go ", "move", "come", "pick", "grab", "eat", "berry"))
    if social_only:
        return False
    explicit = "vla" in message or "minicpm" in message or "vision language" in message
    return explicit or vla_router_action_configured()


def command_for_skill(skill: str, payload: dict[str, Any]) -> str:
    original = str(payload.get("message") or payload.get("command") or "").strip()
    if skill == "run_around":
        return mujoco_command(original, "run around")
    if skill == "pick_up":
        return mujoco_command(original, "pick up the nearest object")
    if skill == "find_and_eat_berry":
        return mujoco_command(original, "go find berry and eat it")
    return mujoco_command(original, "walk to the yellow marker")


def mujoco_command(original: str, fallback: str) -> str:
    command = (original or fallback).strip()
    lower = command.lower()
    if "mujoco" in lower or "physics policy" in lower or "learned policy" in lower:
        return command
    return f"{command} with mujoco policy"


def compact_vla_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": result.get("ok"),
        "skill": result.get("skill"),
        "skillId": result.get("skill_id"),
        "skillConfidence": result.get("skill_confidence"),
        "neuralSkill": result.get("neural_skill") or result.get("neuralSkill"),
        "neuralSkillConfidence": result.get("neural_skill_confidence") or result.get("neuralSkillConfidence"),
        "params": result.get("params"),
        "dispatch": result.get("dispatch"),
        "localOverride": result.get("localOverride"),
        "policyKind": result.get("policy_kind"),
        "modelId": result.get("model_id"),
        "device": result.get("device"),
        "latencyMs": result.get("latency_ms"),
        "clientLatencyMs": result.get("clientLatencyMs"),
    }
