from __future__ import annotations

import json
import os
import re
import time
from typing import Any
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen

from src.command_coercion import coerce_fireboy_command_action
from src.pet_actions import action_schema, validate_action
from src.pet_memory import memory_path
from src.pet_payload import compact_payload, target_from_payload, target_ids_from_payload
from src.pet_profiles import PET_PROFILES, VALID_EMOTIONS, normalize_pet


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_TEXT_MODEL = "hf.co/openbmb/MiniCPM5-1B-GGUF:Q4_K_M"
DEFAULT_OLLAMA_VISION_MODEL = "minicpm-v4.6"
_OLLAMA_STATUS_CACHE: tuple[float, dict[str, Any]] | None = None


def try_model_policy(endpoint: str, payload: dict[str, Any], model_override: str | None = None) -> dict[str, Any] | None:
    try:
        import httpx
    except Exception:
        return None

    model = model_override or os.getenv("TOYBOX_LLM_MODEL", "local-small-model")
    prompt_payload = compact_payload(payload)
    ollama_endpoint = ollama_chat_endpoint(endpoint)

    if ollama_endpoint:
        started = time.perf_counter()
        action = try_ollama_structured_policy(httpx, ollama_endpoint, model, prompt_payload, payload)
        if action:
            coerce_fireboy_command_action(action, payload)
            return attach_model_debug(action, model, provider="ollama", latency_ms=elapsed_ms(started))

    if not can_call_endpoint(endpoint, "TOYBOX_LLM"):
        return None

    try:
        started = time.perf_counter()
        request_json = {
            "model": model,
            "messages": [
                {"role": "system", "content": text_policy_system_prompt()},
                {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=True)},
            ],
            "temperature": 0.8,
            "max_tokens": int(os.getenv("TOYBOX_LLM_MAX_TOKENS", "900")),
            "stream": False,
        }
        if os.getenv("TOYBOX_LLM_SEND_THINK", "").lower() in {"1", "true", "yes"}:
            request_json["think"] = False

        response = httpx.post(
            endpoint,
            json=request_json,
            headers=auth_headers(endpoint, "TOYBOX_LLM"),
            timeout=float(os.getenv("TOYBOX_LLM_TIMEOUT", "18")),
        )
        response.raise_for_status()
        data = response.json()
        parsed = extract_json(data["choices"][0]["message"]["content"])
        action = validate_action(parsed, payload)
        coerce_fireboy_command_action(action, payload)
        return attach_model_debug(
            action,
            model,
            provider=endpoint_provider(endpoint) or endpoint_mode(endpoint),
            latency_ms=elapsed_ms(started),
            usage=data.get("usage") if isinstance(data, dict) else None,
        )
    except Exception:
        return None


def local_ollama_base_url() -> str:
    endpoint = os.getenv("TOYBOX_OLLAMA_BASE_URL", "").strip() or os.getenv("OLLAMA_HOST", "").strip()
    if not endpoint:
        return DEFAULT_OLLAMA_BASE_URL
    if "://" not in endpoint:
        endpoint = f"http://{endpoint}"
    return endpoint.rstrip("/")


def local_ollama_chat_endpoint() -> str:
    return f"{local_ollama_base_url()}/api/chat"


def local_ollama_text_model() -> str:
    return os.getenv("TOYBOX_OLLAMA_TEXT_MODEL", DEFAULT_OLLAMA_TEXT_MODEL).strip() or DEFAULT_OLLAMA_TEXT_MODEL


def local_ollama_vision_model() -> str:
    return os.getenv("TOYBOX_OLLAMA_VISION_MODEL", DEFAULT_OLLAMA_VISION_MODEL).strip() or DEFAULT_OLLAMA_VISION_MODEL


def local_ollama_status() -> dict[str, Any]:
    global _OLLAMA_STATUS_CACHE
    now = time.perf_counter()
    if _OLLAMA_STATUS_CACHE and now - _OLLAMA_STATUS_CACHE[0] < 5:
        return dict(_OLLAMA_STATUS_CACHE[1])

    timeout = float(os.getenv("TOYBOX_OLLAMA_STATUS_TIMEOUT", "0.45"))
    status: dict[str, Any] = {"available": False, "models": [], "error": ""}
    try:
        with urlopen(f"{local_ollama_base_url()}/api/tags", timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        models = [str(item.get("name") or "") for item in data.get("models", []) if item.get("name")]
        status = {"available": True, "models": models[:32], "error": ""}
    except Exception as exc:
        status = {"available": False, "models": [], "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    _OLLAMA_STATUS_CACHE = (now, status)
    return dict(status)


def model_status() -> dict[str, Any]:
    endpoint = os.getenv("TOYBOX_LLM_ENDPOINT", "").strip()
    model = os.getenv("TOYBOX_LLM_MODEL", "").strip()
    vision_endpoint = os.getenv("TOYBOX_VISION_ENDPOINT", "").strip()
    vision_model = os.getenv("TOYBOX_VISION_MODEL", "").strip()
    ollama_status = local_ollama_status()
    ollama_models = ollama_status.get("models") if isinstance(ollama_status.get("models"), list) else []
    ollama_text_model = local_ollama_text_model()
    ollama_vision_model = local_ollama_vision_model()
    modal_requested = modal_omni_action_enabled()
    modal_url = os.getenv("TOYBOX_MODAL_OMNI_URL", "").strip().rstrip("/")
    modal_model = os.getenv("TOYBOX_MODAL_OMNI_MODEL", "openbmb/MiniCPM-o-4_5").strip() or "openbmb/MiniCPM-o-4_5"
    modal_configured = modal_requested and bool(modal_url)
    vision_action_configured = vision_model_action_enabled() and bool(vision_endpoint and vision_model)
    llm_ollama = bool(endpoint and ollama_chat_endpoint(endpoint))
    vision_ollama = bool(vision_endpoint and ollama_chat_endpoint(vision_endpoint))
    llm_auth_required = bool(endpoint and not llm_ollama and endpoint_requires_bearer_auth(endpoint))
    vision_auth_required = bool(
        vision_endpoint and not vision_ollama and endpoint_requires_bearer_auth(vision_endpoint)
    )
    llm_auth_configured = bool(endpoint and api_key_for_endpoint(endpoint, "TOYBOX_LLM"))
    vision_auth_configured = bool(vision_endpoint and api_key_for_endpoint(vision_endpoint, "TOYBOX_VISION"))
    llm_configured = bool(endpoint and model)
    vision_configured = bool(vision_endpoint and vision_model)
    trace_policy_enabled = os.getenv("TOYBOX_TRACE_POLICY", "1").lower() not in {"0", "false", "no"}
    any_model_configured = modal_requested or llm_configured or vision_action_configured
    any_model_enabled = (
        modal_configured
        or (llm_configured and (not llm_auth_required or llm_auth_configured))
        or (vision_action_configured and (not vision_auth_required or vision_auth_configured))
    )
    if any_model_configured and not allow_heuristic_fallback():
        fallback_policy = "asleep_when_configured"
    elif trace_policy_enabled:
        fallback_policy = "trace_retrieval+heuristic"
    else:
        fallback_policy = "heuristic"
    return {
        "configured": any_model_configured,
        "enabled": any_model_enabled,
        "mode": "modal-omni-websocket"
        if modal_requested
        else (
            "ollama"
            if llm_ollama
            else (endpoint_mode(endpoint) if endpoint else (endpoint_mode(vision_endpoint) if vision_action_configured else "fallback"))
        ),
        "provider": "modal"
        if modal_requested
        else (endpoint_provider(endpoint) or (endpoint_provider(vision_endpoint) if vision_action_configured else None)),
        "endpoint": modal_url if modal_requested else (endpoint or (vision_endpoint if vision_action_configured else None) or None),
        "model": modal_model if modal_requested else (model or (vision_model if vision_action_configured else "") or "fallback-policy"),
        "authRequired": (False if modal_requested else llm_auth_required)
        or (not modal_requested and vision_action_configured and vision_auth_required),
        "authConfigured": (True if modal_configured else llm_auth_configured)
        or (not modal_requested and vision_action_configured and vision_auth_configured),
        "modalOmniRequested": modal_requested,
        "modalOmniConfigured": modal_configured,
        "modalOmniEnabled": modal_configured,
        "modalOmniUrl": modal_url or None,
        "modalOmniModel": modal_model,
        "modalOmniImageMode": os.getenv("TOYBOX_MODAL_OMNI_SEND_IMAGE", "auto").strip() or "auto",
        "modalOmniWsPath": "/ws/chat",
        "localOllamaEndpoint": local_ollama_base_url(),
        "localOllamaAvailable": bool(ollama_status.get("available")),
        "localOllamaError": str(ollama_status.get("error") or ""),
        "localOllamaModels": ollama_models,
        "localOllamaTextModel": ollama_text_model,
        "localOllamaVisionModel": ollama_vision_model,
        "localOllamaTextInstalled": ollama_model_installed(ollama_text_model, ollama_models),
        "localOllamaVisionInstalled": ollama_model_installed(ollama_vision_model, ollama_models),
        "visionConfigured": vision_configured,
        "visionEnabled": vision_configured and (not vision_auth_required or vision_auth_configured),
        "visionActionConfigured": vision_action_configured,
        "visionActionEnabled": vision_action_configured and (not vision_auth_required or vision_auth_configured),
        "visionMode": "ollama" if vision_ollama else (endpoint_mode(vision_endpoint) if vision_endpoint else "none"),
        "visionProvider": endpoint_provider(vision_endpoint),
        "visionEndpoint": vision_endpoint or None,
        "visionModel": vision_model or None,
        "visionAuthRequired": vision_auth_required,
        "visionAuthConfigured": vision_auth_configured,
        "fallbackPolicy": fallback_policy,
        "tracePolicyEnabled": trace_policy_enabled,
        "tracePath": os.getenv("TOYBOX_TRACE_PATH", "data/traces/pet-actions.jsonl"),
        "memoryPath": str(memory_path()),
        "actionDbPath": os.getenv("TOYBOX_ACTION_DB_PATH", "data/pet-action-events.sqlite3"),
    }


def allow_heuristic_fallback() -> bool:
    return os.getenv("TOYBOX_ALLOW_HEURISTIC_FALLBACK", "").lower() in {"1", "true", "yes"}


def ollama_model_installed(model: str, models: list[str]) -> bool:
    if model in models:
        return True
    if ":" not in model and f"{model}:latest" in models:
        return True
    return False


def vision_model_action_enabled() -> bool:
    return os.getenv("TOYBOX_MINICPM_V_ACTION", "").lower() in {"1", "true", "yes"}


def modal_omni_action_enabled() -> bool:
    return os.getenv("TOYBOX_MODAL_OMNI_ACTION", "").lower() in {"1", "true", "yes"}


def can_call_endpoint(endpoint: str, prefix: str) -> bool:
    if not endpoint:
        return False
    if endpoint_requires_bearer_auth(endpoint):
        return bool(api_key_for_endpoint(endpoint, prefix))
    return True


def auth_headers(endpoint: str, prefix: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    api_key = api_key_for_endpoint(endpoint, prefix)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    bill_to = os.getenv(f"{prefix}_BILL_TO", "").strip() or os.getenv("TOYBOX_HF_BILL_TO", "").strip()
    if bill_to and is_huggingface_endpoint(endpoint):
        headers["X-HF-Bill-To"] = bill_to
    return headers


def api_key_for_endpoint(endpoint: str, prefix: str) -> str:
    direct = os.getenv(f"{prefix}_API_KEY", "").strip()
    if direct:
        return direct

    host = endpoint_hostname(endpoint)
    if is_huggingface_endpoint(endpoint):
        return (
            os.getenv("HF_TOKEN", "").strip()
            or os.getenv("HUGGINGFACEHUB_API_TOKEN", "").strip()
            or os.getenv("HUGGING_FACE_HUB_TOKEN", "").strip()
        )
    if is_runpod_endpoint(endpoint):
        return os.getenv("RUNPOD_API_KEY", "").strip()
    if is_modelbest_endpoint(endpoint):
        return (
            os.getenv(f"{prefix}_API_KEY", "").strip()
            or os.getenv("MINICPM_V_API_KEY", "").strip()
            or os.getenv("MODELBEST_API_KEY", "").strip()
            or os.getenv("MODEL_BEST_API_KEY", "").strip()
        )
    if "openai.com" in host:
        return os.getenv("OPENAI_API_KEY", "").strip()
    return ""


def endpoint_requires_bearer_auth(endpoint: str) -> bool:
    if is_local_endpoint(endpoint):
        return False
    host = endpoint_hostname(endpoint)
    known_hosts = (
        "api.openai.com",
        "router.huggingface.co",
        "api-inference.huggingface.co",
        "api.groq.com",
        "api.together.xyz",
        "api.fireworks.ai",
        "api.mistral.ai",
        "api.deepseek.com",
        "openrouter.ai",
        "api.runpod.ai",
        "api.modelbest.cn",
        "modelbest.cn",
    )
    return any(host == item or host.endswith(f".{item}") for item in known_hosts)


def endpoint_mode(endpoint: str) -> str:
    provider = endpoint_provider(endpoint)
    if provider == "runpod":
        return "runpod-openai-compatible"
    if provider == "huggingface":
        return "hf-openai-compatible"
    return "openai-compatible"


def endpoint_provider(endpoint: str) -> str | None:
    if not endpoint:
        return None
    if is_huggingface_endpoint(endpoint):
        return "huggingface"
    if is_runpod_endpoint(endpoint):
        return "runpod"
    if is_modelbest_endpoint(endpoint):
        return "modelbest"
    host = endpoint_hostname(endpoint)
    if "openai.com" in host:
        return "openai"
    if "groq.com" in host:
        return "groq"
    if "together.xyz" in host:
        return "together"
    if "fireworks.ai" in host:
        return "fireworks"
    if "mistral.ai" in host:
        return "mistral"
    if "deepseek.com" in host:
        return "deepseek"
    if "openrouter.ai" in host:
        return "openrouter"
    return "custom"


def is_huggingface_endpoint(endpoint: str) -> bool:
    host = endpoint_hostname(endpoint)
    return host == "huggingface.co" or host.endswith(".huggingface.co")


def is_runpod_endpoint(endpoint: str) -> bool:
    host = endpoint_hostname(endpoint)
    return host == "api.runpod.ai" or host.endswith(".runpod.ai") or host.endswith(".runpod.net")


def is_modelbest_endpoint(endpoint: str) -> bool:
    host = endpoint_hostname(endpoint)
    return host == "api.modelbest.cn" or host.endswith(".modelbest.cn")


def is_local_endpoint(endpoint: str) -> bool:
    host = endpoint_hostname(endpoint)
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def endpoint_hostname(endpoint: str) -> str:
    try:
        return (urlparse(endpoint).hostname or "").lower()
    except Exception:
        return ""


def try_ollama_structured_policy(
    httpx: Any,
    endpoint: str,
    model: str,
    prompt_payload: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    pet = normalize_pet(prompt_payload.get("pet"))
    profile = PET_PROFILES[pet]
    schema = action_schema(profile, target_ids_from_payload(payload))

    try:
        return post_ollama_action(
            httpx,
            endpoint,
            model,
            schema,
            scene_brief(prompt_payload, profile),
            float(os.getenv("TOYBOX_LLM_TEMPERATURE", "0.45")),
            payload,
        )
    except Exception:
        try:
            return post_ollama_action(
                httpx,
                endpoint,
                model,
                schema,
                minimal_scene_brief(prompt_payload, profile, payload),
                0.2,
                payload,
            )
        except Exception:
            return None


def post_ollama_action(
    httpx: Any,
    endpoint: str,
    model: str,
    schema: dict[str, Any],
    user_content: str,
    temperature: float,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = httpx.post(
        endpoint,
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are PET-LLM, an embodied virtual pet brain. "
                        "Fill the JSON schema for one visible room action or pet interaction. "
                        "Invent a short spellName and compose primitive spell ops; never output code. "
                        "Optionally invent a bounded soundRecipe of tiny oscillator tones; never output audio files. "
                        "When the player wishes for, asks to create, spawn, add, summon, or make a new object, fill objectRecipe. "
                        "If the player teaches a new word, rule, preference, or value, set newMemory. "
                        "Use interaction verbs for eating berries, reading books, sitting, sniffing plants, picking up toys, carrying toys, or running around. "
                        "The speech field is the pet's short spoken line only."
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            "format": schema,
            "options": ollama_generation_options(temperature),
            "think": False,
            "stream": False,
        },
        timeout=float(os.getenv("TOYBOX_LLM_TIMEOUT", "18")),
    )
    response.raise_for_status()
    data = response.json()
    action = validate_action(extract_json(data["message"]["content"]), payload)
    action["_modelMetrics"] = ollama_response_metrics(data)
    return action


def ollama_generation_options(temperature: float) -> dict[str, Any]:
    options: dict[str, Any] = {
        "temperature": temperature,
        "num_predict": int(os.getenv("TOYBOX_LLM_NUM_PREDICT", "420")),
    }
    num_ctx = os.getenv("TOYBOX_LLM_NUM_CTX", "2048").strip()
    if num_ctx:
        options["num_ctx"] = int(num_ctx)
    return options


def text_policy_system_prompt() -> str:
    return (
        "You are PET-LLM, the tiny embodied action brain for a cute virtual pet in a Three.js physics toy room. "
        "You are not a chatbot. You must choose one short line and one visible embodied action that the renderer can execute. "
        "React to room objects, collisions, petting, poking, mouse hover, and recent forces. "
        "Prefer playful agency, object awareness, and cute physical behavior over explaining yourself. "
        "For Fire Boy, speak like a babyish warm ember: simple words, tiny confidence, no scary fire. "
        "Do not write <think> tags. Do not include chain-of-thought. "
        "Return only valid JSON matching this schema: "
        '{"pet": string, "speech": string, "emotion": string, "animation": string, '
        '"intent": string, "blendshape": object, "power": {"name": string, "targetId": string, '
        '"strength": number, "durationMs": integer}, '
        '"interaction": {"verb": string, "targetId": string, "partnerPet": string, "durationMs": integer}, '
        '"spell": {"spellName": string, "ops": [{"op": string, "targetId": string, "vec": [number,number,number], '
        '"factor": number, "radius": number, "strength": number, "durationMs": integer, "intensity": number, "color": string}]}, '
        '"newMemory": {"concept": string, "meaning": string} or null, '
        '"objectRecipe": {"id": string, "name": string, "kind": string, "shape": string, "color": string, '
        '"accentColor": string, "size": {"x": number, "y": number, "z": number}, "radius": number, '
        '"mass": number, "affordances": [string], "tags": [string], "parts": [object]} or null, '
        '"sound": string, '
        '"soundRecipe": {"label": string, "gain": number, "tones": [{"frequency": number, "offsetMs": integer, '
        '"durationMs": integer, "gain": number, "wave": string}]} or null}. '
        f"emotion must be one of {VALID_EMOTIONS}. "
        "interaction.verb must be one of none, eat, read, sit, gather, sniff, inspect, water, share, clean, recycle, play, comfort, talk, pickup, carry, bring, walk, run. "
        "Blendshape may include numeric eye, smile, mouth, brow, cheek, squash, tilt, sparkle. "
        "Spell ops must use only impulse, freeze, scale, attract, spawn_particle, set_light, or nudge_pet. "
        "Spell targetId must be a listed object id, self, all-moving, all-toys, or all-agents. "
        "Speech must be under 18 words, first-person, and pet-like. Pick only powers available to the selected pet. "
        "Use interactions for ordinary pet behaviors like eating berries, reading books, sitting near chairs/tables, or sniffing plants. "
        "Use newMemory only for durable lessons from the player, not ordinary observations. "
        "Use objectRecipe only when the player asks to create, spawn, summon, wish for, add, or make a new room object. "
        "objectRecipe parts may use simple box, sphere, and cylinder pieces with safe colors and small dimensions. "
        "Optionally invent soundRecipe as 1-6 tiny oscillator tones; wave must be sine, triangle, square, or sawtooth. "
        "If the user touched the pet, acknowledge touch with a cute physical reaction. "
        "No markdown, no explanation."
    )


def ollama_chat_endpoint(endpoint: str) -> str | None:
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        return None
    if parsed.path.rstrip("/") == "/api/chat":
        return endpoint
    if "11434" not in parsed.netloc and "ollama" not in parsed.netloc.lower():
        return None
    return urlunparse((parsed.scheme, parsed.netloc, "/api/chat", "", "", ""))


def scene_brief(prompt_payload: dict[str, Any], profile: dict[str, Any]) -> str:
    objects = prompt_payload.get("objects") or []
    object_lines = [
        (
            f"{item['id']} kind={item['kind']} name={item.get('name') or ''} generated={item.get('generated', False)} speed={item['speed']} "
            f"distance={item['distanceToPet']} moving={item['moving']} "
            f"affordances={','.join(item.get('affordances') or []) or 'none'} "
            f"nutrition={item.get('nutrition', 0)} readable={item.get('readable', False)}"
        )
        for item in objects[:8]
    ]
    interactions = prompt_payload.get("interactions") or []
    forces = prompt_payload.get("recentForces") or []
    agents = prompt_payload.get("agents") or []
    arrangements = prompt_payload.get("arrangements") or []
    memories = prompt_payload.get("memories") or []
    vision = prompt_payload.get("vision") or {}
    audio = prompt_payload.get("audio") or {}
    needs = prompt_payload.get("needs") or {}
    balance = prompt_payload.get("balance") or {}
    camera_source = prompt_payload.get("cameraFrameSource") or "unknown"

    return "\n".join(
        [
            f"Pet: {prompt_payload['pet']}. Traits: {profile['traits']}.",
            f"User message: {prompt_payload.get('user_message') or '(none)'}",
            f"Objects: {'; '.join(object_lines) if object_lines else 'none'}",
            f"Physical arrangements: {json.dumps(arrangements[:4], ensure_ascii=True) if arrangements else 'none'}",
            f"Other agents: {json.dumps(agents[:6], ensure_ascii=True) if agents else 'none'}",
            f"Memories: {json.dumps(memories[:8], ensure_ascii=True) if memories else 'none'}",
            f"Vision: {json.dumps(vision, ensure_ascii=True) if vision else 'none'} camera={camera_source}",
            f"Audio: {json.dumps(audio, ensure_ascii=True) if audio else 'none'}",
            f"Needs: {json.dumps(needs, ensure_ascii=True) if needs else 'none'}",
            f"Balance: {json.dumps(balance, ensure_ascii=True) if balance else 'none'}",
            f"Recent forces: {json.dumps(forces[-4:], ensure_ascii=True)}",
            f"Recent interactions: {json.dumps(interactions[-4:], ensure_ascii=True)}",
            f"Allowed powers: {', '.join(profile['powers'])}.",
            f"Allowed animations: {', '.join(profile['animations'])}.",
            f"Allowed sounds: {', '.join(profile['sounds'])}.",
            "Choose one playful, visible action. Use a real object id when one is listed; otherwise use all-moving.",
            "Also invent a spellName and 1-4 spell ops from: impulse, freeze, scale, attract, spawn_particle, set_light, nudge_pet.",
            "Optionally invent a soundRecipe of 1-6 oscillator tones that matches the spell, object, or thing the player asked for.",
            "SoundRecipe tones use frequency 80-1800 Hz, offsetMs 0-1200, durationMs 24-900, gain 0.04-1, and wave sine/triangle/square/sawtooth.",
            "Primitive targets may be object ids, self, all-moving, all-toys, or all-agents. Keep magnitudes gentle.",
            "If the player asks to create, spawn, summon, wish for, add, or make a new room object, fill objectRecipe with one small physical toy recipe.",
            "objectRecipe can describe instruments, furniture, plants, food, tools, decor, waste, or toys using up to six simple box/sphere/cylinder parts.",
            "If the player explicitly teaches a term, rule, preference, or value, write newMemory={concept,meaning}; otherwise newMemory=null.",
            "Use memories to transfer taught concepts to new objects and to respect player-taught values.",
            "If physical arrangements include a stack, line, huddle, or wished toy and the player asks what they built, guess the arrangement in character.",
            "For berries/food and high hunger, prefer interaction={verb:eat,targetId:berry id}.",
            "For books or reading requests, prefer interaction={verb:read,targetId:book id}.",
            "For chairs/tables/rest/social requests, prefer interaction=sit or gather. For plants, prefer sniff/inspect/water.",
            "For waste, paper, can, bottle, or peel objects, prefer clean or recycle when the player asks for tidying.",
            "If the player says pick up, grab, hold, fetch, carry, or bring a toy, use interaction verb pickup/carry/bring with the exact object id.",
            "If the player asks to walk around, stroll, or patrol, use interaction={verb:walk,targetId:any listed id,partnerPet:\"\",durationMs:4200}.",
            "If the player asks to run around, zoom, dash, or race, use interaction={verb:run,targetId:any listed id,partnerPet:\"\",durationMs:2600}.",
            "If pet=fire_boy and the player asks for a fireball, use power=fireball and target the named toy if possible.",
            "For another nearby agent, use interaction=talk, play, comfort, or share and set partnerPet.",
            "Use interaction={verb:none,targetId:any listed id,partnerPet:\"\",durationMs:1200} when only using a power.",
            "Recent interactions may include pointer modality, screen coordinates, and pet hit point; treat mouse, touch, and pen as embodied contact.",
            "Audio may include microphone input and room-output bands, peak, and rms; react to loud user sounds with small startles or curious listening.",
            "Balance may include stability and tilt; if unstable, choose a cute steadying action or calmer power.",
            "If touched or petted, prefer emotion=petted, animation=nuzzle, sound=pet_touch.",
            "If poked, prefer emotion=startled, animation=startle, sound=startle.",
            "If asked to freeze/stop/pause or a moving object is near, time_freeze is a good Squeaky power.",
            "If pet=fire_boy, speech should sound babyish and warm: tiny words, little giggles, under 10 words.",
            "Optionally set blendshape values to fine-control the face. Speech must be cute, first-person, under 12 words.",
        ]
    )


def minimal_scene_brief(prompt_payload: dict[str, Any], profile: dict[str, Any], payload: dict[str, Any]) -> str:
    pet = normalize_pet(prompt_payload.get("pet"))
    target_id = target_from_payload(payload)
    interactions = prompt_payload.get("interactions") or []
    message = str(prompt_payload.get("user_message") or "").lower()
    latest = next((item for item in reversed(interactions) if item.get("kind") in {"pet", "poke"}), None)

    if latest and latest.get("kind") == "pet":
        emotion, animation, sound = "petted", "nuzzle", "pet_touch"
        power_name = "clock_bubble" if "clock_bubble" in profile["powers"] else profile["powers"][0]
    elif latest:
        emotion, animation, sound = "startled", "startle", "startle"
        power_name = profile["powers"][0]
    elif pet == "squeaky" and any(word in message for word in ["freeze", "stop", "pause", "time"]):
        emotion, animation, sound = "focused", "trunk_wiggle", "clock_chime"
        power_name = "time_freeze"
    else:
        emotion, animation, sound = "happy", profile["animations"][0], profile["sounds"][0]
        power_name = profile["powers"][0]

    return "\n".join(
        [
            "Create one compact virtual-pet action.",
            f"pet={pet}",
            f"user_message={prompt_payload.get('user_message') or '(none)'}",
            f"targetId={target_id}",
            f"emotion={emotion}",
            f"animation={animation}",
            f"power={power_name}",
            f"interaction=none targetId={target_id}",
            f"spellName={power_name.replace('_', ' ')} improvisation",
            "spell ops: one gentle spawn_particle plus one safe impulse/freeze/attract op if useful",
            "soundRecipe: optional tiny oscillator recipe matching the action",
            "objectRecipe=null unless the user asks to create or wish a new room object into existence",
            "newMemory=null unless the user explicitly taught a lasting concept",
            f"sound={sound}",
            "speech: cute first-person pet line, under 8 words; Fire Boy sounds babyish and warm.",
        ]
    )


def extract_json(content: str) -> dict[str, Any]:
    stripped = content.strip()
    stripped = re.sub(r"<think>.*?</think>", "", stripped, flags=re.DOTALL | re.IGNORECASE).strip()
    stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
    stripped = re.sub(r"```$", "", stripped).strip()
    match = re.search(r"\{[^{}]*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}[^{}]*)*\}", stripped, re.DOTALL)
    if not match:
        raise ValueError("No JSON object in model response")
    return json.loads(match.group(0))


def attach_model_debug(
    action: dict[str, Any],
    model: str,
    provider: str | None = None,
    latency_ms: float | None = None,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = action.pop("_modelMetrics", {})
    debug: dict[str, Any] = {"policy": "model", "model": model}
    if provider:
        debug["provider"] = provider
    if latency_ms is not None:
        debug["modelLatencyMs"] = latency_ms
    if isinstance(metrics, dict):
        debug.update(metrics)
    if isinstance(usage, dict):
        completion_tokens = usage.get("completion_tokens") or usage.get("completionTokens")
        prompt_tokens = usage.get("prompt_tokens") or usage.get("promptTokens")
        total_tokens = usage.get("total_tokens") or usage.get("totalTokens")
        tokens_per_second = usage.get("tokens_per_second") or usage.get("tokensPerSecond")
        if completion_tokens is not None:
            debug["completionTokens"] = completion_tokens
        if prompt_tokens is not None:
            debug["promptTokens"] = prompt_tokens
        if total_tokens is not None:
            debug["totalTokens"] = total_tokens
        if tokens_per_second is not None:
            debug["tokensPerSecond"] = round(float(tokens_per_second), 2)
        elif latency_ms and completion_tokens:
            debug["tokensPerSecond"] = round(float(completion_tokens) / max(latency_ms / 1000, 0.001), 2)
    action["debug"] = debug
    return action


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def ollama_response_metrics(data: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    eval_count = data.get("eval_count")
    eval_duration = data.get("eval_duration")
    prompt_eval_count = data.get("prompt_eval_count")
    prompt_eval_duration = data.get("prompt_eval_duration")
    if eval_count is not None:
        metrics["completionTokens"] = eval_count
    if prompt_eval_count is not None:
        metrics["promptTokens"] = prompt_eval_count
    if eval_duration:
        duration_seconds = float(eval_duration) / 1_000_000_000
        metrics["completionDurationMs"] = round(duration_seconds * 1000, 1)
        if eval_count:
            metrics["tokensPerSecond"] = round(float(eval_count) / max(duration_seconds, 0.001), 2)
    if prompt_eval_duration:
        metrics["promptEvalDurationMs"] = round(float(prompt_eval_duration) / 1_000_000, 1)
    return metrics
