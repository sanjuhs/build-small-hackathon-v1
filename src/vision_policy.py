from __future__ import annotations

import os
from typing import Any

from src.model_policy import auth_headers, can_call_endpoint, extract_json, ollama_chat_endpoint
from src.pet_profiles import FACE_BLENDSHAPE_KEYS, VALID_EMOTIONS


def try_vision_perception(payload: dict[str, Any]) -> dict[str, Any] | None:
    endpoint = os.getenv("TOYBOX_VISION_ENDPOINT", "").strip()
    model = os.getenv("TOYBOX_VISION_MODEL", "").strip()
    camera_frame = payload.get("cameraFrame")
    if not endpoint or not model or not isinstance(camera_frame, str) or not camera_frame.startswith("data:image/"):
        return None

    try:
        import httpx
    except Exception:
        return None

    errors = []
    native_endpoint = ollama_chat_endpoint(endpoint)
    attempts = [("openai", endpoint)]
    if native_endpoint and endpoint.rstrip("/").endswith("/api/chat"):
        attempts = [("ollama", native_endpoint)]
    elif native_endpoint:
        attempts.append(("ollama", native_endpoint))

    for mode, url in attempts:
        try:
            content = post_vision_request(httpx, mode, url, model, camera_frame)
            return clean_vision_perception(extract_json(content), model)
        except Exception as exc:
            errors.append(f"{mode}: {exc}")

    log_vision_errors(model, errors)
    return None


def post_vision_request(httpx: Any, mode: str, endpoint: str, model: str, camera_frame: str) -> str:
    if mode == "ollama":
        return post_ollama_vision(httpx, endpoint, model, camera_frame)
    return post_openai_vision(httpx, endpoint, model, camera_frame)


def post_openai_vision(httpx: Any, endpoint: str, model: str, camera_frame: str) -> str:
    if not can_call_endpoint(endpoint, "TOYBOX_VISION"):
        raise RuntimeError("vision endpoint requires TOYBOX_VISION_API_KEY, HF_TOKEN, or RUNPOD_API_KEY")

    try:
        response = httpx.post(
            endpoint,
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": vision_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": vision_user_prompt()},
                            {"type": "image_url", "image_url": {"url": camera_frame}},
                        ],
                    },
                ],
                "temperature": float(os.getenv("TOYBOX_VISION_TEMPERATURE", "0.2")),
                "max_tokens": int(os.getenv("TOYBOX_VISION_MAX_TOKENS", "260")),
                "stream": False,
            },
            headers=auth_headers(endpoint, "TOYBOX_VISION"),
            timeout=float(os.getenv("TOYBOX_VISION_TIMEOUT", "20")),
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc


def post_ollama_vision(httpx: Any, endpoint: str, model: str, camera_frame: str) -> str:
    try:
        response = httpx.post(
            endpoint,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": vision_system_prompt()},
                    {"role": "user", "content": vision_user_prompt(), "images": [image_base64(camera_frame)]},
                ],
                "format": "json",
                "think": False,
                "options": ollama_vision_options(),
                "stream": False,
            },
            timeout=float(os.getenv("TOYBOX_VISION_TIMEOUT", "20")),
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc


def ollama_vision_options() -> dict[str, Any]:
    options: dict[str, Any] = {
        "temperature": float(os.getenv("TOYBOX_VISION_TEMPERATURE", "0.2")),
        "num_predict": int(os.getenv("TOYBOX_VISION_NUM_PREDICT", "220")),
    }
    num_ctx = os.getenv("TOYBOX_VISION_NUM_CTX", "4096").strip()
    if num_ctx:
        options["num_ctx"] = int(num_ctx)
    return options


def vision_system_prompt() -> str:
    return (
        "You are the pet's tiny visual cortex. Return compact JSON only. "
        "Describe what the pet can see and suggest a face blendshape."
    )


def vision_user_prompt() -> str:
    return (
        "Analyze this toy-room camera frame. Return JSON with keys: "
        "summary, attention, emotion, blendshape, hazards, toyObjects. "
        f"emotion must be one of {VALID_EMOTIONS}. "
        f"blendshape may include {FACE_BLENDSHAPE_KEYS}."
    )


def image_base64(data_url: str) -> str:
    return data_url.split(",", 1)[1] if "," in data_url else data_url


def log_vision_errors(model: str, errors: list[str]) -> None:
    if os.getenv("TOYBOX_VISION_DEBUG", "").lower() not in {"1", "true", "yes"}:
        return
    joined = " | ".join(error[:240] for error in errors)
    print(f"Vision model {model} did not return perception: {joined}", flush=True)


def clean_vision_perception(value: dict[str, Any], model: str) -> dict[str, Any]:
    blendshape = value.get("blendshape") if isinstance(value.get("blendshape"), dict) else {}
    cleaned_shape = {}
    for key in FACE_BLENDSHAPE_KEYS:
        if key in blendshape:
            try:
                cleaned_shape[key] = max(-1.5, min(1.5, float(blendshape[key] or 0)))
            except (TypeError, ValueError):
                pass

    emotion = str(value.get("emotion") or "curious")
    if emotion not in VALID_EMOTIONS:
        emotion = "curious"

    toy_objects = value.get("toyObjects") if isinstance(value.get("toyObjects"), list) else []
    hazards = value.get("hazards") if isinstance(value.get("hazards"), list) else []
    return {
        "summary": str(value.get("summary") or "")[:220],
        "attention": str(value.get("attention") or "")[:80],
        "emotion": emotion,
        "blendshape": cleaned_shape,
        "hazards": [str(item)[:80] for item in hazards[:5]],
        "toyObjects": [str(item)[:60] for item in toy_objects[:8]],
        "debug": {"visionModel": model},
    }
