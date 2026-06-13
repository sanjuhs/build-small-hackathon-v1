from __future__ import annotations

import json
import os
from collections import Counter, deque
from pathlib import Path
from typing import Any


TRAINING_SYSTEM_PROMPT = (
    "You are PET-LLM, the embodied action policy for Toy Room v2. "
    "Read the compact room state, memories, forces, interactions, audio, and vision summary. "
    "Return one valid Toy Room action JSON object with speech, emotion, animation, intent, "
    "optional interaction, spell, objectRecipe, newMemory, and soundRecipe fields."
)


def trace_path() -> Path:
    return Path(os.getenv("TOYBOX_TRACE_PATH", "data/traces/pet-actions.jsonl"))


def training_dataset_summary(limit: int = 4, path: Path | None = None) -> dict[str, Any]:
    source = path or trace_path()
    min_rows = int(os.getenv("TOYBOX_TRAINING_READY_MIN_ROWS", "20"))
    samples: deque[dict[str, Any]] = deque(maxlen=max(0, min(limit, 12)))
    counters = {
        "policies": Counter(),
        "pets": Counter(),
        "intents": Counter(),
    }
    total_rows = 0
    usable_rows = 0
    invalid_rows = 0

    for record in iter_trace_records(source):
        total_rows += 1
        output = record.get("output") if isinstance(record, dict) else None
        policy = output_policy(output)
        counters["policies"][policy] += 1
        if not is_usable_trace(record):
            invalid_rows += 1
            continue

        usable_rows += 1
        pet = str(output.get("pet") or record.get("input", {}).get("pet") or "unknown")
        intent = str(output.get("intent") or "unknown")
        counters["pets"][pet] += 1
        counters["intents"][intent] += 1
        if samples.maxlen:
            samples.append(compact_sample(record))

    return {
        "tracePath": str(source),
        "exists": source.exists(),
        "target": "MiniCPM/PET action-policy distillation",
        "format": "openai-chat-jsonl",
        "totalRows": total_rows,
        "seedRows": counters["policies"].get("seed", 0),
        "usableRows": usable_rows,
        "invalidRows": invalid_rows,
        "minRows": min_rows,
        "ready": usable_rows >= min_rows,
        "downloadUrl": "/api/training-dataset?format=jsonl&limit=200",
        "policies": dict(counters["policies"].most_common(8)),
        "pets": dict(counters["pets"].most_common(8)),
        "intents": dict(counters["intents"].most_common(8)),
        "samples": list(samples),
    }


def training_dataset_jsonl(limit: int = 200, path: Path | None = None) -> str:
    source = path or trace_path()
    rows: deque[dict[str, Any]] = deque(maxlen=max(1, min(limit, 1000)))
    for record in iter_trace_records(source):
        if is_usable_trace(record):
            rows.append(training_row(record))
    return "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows)


def iter_trace_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return seed_training_records()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                records.append({"output": {"debug": {"policy": "invalid_json"}}})
                continue
            if isinstance(value, dict):
                records.append(value)
            else:
                records.append({"output": {"debug": {"policy": "invalid_record"}}})
    if os.getenv("TOYBOX_TRAINING_INCLUDE_SEED", "1").lower() not in {"0", "false", "no"}:
        records.extend(seed_training_records())
    return records


def seed_training_records() -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    scenarios = [
        ("squeaky", "Use your agent-view camera: what do you see closest?", "vision_grounded", "I see soft ball at 0.9m.", "clock_bubble", "inspect", "soft-ball"),
        ("squeaky", "Remember rule: dominos are sacred, never knock them.", "memory_transfer", "I learned that dominos are sacred.", "clock_bubble", "inspect", "domino-3"),
        ("squeaky", "What did I build? Guess the charade.", "fallback_playful_intervention", "That looks like a domino parade.", "time_freeze", "inspect", "domino-1"),
        ("fire_boy", "I wish the room had a tiny piano for the toys.", "fallback_playful_intervention", "I wished in tiny piano.", "smoke_poof", "none", "all-toys"),
        ("fire_boy", "Talk to Shark Girl and answer with a warm ember jump.", "fallback_playful_intervention", "Warm copy, Shark Girl.", "ember_jump", "talk", "shell-chair"),
        ("fire_boy", "React to force input: the player dropped you from a height.", "fallback_playful_intervention", "I caught the scary part.", "smoke_poof", "comfort", "fire_boy-body"),
        ("shark_girl", "Invite Fire Boy to play together with a bubble lift.", "fallback_playful_intervention", "Bubble received, Fire Boy.", "bubble_lift", "play", "shell-chair"),
        ("shark_girl", "Use your wave to clean the plastic bottle.", "fallback_playful_intervention", "Soft tide toward the blue bin.", "wave", "recycle", "plastic-bottle"),
        ("shark_girl", "Listen to the room audio and react.", "fallback_playful_intervention", "I heard the room.", "bubble_lift", "inspect", "soft-ball"),
        ("electraica", "Please recycle the can and tidy the waste.", "fallback_playful_intervention", "This belongs in the blue bin.", "magnet_pull", "recycle", "tin-can"),
        ("electraica", "Use your agent-view camera: inspect the nearest shiny toy.", "vision_grounded", "I see tin can at 1.2m.", "magnet_pull", "inspect", "tin-can"),
        ("electraica", "Use power: lamp_burst. Make the lamp cheerful.", "fallback_playful_intervention", "Lamp cheer circuit online.", "lamp_burst", "inspect", "lamp"),
    ]
    for index in range(24):
        pet, message, intent, speech, power, verb, target_id = scenarios[index % len(scenarios)]
        partner = ""
        if pet == "fire_boy" and verb in {"talk", "comfort"}:
            partner = "shark_girl"
        elif pet == "shark_girl" and verb == "play":
            partner = "fire_boy"
        output = seed_output(pet, intent, speech, power, verb, target_id, partner)
        if "remember rule" in message.lower():
            output["newMemory"] = {
                "concept": "dominos are sacred",
                "meaning": "Protect domino arrangements and avoid knocking them over.",
                "confidence": 0.92,
            }
        if "wish" in message.lower():
            output["objectRecipe"] = {
                "id": "wish-tiny-piano",
                "name": "tiny piano",
                "kind": "music",
                "shape": "composite",
                "color": "#5a3d8a",
                "accentColor": "#ffd75a",
                "size": {"x": 0.64, "y": 0.38, "z": 0.46},
                "radius": 0.34,
                "mass": 0.8,
                "affordances": ["music", "play", "inspect"],
                "tags": ["generated", "music"],
                "parts": [
                    {"shape": "box", "offset": [0, 0, 0], "scale": [1, 0.42, 0.7], "color": "#5a3d8a"},
                    {"shape": "box", "offset": [0, 0.16, 0.28], "scale": [0.82, 0.08, 0.14], "color": "#fff7d1"},
                ],
            }
        seeds.append({"timestamp": f"seed-{index + 1:02d}", "input": seed_input(pet, message, target_id), "output": output})
    return seeds


def seed_input(pet: str, message: str, target_id: str) -> dict[str, Any]:
    kind = "can" if "can" in target_id else "domino" if "domino" in target_id else "toy"
    return {
        "pet": pet,
        "user_message": message,
        "objects": [
            {"id": target_id, "kind": kind, "speed": 0.0, "distanceToPet": 1.2, "moving": False},
            {"id": "recycle-bin", "kind": "bin", "speed": 0.0, "distanceToPet": 2.1, "moving": False},
        ],
        "recentForces": [],
        "detectedObjects": [{"id": target_id, "kind": kind, "distance": 1.2, "moving": False}],
        "interactions": [],
        "cooldowns": {},
        "cameraFrame": {"present": False, "bytesApprox": 0, "source": "seed"},
    }


def seed_output(pet: str, intent: str, speech: str, power: str, verb: str, target_id: str, partner: str) -> dict[str, Any]:
    return {
        "pet": pet,
        "speech": speech,
        "emotion": "focused" if verb in {"inspect", "recycle"} else "happy",
        "animation": "bounce",
        "intent": intent,
        "power": {"name": power, "targetId": target_id, "strength": 0.9, "durationMs": 1700},
        "interaction": {"verb": verb, "targetId": target_id, "partnerPet": partner, "durationMs": 2200},
        "spell": {
            "spellName": f"seed {power}",
            "ops": [{"op": "spawn_particle", "targetId": target_id, "durationMs": 700, "color": "#8bd5e5"}],
        },
        "sound": "happy_chirp",
        "debug": {"policy": "seed"},
    }


def is_usable_trace(record: dict[str, Any]) -> bool:
    input_payload = record.get("input")
    output = record.get("output")
    if not isinstance(input_payload, dict) or not isinstance(output, dict):
        return False
    policy = output_policy(output)
    if policy in {"model_error", "invalid_json", "invalid_record"}:
        return False
    if not output.get("pet") or not output.get("speech") or not output.get("intent"):
        return False
    if not any(key in output for key in ("power", "interaction", "spell", "objectRecipe", "newMemory")):
        return False
    return True


def training_row(record: dict[str, Any]) -> dict[str, Any]:
    output = clean_output(record.get("output") or {})
    input_payload = record.get("input") or {}
    return {
        "messages": [
            {"role": "system", "content": TRAINING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "choose_next_toy_room_action",
                        "input": input_payload,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                ),
            },
            {"role": "assistant", "content": json.dumps(output, ensure_ascii=True, sort_keys=True)},
        ],
        "metadata": {
            "timestamp": record.get("timestamp"),
            "pet": output.get("pet"),
            "intent": output.get("intent"),
            "policy": output_policy(record.get("output")),
        },
    }


def clean_output(output: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(output)
    cleaned.pop("debug", None)
    return cleaned


def compact_sample(record: dict[str, Any]) -> dict[str, Any]:
    output = record.get("output") or {}
    input_payload = record.get("input") or {}
    objects = input_payload.get("objects") if isinstance(input_payload.get("objects"), list) else []
    detected = input_payload.get("detectedObjects") if isinstance(input_payload.get("detectedObjects"), list) else []
    return {
        "timestamp": record.get("timestamp"),
        "pet": output.get("pet") or input_payload.get("pet"),
        "message": str(input_payload.get("user_message") or "")[:160],
        "intent": output.get("intent"),
        "policy": output_policy(output),
        "speech": str(output.get("speech") or "")[:160],
        "objects": len(objects),
        "detectedObjects": len(detected),
        "hasCameraFrame": bool((input_payload.get("cameraFrame") or {}).get("present"))
        if isinstance(input_payload.get("cameraFrame"), dict)
        else False,
    }


def output_policy(output: Any) -> str:
    if not isinstance(output, dict):
        return "invalid_record"
    debug = output.get("debug") if isinstance(output.get("debug"), dict) else {}
    return str(debug.get("policy") or "unknown")
