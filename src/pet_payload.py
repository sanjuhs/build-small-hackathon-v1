from __future__ import annotations

from typing import Any

from src.pet_memory import load_memories
from src.pet_profiles import normalize_pet


def compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    scene = payload.get("scene") or {}
    pet_state = scene.get("pet") if isinstance(scene.get("pet"), dict) else {}
    objects = scene.get("objects") or []
    pet = normalize_pet(payload.get("pet"))
    compact_objects = sorted(
        [
            {
                "id": item.get("id"),
                "kind": item.get("kind"),
                "name": str(item.get("name") or "")[:54],
                "generated": bool(item.get("generated")),
                "speed": round(float(item.get("speed") or 0), 2),
                "distanceToPet": round(float(item.get("distanceToPet") or 0), 2),
                "moving": bool(item.get("moving")),
                "affordances": compact_string_list(item.get("affordances"), 6),
                "tags": compact_string_list(item.get("tags"), 6),
                "nutrition": round(float(item.get("nutrition") or 0), 1),
                "readable": bool(item.get("readable")),
                "comfort": round(float(item.get("comfort") or 0), 1),
                "social": round(float(item.get("social") or 0), 1),
            }
            for item in objects[:18]
        ],
        key=lambda item: item["distanceToPet"],
    )
    return {
        "pet": pet,
        "user_message": str(payload.get("message") or "")[:240],
        "objects": compact_objects,
        "arrangements": detect_scene_arrangements(objects),
        "agents": compact_agents(scene.get("agents")),
        "memories": compact_memories(payload.get("memories")) or load_memories(pet, limit=8),
        "recentForces": (payload.get("forces") or [])[-8:],
        "detectedObjects": (payload.get("detectedObjects") or [])[:10],
        "vision": payload.get("vision") or {},
        "audio": compact_audio(payload.get("audio")),
        "needs": compact_needs(pet_state.get("needs")),
        "balance": compact_balance(pet_state.get("balance")),
        "cameraFrameSource": str(payload.get("cameraFrameSource") or "")[:32],
        "interactions": (payload.get("interactions") or [])[-8:],
        "cooldowns": payload.get("cooldowns") or {},
    }


def target_from_payload(payload: dict[str, Any]) -> str:
    scene = payload.get("scene") or {}
    objects = scene.get("objects") or []
    moving = [item for item in objects if float(item.get("speed") or 0) > 0.8]
    candidates = moving or objects
    if not candidates:
        return "all-moving"
    nearest = sorted(candidates, key=lambda item: float(item.get("distanceToPet") or 999))[0]
    return str(nearest.get("id") or "all-moving")


def target_ids_from_payload(payload: dict[str, Any]) -> list[str]:
    scene = payload.get("scene") or {}
    object_ids = [
        str(item.get("id"))
        for item in scene.get("objects", [])
        if item.get("id")
    ]
    return list(dict.fromkeys(object_ids + ["all-moving"]))


def detect_scene_arrangements(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positioned = [item for item in objects if isinstance(item.get("position"), dict) and item.get("id")]
    if len(positioned) < 2:
        return generated_arrangements(positioned)

    arrangements: list[dict[str, Any]] = []
    arrangements.extend(stack_arrangements(positioned))
    arrangements.extend(line_arrangements(positioned))
    arrangements.extend(cluster_arrangements(positioned))
    arrangements.extend(generated_arrangements(positioned))
    deduped = []
    seen = set()
    for item in sorted(arrangements, key=lambda value: float(value.get("confidence") or 0), reverse=True):
        key = (item.get("kind"), tuple(item.get("objectIds") or []))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= 4:
            break
    return deduped


def stack_arrangements(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stacks = []
    used: set[str] = set()
    for base in objects:
        if base.get("id") in used:
            continue
        column = [
            item
            for item in objects
            if horizontal_distance(base, item) <= 0.52
        ]
        column = sorted(column, key=lambda item: coord(item, "y"))
        if len(column) < 2:
            continue
        height_span = coord(column[-1], "y") - coord(column[0], "y")
        if height_span < 0.55:
            continue
        ids = [str(item.get("id")) for item in column[:4]]
        used.update(ids)
        stacks.append({
            "kind": "stack",
            "label": "tiny tower",
            "objectIds": ids,
            "confidence": min(0.96, 0.58 + height_span / 3),
            "summary": f"{object_label(column[-1])} is perched above {object_label(column[0])}.",
        })
    return stacks


def line_arrangements(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(objects) < 3:
        return []
    arrangements = []
    by_x = sorted(objects, key=lambda item: coord(item, "x"))
    by_z = sorted(objects, key=lambda item: coord(item, "z"))
    for axis, ordered, cross_axis in [("x", by_x, "z"), ("z", by_z, "x")]:
        group = tightest_line_group(ordered, axis, cross_axis)
        if len(group) < 3:
            continue
        spread = coord(group[-1], axis) - coord(group[0], axis)
        if spread < 1.0:
            continue
        ids = [str(item.get("id")) for item in group[:8]]
        kinds = {str(item.get("kind") or "") for item in group}
        label = "domino parade" if "domino" in kinds else "toy line"
        arrangements.append({
            "kind": "line",
            "label": label,
            "objectIds": ids,
            "confidence": min(0.94, 0.54 + spread / 6),
            "summary": f"{len(ids)} objects form a {label}.",
        })
    return arrangements[:2]


def tightest_line_group(objects: list[dict[str, Any]], axis: str, cross_axis: str) -> list[dict[str, Any]]:
    best: list[dict[str, Any]] = []
    for index, item in enumerate(objects):
        group = [
            candidate
            for candidate in objects[index:]
            if abs(coord(candidate, cross_axis) - coord(item, cross_axis)) <= 0.42
        ]
        if len(group) > len(best):
            best = group
    return sorted(best, key=lambda item: coord(item, axis))


def cluster_arrangements(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(objects) < 3:
        return []
    clusters = []
    for item in objects:
        group = [
            candidate
            for candidate in objects
            if horizontal_distance(item, candidate) <= 0.9
        ]
        if len(group) < 3:
            continue
        ids = [str(candidate.get("id")) for candidate in sorted(group, key=lambda value: horizontal_distance(item, value))[:6]]
        clusters.append({
            "kind": "cluster",
            "label": "toy huddle",
            "objectIds": ids,
            "confidence": min(0.72, 0.44 + len(ids) / 14),
            "summary": f"{len(ids)} objects are gathered into a toy huddle.",
        })
    return clusters[:1]


def generated_arrangements(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    generated = [item for item in objects if item.get("generated")]
    if not generated:
        return []
    return [{
        "kind": "generated_object",
        "label": "wished toy",
        "objectIds": [str(item.get("id")) for item in generated[:4]],
        "confidence": 0.9,
        "summary": f"Player-wished object present: {', '.join(object_label(item) for item in generated[:3])}.",
    }]


def horizontal_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    dx = coord(a, "x") - coord(b, "x")
    dz = coord(a, "z") - coord(b, "z")
    return (dx * dx + dz * dz) ** 0.5


def coord(item: dict[str, Any], key: str) -> float:
    position = item.get("position") if isinstance(item.get("position"), dict) else {}
    try:
        return float(position.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def object_label(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("id") or item.get("kind") or "object")[:54]


def latest_touch(payload: dict[str, Any]) -> dict[str, Any] | None:
    interactions = payload.get("interactions") or []
    return next((item for item in reversed(interactions) if item.get("kind") in {"pet", "poke"}), None)


def trace_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compact = compact_payload(payload)
    camera_frame = payload.get("cameraFrame")
    compact["cameraFrame"] = {
        "present": bool(camera_frame),
        "bytesApprox": len(camera_frame) if isinstance(camera_frame, str) else 0,
        "source": str(payload.get("cameraFrameSource") or "")[:32],
    }
    return compact


def compact_audio(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    input_audio = compact_audio_channel(value.get("input"))
    output_audio = compact_audio_channel(value.get("output"))
    root = compact_audio_channel(value)
    peak = max(root["peak"], input_audio["peak"], output_audio["peak"])
    rms = max(root["rms"], input_audio["rms"], output_audio["rms"])
    return {
        "active": bool(value.get("active")) or input_audio["active"] or output_audio["active"],
        "source": str(value.get("source") or "")[:32],
        "peak": peak,
        "rms": rms,
        "bands": root["bands"],
        "input": input_audio,
        "output": output_audio,
    }


def compact_audio_channel(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"active": False, "peak": 0.0, "rms": 0.0, "bands": []}
    bands = value.get("bands") if isinstance(value.get("bands"), list) else []
    return {
        "active": bool(value.get("active")),
        "peak": round(float(value.get("peak") or 0), 2),
        "rms": round(float(value.get("rms") or 0), 2),
        "bands": [
            round(float(item or 0), 2)
            for item in bands[:10]
            if isinstance(item, (int, float))
        ],
    }


def compact_needs(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        "hunger": round(float(value.get("hunger") or 0), 1),
        "curiosity": round(float(value.get("curiosity") or 0), 1),
        "energy": round(float(value.get("energy") or 0), 1),
        "social": round(float(value.get("social") or 0), 1),
    }


def compact_balance(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    center = value.get("centerOfMass") if isinstance(value.get("centerOfMass"), dict) else {}
    return {
        "active": bool(value.get("active")),
        "stability": round(float(value.get("stability") or 0), 2),
        "tiltDeg": round(float(value.get("tiltDeg") or 0), 1),
        "speed": round(float(value.get("speed") or 0), 2),
        "mass": round(float(value.get("mass") or 0), 2),
        "centerOfMass": {
            "x": round(float(center.get("x") or 0), 2),
            "y": round(float(center.get("y") or 0), 2),
            "z": round(float(center.get("z") or 0), 2),
        },
    }


def compact_agents(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    agents = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        position = item.get("position") if isinstance(item.get("position"), dict) else {}
        agents.append({
            "pet": normalize_pet(item.get("pet") or item.get("kind")),
            "label": str(item.get("label") or "")[:32],
            "emotion": str(item.get("emotion") or "")[:24],
            "lastIntent": str(item.get("lastIntent") or "")[:80],
            "distanceToPet": round(float(item.get("distanceToPet") or 0), 2),
            "position": {
                "x": round(float(position.get("x") or 0), 2),
                "y": round(float(position.get("y") or 0), 2),
                "z": round(float(position.get("z") or 0), 2),
            },
        })
    return agents


def compact_memories(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    memories = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        memories.append({
            "pet": normalize_pet(item.get("pet")),
            "concept": str(item.get("concept") or "")[:48],
            "meaning": str(item.get("meaning") or "")[:180],
            "source": str(item.get("source") or "")[:40],
        })
    return memories


def compact_string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:32] for item in value[:limit]]
