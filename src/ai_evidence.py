from __future__ import annotations

import re
from collections import Counter, deque
from typing import Any

from src.model_policy import model_status
from src.pet_memory import load_memories
from src.trace_dataset import is_usable_trace, iter_trace_records, output_policy, trace_path, training_dataset_summary


def ai_evidence_status(limit: int = 4) -> dict[str, Any]:
    records = iter_trace_records(trace_path())
    training = training_dataset_summary(limit=0)
    model = model_status()

    policies: Counter[str] = Counter()
    pets: Counter[str] = Counter()
    intents: Counter[str] = Counter()
    spell_names: Counter[str] = Counter()
    spell_ops: Counter[str] = Counter()
    object_names: Counter[str] = Counter()
    sound_names: Counter[str] = Counter()
    memory_concepts: Counter[str] = Counter()
    unique_messages: set[str] = set()
    example_messages: deque[str] = deque(maxlen=max(0, min(limit, 8)))
    generated_examples: deque[str] = deque(maxlen=max(0, min(limit, 8)))
    memory_examples: deque[str] = deque(maxlen=max(0, min(limit, 8)))

    total = 0
    usable = 0
    generated_object_count = 0
    sound_recipe_count = 0
    memory_write_count = 0
    vision_trace_count = 0
    model_or_trace_count = 0

    for record in records:
        total += 1
        output = record.get("output") if isinstance(record, dict) else {}
        input_payload = record.get("input") if isinstance(record, dict) else {}
        if not isinstance(output, dict):
            continue
        policy = output_policy(output)
        policies[policy] += 1
        if policy in {"model", "trace_retrieval", "seed"}:
            model_or_trace_count += 1
        if not is_usable_trace(record):
            continue
        usable += 1
        pets[str(output.get("pet") or input_payload.get("pet") or "unknown")] += 1
        intents[str(output.get("intent") or "unknown")] += 1

        message = clean_text(input_payload.get("user_message"), 160)
        if message:
            normalized = normalize_message(message)
            if normalized not in unique_messages and len(example_messages) < example_messages.maxlen:
                example_messages.append(message)
            unique_messages.add(normalized)

        spell = output.get("spell") if isinstance(output.get("spell"), dict) else {}
        spell_name = clean_text(spell.get("spellName"), 80)
        if spell_name:
            spell_names[spell_name] += 1
            if len(generated_examples) < generated_examples.maxlen:
                generated_examples.append(f"spell: {spell_name}")
        for op in spell.get("ops") or []:
            if isinstance(op, dict) and op.get("op"):
                spell_ops[str(op.get("op"))] += 1

        recipe = output.get("objectRecipe") if isinstance(output.get("objectRecipe"), dict) else None
        if recipe and recipe.get("name"):
            generated_object_count += 1
            object_name = clean_text(recipe.get("name"), 80)
            object_names[object_name] += 1
            if len(generated_examples) < generated_examples.maxlen:
                generated_examples.append(f"object: {object_name}")

        sound_recipe = output.get("soundRecipe") if isinstance(output.get("soundRecipe"), dict) else None
        if sound_recipe:
            sound_recipe_count += 1
            sound_name = clean_text(sound_recipe.get("label") or output.get("sound"), 80)
            if sound_name:
                sound_names[sound_name] += 1

        memory = output.get("newMemory") if isinstance(output.get("newMemory"), dict) else None
        if memory and memory.get("concept"):
            memory_write_count += 1
            concept = clean_text(memory.get("concept"), 80)
            memory_concepts[concept] += 1
            if len(memory_examples) < memory_examples.maxlen:
                memory_examples.append(f"{concept}: {clean_text(memory.get('meaning'), 120)}")

        debug = output.get("debug") if isinstance(output.get("debug"), dict) else {}
        if output.get("intent") == "vision_grounded" or debug.get("visionApplied"):
            vision_trace_count += 1

    persisted_memories = load_memories(limit=80)
    for memory in persisted_memories:
        concept = clean_text(memory.get("concept"), 80)
        if concept:
            memory_concepts[concept] += 1
            if len(memory_examples) < memory_examples.maxlen:
                memory_examples.append(f"{concept}: {clean_text(memory.get('meaning'), 120)}")

    metrics = {
        "traceRows": total,
        "usableRows": usable,
        "uniqueUserInputs": len(unique_messages),
        "modelOrTraceRows": model_or_trace_count,
        "uniqueSpellNames": len(spell_names),
        "uniqueSpellOps": len(spell_ops),
        "generatedObjectRecipes": generated_object_count,
        "soundRecipes": sound_recipe_count,
        "memoryWrites": memory_write_count,
        "persistedMemories": len(persisted_memories),
        "uniqueMemoryConcepts": len(memory_concepts),
        "visionGroundedTraces": vision_trace_count,
    }

    checks = [
        evidence_check(
            "unbounded_input",
            "Unbounded input",
            metrics["uniqueUserInputs"] >= 12,
            f"{metrics['uniqueUserInputs']} distinct player messages in traces.",
        ),
        evidence_check(
            "generated_spells",
            "Generated spell ops",
            metrics["uniqueSpellNames"] >= 4 and metrics["uniqueSpellOps"] >= 4,
            f"{metrics['uniqueSpellNames']} spell names using {metrics['uniqueSpellOps']} primitive op types.",
        ),
        evidence_check(
            "wish_objects",
            "Wishable objects",
            metrics["generatedObjectRecipes"] >= 1,
            f"{metrics['generatedObjectRecipes']} generated object recipes recorded.",
        ),
        evidence_check(
            "runtime_learning",
            "Runtime learning",
            metrics["memoryWrites"] + metrics["persistedMemories"] >= 1,
            f"{metrics['memoryWrites']} trace memories; {metrics['persistedMemories']} persisted memories.",
        ),
        evidence_check(
            "vision_grounding",
            "Vision grounding",
            metrics["visionGroundedTraces"] >= 4,
            f"{metrics['visionGroundedTraces']} vision-grounded actions recorded.",
        ),
        evidence_check(
            "distillation_pack",
            "SFT trace pack",
            bool(training.get("ready")),
            f"{training.get('usableRows', 0)} usable MiniCPM/PET rows.",
        ),
        evidence_check(
            "model_path",
            "Model path",
            bool(model.get("enabled")) or metrics["modelOrTraceRows"] >= 20,
            (
                f"Live {model.get('provider') or model.get('mode')} endpoint enabled."
                if model.get("enabled")
                else f"{metrics['modelOrTraceRows']} model/trace/seed policy rows; live endpoint optional warning remains."
            ),
            required=False,
        ),
    ]
    required = [check for check in checks if check.get("required")]
    ok = sum(1 for check in checks if check["state"] == "ok")
    required_ok = sum(1 for check in required if check["state"] == "ok")

    return {
        "title": "Toy Room v2 AI evidence",
        "summary": "Trace-backed proof for unbounded input, generated content, and runtime learning.",
        "score": {
            "ok": ok,
            "warn": sum(1 for check in checks if check["state"] == "warn"),
            "total": len(checks),
            "requiredOk": required_ok,
            "requiredTotal": len(required),
            "ready": required_ok == len(required),
        },
        "checks": checks,
        "metrics": metrics,
        "policies": dict(policies.most_common(8)),
        "pets": dict(pets.most_common(8)),
        "intents": dict(intents.most_common(8)),
        "spellOps": dict(spell_ops.most_common(8)),
        "spellNames": dict(spell_names.most_common(8)),
        "objectRecipes": dict(object_names.most_common(8)),
        "soundRecipes": dict(sound_names.most_common(8)),
        "memoryConcepts": dict(memory_concepts.most_common(8)),
        "examples": {
            "inputs": list(example_messages),
            "generated": list(generated_examples),
            "memories": list(memory_examples),
        },
    }


def evidence_check(check_id: str, label: str, ok: bool, detail: str, *, required: bool = True) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "state": "ok" if ok else "warn",
        "detail": detail,
        "required": required,
    }


def clean_text(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize_message(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())
