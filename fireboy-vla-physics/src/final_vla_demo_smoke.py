from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_policy_registry import validate_policy_registry


DEFAULT_BASE_URL = "http://127.0.0.1:65373"
DEFAULT_OUT = Path("Fireboy-training-policy-vla/proofs/final-vla-demo-smoke.json")
DEFAULT_REGISTRY = Path("fireboy-vla-physics/policy_registry.json")

SCENE = {
    "objects": [
        {
            "id": "yellow-marker",
            "kind": "marker",
            "affordances": ["go_to"],
            "x": 0.44,
            "y": 0.02,
            "z": 0.0,
        },
        {
            "id": "berry-rose",
            "kind": "berry",
            "affordances": ["eat", "pick_up"],
            "x": 0.42,
            "y": -0.1,
            "z": 0.08,
        },
    ]
}

COMMANDS = [
    {"command": "walk to the yellow marker", "expected_skill": "walk_to", "expected_animation": "walk"},
    {"command": "run around", "expected_skill": "run_around", "expected_animation": "run"},
    {"command": "pick up the berry", "expected_skill": "pick_up", "expected_animation": "hold"},
    {"command": "go find berry and eat it", "expected_skill": "find_and_eat_berry", "expected_animation": "hold"},
]


def request_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={"content-type": "application/json"} if body is not None else {},
        method=method,
    )
    try:
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
        data["_client_latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return data
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc


def compact_model_status(status: dict[str, Any]) -> dict[str, Any]:
    router = status.get("vlaRouter") if isinstance(status.get("vlaRouter"), dict) else {}
    health = router.get("health") if isinstance(router.get("health"), dict) else {}
    return {
        "vlaRouterConfigured": bool(router.get("configured")),
        "vlaRouterEnabled": bool(router.get("enabled")),
        "vlaRouterHealthOk": bool(router.get("healthOk")),
        "vlaRouterUrl": router.get("url") or "",
        "routerCheckpointExists": bool(health.get("checkpoint_exists")),
        "routerModelLoaded": bool(health.get("model_loaded")),
        "routerHealthLatencyMs": router.get("latencyMs"),
    }


def check_route(base_url: str, command: str, expected_skill: str, timeout: float) -> dict[str, Any]:
    payload = {"message": command, "scene": SCENE}
    response = request_json(base_url, "POST", "/api/vla-router", payload, timeout)
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    passed = (
        bool(response.get("ok"))
        and result.get("skill") == expected_skill
        and result.get("device") == "cuda"
        and result.get("policy_kind") == "minicpm_vla_frozen_encoder_skill_param_head_v1"
    )
    return {
        "command": command,
        "expected_skill": expected_skill,
        "passed": passed,
        "skill": result.get("skill"),
        "neural_skill": result.get("neural_skill"),
        "device": result.get("device"),
        "policy_kind": result.get("policy_kind"),
        "dispatch": result.get("dispatch"),
        "params": result.get("params"),
        "latency_ms": result.get("latency_ms"),
        "client_latency_ms": result.get("clientLatencyMs") or response.get("_client_latency_ms"),
    }


def check_pet_action(
    base_url: str,
    command: str,
    expected_skill: str,
    expected_animation: str,
    timeout: float,
) -> dict[str, Any]:
    payload = {"pet": "fire_boy", "message": f"VLA router: {command}", "scene": SCENE}
    action = request_json(base_url, "POST", "/api/pet-action", payload, timeout)
    debug = action.get("debug") if isinstance(action.get("debug"), dict) else {}
    vla = debug.get("vlaRouter") if isinstance(debug.get("vlaRouter"), dict) else {}
    mujoco = debug.get("mujocoPolicy") if isinstance(debug.get("mujocoPolicy"), dict) else {}
    passed = (
        debug.get("policy") == "modal_minicpm_vla_router_plus_mujoco"
        and vla.get("skill") == expected_skill
        and vla.get("device") == "cuda"
        and bool(mujoco.get("success"))
        and mujoco.get("skill") == expected_skill
        and action.get("animation") == expected_animation
    )
    return {
        "command": command,
        "expected_skill": expected_skill,
        "expected_animation": expected_animation,
        "passed": passed,
        "intent": action.get("intent"),
        "animation": action.get("animation"),
        "policy": debug.get("policy"),
        "vla_skill": vla.get("skill"),
        "vla_neural_skill": vla.get("neuralSkill"),
        "vla_device": vla.get("device"),
        "vla_policy_kind": vla.get("policyKind"),
        "mujoco_success": mujoco.get("success"),
        "mujoco_skill": mujoco.get("skill"),
        "gif_url": mujoco.get("gifUrl"),
        "mp4_url": mujoco.get("mp4Url"),
        "registry_status": (mujoco.get("registryEntry") or {}).get("status") if isinstance(mujoco.get("registryEntry"), dict) else "",
        "server_latency_ms": debug.get("serverLatencyMs"),
    }


def best_effort_command(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(command, check=False, text=True, capture_output=True, timeout=30)
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()[:1200],
        }
    except Exception as exc:
        return {"command": command, "error": str(exc)[:1200]}


def run_final_smoke(base_url: str, registry_path: Path, timeout: float) -> dict[str, Any]:
    model_status_raw = request_json(base_url, "GET", "/api/model-status", None, timeout)
    model_status = compact_model_status(model_status_raw)
    registry = validate_policy_registry(registry_path)
    route_checks = [
        check_route(base_url, item["command"], item["expected_skill"], timeout)
        for item in COMMANDS
    ]
    pet_action_checks = [
        check_pet_action(
            base_url,
            item["command"],
            item["expected_skill"],
            item["expected_animation"],
            timeout,
        )
        for item in COMMANDS
    ]
    resource_state = {
        "runpod_pods": best_effort_command(["runpodctl", "pod", "list", "--all"]),
        "modal_apps": best_effort_command(["modal", "app", "list"]),
    }
    passed = (
        bool(model_status["vlaRouterEnabled"])
        and bool(model_status["vlaRouterHealthOk"])
        and bool(model_status["routerCheckpointExists"])
        and bool(registry.get("ok"))
        and all(item["passed"] for item in route_checks)
        and all(item["passed"] for item in pet_action_checks)
    )
    return {
        "ok": passed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "model_status": model_status,
        "registry": registry,
        "route_checks": route_checks,
        "pet_action_checks": pet_action_checks,
        "resource_state": resource_state,
        "notes": [
            "This is the final hackathon smoke gate for the hybrid VLA path.",
            "It proves Modal MiniCPM-V routing and local MuJoCo dispatch through the same API path the website uses.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--timeout", type=float, default=240.0)
    args = parser.parse_args()

    result = run_final_smoke(args.base_url, args.registry, args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
