from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from src.command_coercion import command_target_id
from src.pet_actions import validate_action


ROOT = Path(__file__).resolve().parents[1]
FIREBOY_VLA_ROOT = ROOT / "fireboy-vla-physics"
FIREBOY_RUNPOD_ARTIFACT_ROOT = ROOT / "Fireboy-training-policy-vla" / "runpod-artifacts"
DEFAULT_POLICY = FIREBOY_VLA_ROOT / "checkpoints" / "berry_eat_wide" / "state_policy.npz"
DEFAULT_OUT_DIR = FIREBOY_VLA_ROOT / "build" / "toy-v3-policy"
VLA_SKILL_PARAM_MANIFEST = (
    ROOT
    / "Fireboy-training-policy-vla"
    / "runpod-artifacts"
    / "checkpoints"
    / "fireboy_minicpm_vla_skill_param_head"
    / "fireboy_vla_skill_params_allskill.jsonl"
)
RETARGET_JOINT_NAMES = [
    "root_x",
    "root_y",
    "root_z",
    "root_yaw",
    "spine_pitch",
    "chest_yaw",
    "neck_yaw",
    "head_pitch",
    "shoulder_R_yaw",
    "shoulder_R_pitch",
    "shoulder_R_roll",
    "elbow_R",
    "wrist_R_pitch",
    "wrist_R_roll",
    "finger_R_a",
    "finger_R_b",
    "shoulder_L_yaw",
    "shoulder_L_pitch",
    "shoulder_L_roll",
    "elbow_L",
    "wrist_L_pitch",
    "wrist_L_roll",
    "finger_L_a",
    "finger_L_b",
    "hip_R_yaw",
    "hip_R_pitch",
    "knee_R",
    "ankle_R",
    "hip_L_yaw",
    "hip_L_pitch",
    "knee_L",
    "ankle_L",
]


def should_use_mujoco_policy(payload: dict[str, Any]) -> bool:
    if os.getenv("TOYBOX_MUJOCO_POLICY_ENABLED", "1").lower() in {"0", "false", "no"}:
        return False
    message = str(payload.get("message") or "").lower()
    movement_words = ("walk", "run around", "go to", "move to", "yellow marker")
    return (
        "mujoco" in message
        or "physics policy" in message
        or "learned policy" in message
        or any(word in message for word in movement_words)
    )


def run_mujoco_pet_action(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not should_use_mujoco_policy(payload):
        return None
    if not DEFAULT_POLICY.exists():
        return _unavailable_action(payload, f"missing policy: {DEFAULT_POLICY}")

    started = time.perf_counter()
    command = str(payload.get("message") or "go find berry and eat it").strip() or "go find berry and eat it"
    out_dir = DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    python_bin = _python_bin()
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{FIREBOY_VLA_ROOT / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    env.setdefault("MUJOCO_GL", "glfw")
    cmd = [
        str(python_bin),
        str(FIREBOY_VLA_ROOT / "src" / "pet_runtime.py"),
        command,
        "--policy",
        str(DEFAULT_POLICY),
        "--out-dir",
        str(out_dir),
        "--smooth-alpha",
        "0.25",
    ]
    if os.getenv("TOYBOX_MUJOCO_RENDER_LIVE", "").lower() not in {"1", "true", "yes"}:
        cmd.append("--no-render")

    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=float(os.getenv("TOYBOX_MUJOCO_TIMEOUT", "45")),
            check=False,
        )
    except Exception as exc:
        return _unavailable_action(payload, f"policy runner failed: {exc}")

    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "unknown MuJoCo runner error").strip()[-500:]
        return _unavailable_action(payload, detail)

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return _unavailable_action(payload, f"invalid MuJoCo JSON: {exc}")

    rollout = result.get("policy_rollout") if isinstance(result.get("policy_rollout"), dict) else {}
    articulated = result.get("articulated_policy_rollout") if isinstance(result.get("articulated_policy_rollout"), dict) else {}
    if articulated:
        success = bool(result.get("success") and articulated.get("success"))
    else:
        if result.get("skill") == "pick_up":
            success = bool(result.get("success") and rollout.get("success") and rollout.get("grasped"))
        else:
            success = bool(result.get("success") and rollout.get("success") and rollout.get("eaten"))
    if not success:
        return _unavailable_action(payload, f"MuJoCo policy did not complete: {result}")

    media_rollout = articulated or rollout
    registry_entry = result.get("policy_registry_entry") if isinstance(result.get("policy_registry_entry"), dict) else {}
    registry_mp4_path = _registry_media_path(registry_entry, "proof_mp4")
    gif_path = Path(str(media_rollout.get("gif_path") or out_dir / "learned_berry_eat.gif"))
    mp4_path = registry_mp4_path or Path(str(media_rollout.get("mp4_path") or ""))
    is_movement = bool(articulated)
    is_pickup = result.get("skill") == "pick_up"
    wants_run = _command_requests_run(command)
    movement_target_id = _movement_target_id(payload) if is_movement and result.get("skill") != "run_around" else "self"
    target_id = movement_target_id if is_movement else _policy_target_id(payload, prefer_edible=not is_pickup)
    interaction_verb = "run" if is_movement and (result.get("skill") == "run_around" or wants_run) else "walk" if is_movement else "pickup" if is_pickup else "eat"
    retarget_trajectory = _retarget_trajectory(result.get("skill"), media_rollout)
    action = {
        "pet": payload.get("pet") or "fire_boy",
        "speech": "Me used MuJoCo feet." if is_movement else "Me picked it up." if is_pickup else "Me did learned berry move.",
        "emotion": "focused" if is_movement else "glee",
        "animation": "run" if interaction_verb == "run" else "walk" if is_movement else "hold",
        "intent": "mujoco_articulated_policy" if is_movement else "mujoco_learned_pick_up" if is_pickup else "mujoco_learned_berry_eat",
        "blendshape": {"eye": 0.16, "smile": 0.72, "mouth": 0.34, "brow": 0.08, "cheek": 0.3, "squash": 0.05, "tilt": 0.08, "sparkle": 0.8},
        "power": {"name": "ember_jump", "targetId": "self", "strength": 0.32, "durationMs": 900},
        "interaction": {"verb": interaction_verb, "targetId": target_id, "partnerPet": "", "durationMs": 2600 if is_movement else 1800},
        "spell": {
            "spellName": "learned MuJoCo articulated policy" if is_movement else "learned MuJoCo berry policy",
            "ops": [{"op": "spawn_particle", "targetId": "self", "durationMs": 900, "color": "#ff704d"}],
        },
        "sound": "ember_purr",
        "newMemory": None,
        "objectRecipe": None,
        "soundRecipe": None,
        "debug": {
            "policy": "mujoco_articulated_policy" if is_movement else "mujoco_state_action_policy",
            "provider": "local_mujoco",
            "serverLatencyMs": elapsed_ms,
            "mujocoPolicy": {
                "success": success,
                "skill": result.get("skill"),
                "lane": result.get("lane"),
                "gifPath": str(gif_path),
                "gifUrl": _static_url_for(gif_path),
                "mp4Path": str(mp4_path) if str(mp4_path) else "",
                "mp4Url": _static_url_for(mp4_path) if str(mp4_path) else "",
                "mediaSource": "registry_proof_mp4" if registry_mp4_path else "runtime_rollout",
                "registryProofMp4Path": str(registry_mp4_path) if registry_mp4_path else "",
                "registryProofMp4Url": _static_url_for(registry_mp4_path) if registry_mp4_path else "",
                "policyPath": result.get("policy_path"),
                "registryEntry": registry_entry,
                "smoothAlpha": rollout.get("smooth_alpha"),
                "grasped": media_rollout.get("grasped"),
                "eaten": media_rollout.get("eaten"),
                "finalRootXY": media_rollout.get("final_root_xy"),
                "targetXY": media_rollout.get("target_xy"),
                "retargetTrajectory": retarget_trajectory,
            },
        },
    }
    validated = validate_action(action, payload)
    validated["debug"] = action["debug"]
    return validated


def _python_bin() -> Path:
    configured = os.getenv("TOYBOX_MUJOCO_PYTHON")
    if configured:
        return Path(configured)
    venv_python = FIREBOY_VLA_ROOT / ".venv" / "bin" / "python"
    return venv_python if venv_python.exists() else Path(sys.executable)


def _berry_target_id(payload: dict[str, Any]) -> str:
    scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else {}
    objects = scene.get("objects") if isinstance(scene.get("objects"), list) else []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        affordances = obj.get("affordances")
        if not isinstance(affordances, list):
            affordances = []
        kind = str(obj.get("kind") or obj.get("type") or "").lower()
        if kind in {"berry", "food"} or "eat" in affordances:
            return str(obj.get("id") or "berry-rose")
    return "berry-rose"


def _policy_target_id(payload: dict[str, Any], *, prefer_edible: bool) -> str:
    if prefer_edible:
        return _berry_target_id(payload)
    try:
        return command_target_id(payload, {"box", "cube", "block", "toy", "ball", "orb", "berry", "food"})
    except Exception:
        return _berry_target_id(payload)


def _movement_target_id(payload: dict[str, Any]) -> str:
    message = str(payload.get("message") or payload.get("command") or "").lower()
    if any(term in message for term in ("toward me", "towards me", "to me", "come here", "camera", "viewer", "player")):
        scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else {}
        objects = scene.get("objects") if isinstance(scene.get("objects"), list) else []
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            terms = {
                str(obj.get("id") or "").lower(),
                str(obj.get("kind") or "").lower(),
                *(str(tag).lower() for tag in (obj.get("tags") or []) if isinstance(obj.get("tags"), list)),
            }
            if {"player-camera", "viewer", "camera", "me"} & terms:
                return str(obj.get("id") or "player-camera")
        return "player-camera"
    try:
        return command_target_id(
            payload,
            {
                "viewer",
                "camera",
                "player",
                "me",
                "go_to",
                "follow",
                "marker",
                "ball",
                "sphere",
                "orb",
                "cube",
                "block",
                "toy",
                "berry",
                "food",
                "chair",
                "seat",
                "table",
                "desk",
                "lamp",
                "light",
                "plant",
                "pot",
                "book",
                "clock",
            },
        )
    except Exception:
        return "self"


def _command_requests_run(command: str) -> bool:
    lowered = str(command or "").lower()
    return any(word in lowered for word in ("run", "running", "dash", "sprint", "race", "zoom"))


def _retarget_trajectory(skill: Any, rollout: dict[str, Any]) -> dict[str, Any] | None:
    trajectory = rollout.get("retarget_trajectory")
    if isinstance(trajectory, dict) and trajectory.get("frames"):
        return trajectory
    task = _manifest_task_for_skill(str(skill or ""))
    if not task:
        return None
    return _manifest_retarget_trajectory(task)


def _manifest_task_for_skill(skill: str) -> str:
    if skill == "pick_up":
        return "pick_up"
    if skill == "find_and_eat_berry":
        return "go_eat_berry"
    if skill in {"walk_to", "go_to_point"}:
        return "go_to_point"
    if skill in {"run_around", "walk_around"}:
        return "run_around"
    return ""


def _manifest_retarget_trajectory(task: str, max_frames: int = 96) -> dict[str, Any] | None:
    if not VLA_SKILL_PARAM_MANIFEST.exists():
        return None
    episodes: dict[int, list[dict[str, Any]]] = {}
    successes: set[int] = set()
    try:
        with VLA_SKILL_PARAM_MANIFEST.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("task") != task:
                    continue
                episode_id = int(row.get("episode_id") or 0)
                episodes.setdefault(episode_id, []).append(row)
                if row.get("success_so_far") or row.get("grasped") or row.get("eaten"):
                    successes.add(episode_id)
    except Exception:
        return None
    if not episodes:
        return None
    chosen_id = next((episode_id for episode_id in sorted(successes) if episode_id in episodes), sorted(episodes)[0])
    rows = sorted(episodes[chosen_id], key=lambda item: int(item.get("step") or 0))
    if not rows:
        return None
    if len(rows) > max_frames:
        stride = max(1, len(rows) // max_frames)
        rows = rows[::stride][:max_frames]
    frames = []
    for row in rows:
        qpos = _row_qpos(row)
        if len(qpos) >= 39:
            values = qpos[7 : 7 + len(RETARGET_JOINT_NAMES)]
        elif len(qpos) >= len(RETARGET_JOINT_NAMES):
            values = qpos[: len(RETARGET_JOINT_NAMES)]
        else:
            continue
        frames.append(
            {
                "step": int(row.get("step") or len(frames)),
                "stage": str(row.get("stage") or ""),
                "values": [round(float(value), 5) for value in values],
            }
        )
    if not frames:
        return None
    return {
        "format": "fireboy_articulated_pose_v1",
        "source": "minicpm_vla_rollout_manifest",
        "task": task,
        "episodeId": chosen_id,
        "joint_names": RETARGET_JOINT_NAMES,
        "fps": 24,
        "duration_ms": int(max(1200, len(frames) * 1000 / 24)),
        "frames": frames,
    }


def _row_qpos(row: dict[str, Any]) -> list[float]:
    state = row.get("robot_state") if isinstance(row.get("robot_state"), dict) else row
    qpos = state.get("qpos") if isinstance(state, dict) else None
    if isinstance(qpos, list):
        return [float(value) for value in qpos if isinstance(value, (int, float))]
    return []


def _registry_media_path(entry: dict[str, Any], key: str) -> Path | None:
    value = entry.get(key)
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = ROOT / path
    return path if path.exists() else None


def _static_url_for(path: Path) -> str:
    if not path:
        return ""
    roots = (
        (FIREBOY_VLA_ROOT, "/fireboy-vla"),
        (FIREBOY_RUNPOD_ARTIFACT_ROOT, "/fireboy-runpod-artifacts"),
    )
    resolved = path.resolve()
    for root, prefix in roots:
        try:
            rel = resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return f"{prefix}/{rel.as_posix()}"
    try:
        rel = path.resolve().relative_to(FIREBOY_VLA_ROOT.resolve())
    except ValueError:
        return ""
    return "/fireboy-vla/" + rel.as_posix()


def _unavailable_action(payload: dict[str, Any], reason: str) -> dict[str, Any]:
    target_id = _berry_target_id(payload)
    action = {
        "pet": payload.get("pet") or "fire_boy",
        "speech": "Me tried physics brain, then used toy room paws.",
        "emotion": "focused",
        "animation": "reach",
        "intent": "mujoco_policy_unavailable",
        "blendshape": {"eye": 0.04, "smile": 0.28, "mouth": 0.16, "brow": 0.14, "cheek": 0.12, "squash": 0.0, "tilt": 0.04, "sparkle": 0.28},
        "power": {"name": "ember_jump", "targetId": "self", "strength": 0.18, "durationMs": 700},
        "interaction": {"verb": "eat", "targetId": target_id, "partnerPet": "", "durationMs": 1600},
        "spell": {
            "spellName": "local fallback sparkle",
            "ops": [{"op": "spawn_particle", "targetId": "self", "durationMs": 700, "color": "#ffd75a"}],
        },
        "sound": "soft_pop",
        "newMemory": None,
        "objectRecipe": None,
        "soundRecipe": None,
        "debug": {
            "policy": "mujoco_policy_fallback",
            "provider": "local_mujoco",
            "reason": str(reason)[:500],
            "mujocoPolicy": {"success": False, "reason": str(reason)[:500]},
        },
    }
    validated = validate_action(action, payload)
    validated["debug"] = action["debug"]
    return validated
