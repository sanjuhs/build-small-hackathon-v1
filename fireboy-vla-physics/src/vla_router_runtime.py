from __future__ import annotations

import base64
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from build_vla_skill_param_manifest import PARAM_NAMES, SKILL_NAMES


MODEL_ID = "openbmb/MiniCPM-V-4.6"
TASK_NAMES = ["pick_up", "go_eat_berry", "run_around", "go_to_point"]
STAGE_NAMES = ["approach", "reach_above", "descend", "close", "lift", "mouth", "run_loop", "walk_to"]

DEFAULT_CHECKPOINT = Path(
    "Fireboy-training-policy-vla/runpod-artifacts/checkpoints/"
    "fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt"
)


class MiniCPMSkillParamHead:
    def __init__(
        self,
        input_dim: int,
        skill_count: int,
        param_dim: int,
        hidden_dim: int = 512,
    ):
        import torch
        from torch import nn

        class Head(nn.Module):
            def __init__(self, input_dim: int, skill_count: int, param_dim: int, hidden_dim: int):
                super().__init__()
                self.trunk = nn.Sequential(
                    nn.Linear(input_dim, hidden_dim),
                    nn.SiLU(),
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.SiLU(),
                )
                self.skill_head = nn.Linear(hidden_dim, skill_count)
                self.param_head = nn.Linear(hidden_dim, param_dim)

            def forward(self, x: Any) -> tuple[Any, Any]:
                h = self.trunk(x)
                return self.skill_head(h), self.param_head(h)

        self.torch = torch
        self.model = Head(input_dim, skill_count, param_dim, hidden_dim)

    def to(self, device: Any) -> "MiniCPMSkillParamHead":
        self.model.to(device)
        return self

    def __call__(self, x: Any) -> tuple[Any, Any]:
        return self.model(x)

    def load_state_dict(self, state_dict: dict[str, Any]) -> None:
        self.model.load_state_dict(state_dict)

    def eval(self) -> None:
        self.model.eval()


class FireboyVLARouter:
    def __init__(
        self,
        checkpoint: Path = DEFAULT_CHECKPOINT,
        *,
        model_id: str | None = None,
    ):
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("Install torch before running the Fire Boy VLA router") from exc

        self.torch = torch
        self.checkpoint = Path(checkpoint)
        self.payload = torch.load(self.checkpoint, map_location="cpu")
        self.model_id = model_id or str(self.payload.get("model_id") or MODEL_ID)
        self.processor, self.minicpm = load_minicpm(self.model_id)
        self.minicpm.eval()
        for param in self.minicpm.parameters():
            param.requires_grad_(False)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.head = MiniCPMSkillParamHead(
            input_dim=int(self.payload["input_dim"]),
            skill_count=int(self.payload["skill_count"]),
            param_dim=int(self.payload["param_dim"]),
        ).to(self.device)
        self.head.load_state_dict(self.payload["head"])
        self.head.eval()

    def route(self, request: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        command = str(request.get("command") or request.get("message") or "").strip()
        if not command:
            command = "walk around"
        image_path, generated_image = image_path_from_request(request)
        state_features, state_source = state_features_from_request(request, int(self.payload["state_dim"]))

        vl = encode_minicpm_skill_param_prompt(
            self.processor,
            self.minicpm,
            image_path,
            command,
            downsample_mode=str(self.payload.get("downsample_mode", "16x")),
            max_slice_nums=int(self.payload.get("max_slice_nums", 9)),
        )
        features = np.concatenate(
            [
                (vl - np.asarray(self.payload["vl_mean"], dtype=np.float32)) / np.asarray(self.payload["vl_std"], dtype=np.float32),
                (np.asarray(state_features, dtype=np.float32) - np.asarray(self.payload["state_mean"], dtype=np.float32))
                / np.asarray(self.payload["state_std"], dtype=np.float32),
            ],
            axis=0,
        )
        with self.torch.no_grad():
            skill_logits, param_pred = self.head(
                self.torch.tensor(features, dtype=self.torch.float32, device=self.device).view(1, -1)
            )
            probs = self.torch.softmax(skill_logits, dim=-1).detach().cpu().numpy()[0]
            skill_id = int(np.argmax(probs))
            normalized_params = param_pred.detach().cpu().numpy()[0]
        params = normalized_params * np.asarray(self.payload["param_std"], dtype=np.float32) + np.asarray(
            self.payload["param_mean"], dtype=np.float32
        )
        neural_skill = SKILL_NAMES[skill_id]
        raw_params = {name: float(params[index]) for index, name in enumerate(PARAM_NAMES)}
        heuristic = heuristic_route(command, request)
        bounded_params = stabilize_params(bound_params(raw_params), heuristic, request)
        final_skill = stabilize_skill(neural_skill, heuristic, request)
        final_skill_id = int(SKILL_NAMES.index(final_skill))
        dispatch = dispatch_for_skill(final_skill)
        result = {
            "ok": True,
            "policy_kind": self.payload.get("policy_kind"),
            "model_id": self.model_id,
            "checkpoint": str(self.checkpoint),
            "device": str(self.device),
            "command": command,
            "skill": final_skill,
            "skill_id": final_skill_id,
            "skill_confidence": float(probs[skill_id]) if final_skill == neural_skill else float(probs[final_skill_id]),
            "neural_skill": neural_skill,
            "neural_skill_id": skill_id,
            "neural_skill_confidence": float(probs[skill_id]),
            "skill_probabilities": {name: float(probs[index]) for index, name in enumerate(SKILL_NAMES)},
            "params": bounded_params,
            "raw_params": raw_params,
            "param_names": list(PARAM_NAMES),
            "dispatch": dispatch,
            "state_source": state_source,
            "image_source": "generated_blank" if generated_image else "request_image",
            "heuristic": heuristic,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
        if generated_image:
            try:
                image_path.unlink(missing_ok=True)
            except Exception:
                pass
        return result


def load_minicpm(model_id: str) -> tuple[Any, Any]:
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None,
        trust_remote_code=True,
    )
    if not torch.cuda.is_available():
        model.to("cpu")
    return processor, model


def encode_minicpm_skill_param_prompt(
    processor: Any,
    model: Any,
    image_path: Path,
    instruction: str,
    *,
    downsample_mode: str,
    max_slice_nums: int,
) -> np.ndarray:
    import torch

    prompt = (
        "You are the vision-language planner for Fire Boy in a MuJoCo toy room. "
        "From the image, command, and robot state, choose the next pet skill and "
        "its continuous parameters. Valid skills are: "
        f"{', '.join(SKILL_NAMES)}. Command: {instruction}."
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "url": str(image_path)},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    try:
        inputs = apply_minicpm_chat_template(processor, messages, downsample_mode, max_slice_nums)
    except Exception:
        image = Image.open(image_path).convert("RGB")
        messages[0]["content"][0] = {"type": "image", "image": image}
        inputs = apply_minicpm_chat_template(processor, messages, downsample_mode, max_slice_nums)

    device = first_model_device(model)
    inputs = inputs.to(device)
    with torch.inference_mode():
        outputs = model(**inputs, output_hidden_states=True, return_dict=True)
    hidden_states = getattr(outputs, "hidden_states", None)
    if not hidden_states:
        raise RuntimeError("MiniCPM forward did not return hidden_states; cannot route Fire Boy action.")
    last_hidden = hidden_states[-1].float()
    attention = inputs.get("attention_mask")
    if attention is not None:
        mask = attention.to(last_hidden.device).unsqueeze(-1).float()
        pooled = (last_hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
    else:
        pooled = last_hidden.mean(dim=1)
    return pooled.squeeze(0).detach().cpu().numpy().astype(np.float32)


def apply_minicpm_chat_template(
    processor: Any,
    messages: list[dict[str, Any]],
    downsample_mode: str,
    max_slice_nums: int,
) -> Any:
    base_kwargs = {
        "tokenize": True,
        "add_generation_prompt": True,
        "return_dict": True,
        "return_tensors": "pt",
    }
    try:
        return processor.apply_chat_template(
            messages,
            **base_kwargs,
            processor_kwargs={
                "downsample_mode": downsample_mode,
                "max_slice_nums": max_slice_nums,
            },
        )
    except TypeError:
        return processor.apply_chat_template(
            messages,
            **base_kwargs,
            downsample_mode=downsample_mode,
            max_slice_nums=max_slice_nums,
        )


def first_model_device(model: Any) -> Any:
    for parameter in model.parameters():
        return parameter.device
    raise RuntimeError("Model has no parameters")


def route_with_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "policy_kind": "heuristic_fallback_no_gpu_model",
        "model_id": "",
        "checkpoint": "",
        "device": "none",
        **heuristic_route(str(payload.get("command") or payload.get("message") or ""), payload),
    }


def image_path_from_request(request: dict[str, Any]) -> tuple[Path, bool]:
    image_path = request.get("image_path")
    if image_path and Path(str(image_path)).exists():
        return Path(str(image_path)), False

    camera_frame = request.get("image") or request.get("camera_frame") or request.get("cameraFrame")
    if isinstance(camera_frame, str) and camera_frame.startswith("data:image/"):
        header, encoded = camera_frame.split(",", 1)
        suffix = ".jpg" if "jpeg" in header or "jpg" in header else ".png"
        tmp = tempfile.NamedTemporaryFile(prefix="fireboy-vla-", suffix=suffix, delete=False)
        tmp.write(base64.b64decode(encoded))
        tmp.close()
        return Path(tmp.name), False

    tmp = tempfile.NamedTemporaryFile(prefix="fireboy-vla-blank-", suffix=".png", delete=False)
    tmp.close()
    image = Image.new("RGB", (320, 320), (245, 241, 228))
    image.save(tmp.name)
    return Path(tmp.name), True


def state_features_from_request(request: dict[str, Any], state_dim: int) -> tuple[list[float], str]:
    direct = request.get("robot_state_features") or request.get("state_features")
    if isinstance(direct, list) and len(direct) == state_dim:
        return [float(value) for value in direct], "direct_features"

    robot_state = request.get("robot_state") if isinstance(request.get("robot_state"), dict) else {}
    if isinstance(robot_state.get("features"), list) and len(robot_state["features"]) == state_dim:
        return [float(value) for value in robot_state["features"]], "robot_state.features"

    raw = training_row_from_request(request)
    state = state_from_row(
        raw,
        include_stage_flags=bool(request.get("include_stage_flags", True)),
        state_mode=str(request.get("state_mode") or "nav_clock"),
    )
    if len(state) < state_dim:
        state.extend([0.0] * (state_dim - len(state)))
    elif len(state) > state_dim:
        state = state[:state_dim]
    return [float(value) for value in state], "constructed_nav_clock"


def state_from_row(raw: dict[str, Any], include_stage_flags: bool = False, state_mode: str = "full") -> list[float]:
    task_flags = raw.get("task_flags")
    if task_flags is None:
        task_flags = one_hot(str(raw.get("task", "pick_up")), TASK_NAMES)
    if state_mode in {"clock", "nav_clock"}:
        nav_state = navigation_features_from_row(raw) if state_mode == "nav_clock" else []
        state = (
            nav_state
            + list(raw.get("right_hand_pos", [0.0, 0.0, 0.0]))
            + list(raw.get("left_hand_pos", [0.0, 0.0, 0.0]))
            + list(raw.get("ball_pos", [0.0, 0.0, 0.0]))
            + list(raw.get("mouth_pos", [0.0, 0.0, 0.0]))
            + list(task_flags)
        )
        if state_mode == "nav_clock":
            state += list(raw.get("previous_action", [0.0, 0.0, -0.7, 0.0]))[:4]
    else:
        state = (
            list(raw["qpos"])
            + list(raw["qvel"])
            + list(raw["ctrl"])
            + list(raw["previous_action"])
            + list(raw.get("right_hand_pos", [0.0, 0.0, 0.0]))
            + list(raw.get("left_hand_pos", [0.0, 0.0, 0.0]))
            + list(raw.get("ball_pos", [0.0, 0.0, 0.0]))
            + list(raw.get("mouth_pos", [0.0, 0.0, 0.0]))
            + list(task_flags)
        )
    if include_stage_flags:
        flags = raw.get("stage_flags")
        if flags is None:
            flags = one_hot(str(raw.get("stage", "approach")), STAGE_NAMES)
        state += list(flags)
    state += [
        float(raw.get("step", 0)) / 250.0,
        1.0 if raw.get("grasped", False) else 0.0,
        1.0 if raw.get("eaten", False) else 0.0,
    ]
    return state


def one_hot(name: str, names: list[str]) -> list[float]:
    return [1.0 if item == name else 0.0 for item in names]


def navigation_features_from_row(raw: dict[str, Any]) -> list[float]:
    qpos = list(raw.get("qpos", []))
    root_x = float(qpos[7]) if len(qpos) > 7 else 0.0
    root_y = float(qpos[8]) if len(qpos) > 8 else 0.0
    root_yaw = float(qpos[10]) if len(qpos) > 10 else 0.0
    target = list(raw.get("ball_pos", [0.0, 0.0, 0.0]))
    target_x = float(target[0]) if len(target) > 0 else 0.0
    target_y = float(target[1]) if len(target) > 1 else 0.0
    return navigation_features(root_x, root_y, root_yaw, target_x, target_y)


def navigation_features(root_x: float, root_y: float, root_yaw: float, target_x: float, target_y: float) -> list[float]:
    dx = float(target_x - root_x)
    dy = float(target_y - root_y)
    distance = float(np.hypot(dx, dy))
    bearing = float(np.arctan2(dy, dx)) if distance > 1e-6 else 0.0
    relative_bearing = bearing - float(root_yaw)
    return [
        float(root_x),
        float(root_y),
        float(np.sin(root_yaw)),
        float(np.cos(root_yaw)),
        dx,
        dy,
        distance,
        float(np.sin(bearing)),
        float(np.cos(bearing)),
        float(np.sin(relative_bearing)),
        float(np.cos(relative_bearing)),
    ]


def training_row_from_request(request: dict[str, Any]) -> dict[str, Any]:
    command = str(request.get("command") or request.get("message") or "")
    target = target_from_request(request)
    robot_state = request.get("robot_state") if isinstance(request.get("robot_state"), dict) else {}
    root = robot_state.get("root_xy") or robot_state.get("root") or request.get("root_xy") or [0.0, 0.0]
    root_x = float(root[0]) if isinstance(root, list) and len(root) > 0 else 0.0
    root_y = float(root[1]) if isinstance(root, list) and len(root) > 1 else 0.0
    root_yaw = float(robot_state.get("root_yaw") or request.get("root_yaw") or 0.0)
    qpos = [0.0] * 11
    qpos[7] = root_x
    qpos[8] = root_y
    qpos[10] = root_yaw
    task = task_from_command(command)
    return {
        "qpos": qpos,
        "qvel": [],
        "ctrl": [],
        "previous_action": list(robot_state.get("previous_action") or [0.0, 0.0, -0.7, 0.0]),
        "right_hand_pos": list(robot_state.get("right_hand_pos") or [0.16, -0.18, 0.62]),
        "left_hand_pos": list(robot_state.get("left_hand_pos") or [-0.16, -0.18, 0.62]),
        "ball_pos": target,
        "mouth_pos": list(robot_state.get("mouth_pos") or [0.0, -0.08, 0.82]),
        "task": task,
        "stage": stage_from_command(command),
        "step": int(robot_state.get("step") or request.get("step") or 0),
        "grasped": bool(robot_state.get("grasped") or request.get("grasped") or False),
        "eaten": bool(robot_state.get("eaten") or request.get("eaten") or False),
    }


def target_from_request(request: dict[str, Any]) -> list[float]:
    for key in ("target", "target_pos", "target_position", "ball_pos"):
        value = request.get(key)
        if isinstance(value, list) and len(value) >= 2:
            return [float(value[0]), float(value[1]), float(value[2]) if len(value) > 2 else 0.08]

    scene = request.get("scene") if isinstance(request.get("scene"), dict) else {}
    objects = scene.get("objects") if isinstance(scene.get("objects"), list) else []
    command = str(request.get("command") or request.get("message") or "").lower()
    preferred = None
    wants_viewer = any(term in command for term in ("toward me", "towards me", "to me", "come here", "camera", "viewer", "player"))
    wants_berry = any(word in command for word in ("berry", "eat", "snack", "pick", "grab", "hold"))
    wants_marker = any(word in command for word in ("marker", "there", "point")) or ("go" in command and not wants_berry)
    if wants_viewer:
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            kind = str(obj.get("kind") or "").lower()
            obj_id = str(obj.get("id") or "").lower()
            tags = obj.get("tags") if isinstance(obj.get("tags"), list) else []
            tag_terms = {str(tag).lower() for tag in tags}
            if obj_id == "player-camera" or kind == "viewer" or {"me", "camera", "viewer", "player"} & tag_terms:
                preferred = obj
                break
    if preferred is None:
        preferred = best_command_target(objects, command)
    for obj in objects:
        if preferred is not None:
            break
        if not isinstance(obj, dict):
            continue
        kind = str(obj.get("kind") or "").lower()
        affordances = obj.get("affordances") if isinstance(obj.get("affordances"), list) else []
        if wants_berry and (kind == "berry" or "eat" in affordances or "pick_up" in affordances):
            preferred = obj
            break
    if preferred is None:
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            kind = str(obj.get("kind") or "").lower()
            affordances = obj.get("affordances") if isinstance(obj.get("affordances"), list) else []
            if wants_marker and (kind == "marker" or "go_to" in affordances):
                preferred = obj
                break
            if preferred is None and (kind in {"berry", "ball", "marker"} or affordances):
                preferred = obj
    if preferred:
        position_value = preferred.get("position")
        if isinstance(position_value, dict):
            return [
                float(position_value.get("x", preferred.get("x", 0.42))),
                float(position_value.get("z", preferred.get("z", -0.1))),
                float(position_value.get("y", preferred.get("y", 0.08))),
            ]
        position = position_value if isinstance(position_value, list) else None
        if position:
            return [
                float(position[0]) if len(position) > 0 else 0.42,
                float(position[1]) if len(position) > 1 else -0.1,
                float(position[2]) if len(position) > 2 else 0.08,
            ]
        return [
            float(preferred.get("x", 0.42)),
            float(preferred.get("y", -0.1)),
            float(preferred.get("z", 0.08)),
        ]
    return [0.42, -0.1, 0.08]


TARGET_GROUP_ALIASES = {
    "berry": {"berry", "berries", "food", "snack"},
    "ball": {"ball", "sphere", "orb", "round"},
    "cube": {"cube", "block", "box"},
    "chair": {"chair", "seat", "stool", "sit"},
    "table": {"table", "desk"},
    "lamp": {"lamp", "light"},
    "plant": {"plant", "fern", "sprout", "pot"},
    "book": {"book", "notes", "story"},
    "clock": {"clock", "timer"},
    "bottle": {"bottle"},
    "can": {"can", "tin"},
    "paper": {"paper"},
    "waste": {"waste", "trash", "garbage", "peel"},
    "bin": {"bin", "recycle"},
    "ramp": {"ramp"},
    "domino": {"domino"},
}

TARGET_COLOR_ALIASES = {
    "blue": {"blue", "cyan", "teal"},
    "mint": {"mint", "green", "teal"},
    "green": {"green", "mint", "leaf", "fern"},
    "yellow": {"yellow", "amber", "honey", "gold", "golden"},
    "orange": {"orange", "coral", "ember", "fire"},
    "red": {"red", "rose", "pink"},
    "purple": {"purple", "violet", "moon"},
    "white": {"white", "pale", "cream"},
    "black": {"black", "dark"},
    "brown": {"brown", "wood", "wooden"},
}


def best_command_target(objects: list[Any], command: str) -> dict[str, Any] | None:
    command_terms = expanded_command_terms(command)
    requested_groups = {group for group, aliases in TARGET_GROUP_ALIASES.items() if aliases & command_terms}
    candidates = [obj for obj in objects if isinstance(obj, dict) and obj.get("id")]
    if requested_groups:
        grouped = [obj for obj in candidates if any(object_terms(obj) & TARGET_GROUP_ALIASES.get(group, {group}) for group in requested_groups)]
        if grouped:
            candidates = grouped
    best: tuple[float, float, dict[str, Any]] | None = None
    for obj in candidates:
        terms = object_terms(obj)
        score = float(sum(12 for term in command_terms if len(term) >= 3 and term in terms))
        for group in requested_groups:
            if terms & TARGET_GROUP_ALIASES.get(group, {group}):
                score += 18
        for color, aliases in TARGET_COLOR_ALIASES.items():
            if aliases & command_terms and aliases & terms:
                score += 14
        if "reading lamp" in command and str(obj.get("id")) == "reading-lamp":
            score += 12
        if "tea table" in command and str(obj.get("id")) == "tea-table":
            score += 12
        if score <= 0:
            continue
        distance = -float(obj.get("distanceToPet") or 999)
        candidate = (score, distance, obj)
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    return best[2] if best else None


def expanded_command_terms(command: str) -> set[str]:
    terms = {word for word in split_words(command) if len(word) >= 3}
    expanded = set(terms)
    for aliases in TARGET_GROUP_ALIASES.values():
        if aliases & terms:
            expanded |= aliases
    for aliases in TARGET_COLOR_ALIASES.values():
        if aliases & terms:
            expanded |= aliases
    return expanded


def object_terms(obj: dict[str, Any]) -> set[str]:
    fields = [
        str(obj.get("id") or ""),
        str(obj.get("kind") or ""),
        str(obj.get("name") or ""),
        " ".join(str(tag) for tag in (obj.get("tags") or []) if isinstance(obj.get("tags"), list)),
        " ".join(str(affordance) for affordance in (obj.get("affordances") or []) if isinstance(obj.get("affordances"), list)),
    ]
    terms = set(split_words(" ".join(fields).lower().replace("-", " ")))
    obj_id = str(obj.get("id") or "").lower()
    kind = str(obj.get("kind") or "").lower()
    if kind == "ball":
        terms.update({"sphere", "orb", "round", "toy"})
    elif kind == "berry":
        terms.update({"berries", "food", "snack", "sphere", "round"})
    elif kind == "cube":
        terms.update({"block", "box"})
    elif kind == "chair":
        terms.update({"seat", "furniture"})
    elif kind == "table":
        terms.update({"desk", "furniture"})
    elif kind == "lamp":
        terms.update({"light"})
    elif kind == "plant":
        terms.update({"fern", "sprout", "pot", "green"})
    if "blue" in obj_id:
        terms.update({"blue", "cyan", "teal"})
    if "mint" in obj_id:
        terms.update({"mint", "green", "teal"})
    if "coral" in obj_id:
        terms.update({"coral", "orange", "red"})
    if "honey" in obj_id:
        terms.update({"honey", "yellow", "gold", "golden"})
    if "amber" in obj_id:
        terms.update({"amber", "yellow", "orange", "gold", "golden"})
    if "ember" in obj_id or "fire" in obj_id:
        terms.update({"ember", "fire", "orange", "red", "warm"})
    if "moon" in obj_id:
        terms.update({"moon", "purple", "violet", "blue", "pale"})
    if "rose" in obj_id:
        terms.update({"rose", "red", "pink"})
    if "beach" in obj_id:
        terms.update({"beach", "white", "pale", "sphere", "orb"})
    if "reading-lamp" in obj_id:
        terms.update({"reading", "blue", "cyan", "lamp", "light"})
    elif "lamp" in obj_id:
        terms.update({"yellow", "warm", "lamp", "light"})
    if "fern" in obj_id or "sprout" in obj_id:
        terms.update({"green", "plant", "leaf"})
    if "paper" in obj_id:
        terms.update({"paper", "white", "waste", "trash", "sphere"})
    if "can" in obj_id:
        terms.update({"can", "tin", "metal", "waste"})
    if "bottle" in obj_id:
        terms.update({"bottle", "blue", "waste"})
    if "peel" in obj_id:
        terms.update({"peel", "banana", "yellow", "waste"})
    return terms


def split_words(value: str) -> list[str]:
    return [word for word in "".join(char if char.isalnum() else " " for char in value).split() if word]


def task_from_command(command: str) -> str:
    text = command.lower()
    if any(word in text for word in ("pick", "grab", "hold")):
        return "pick_up"
    if "run" in text and "around" in text:
        return "run_around"
    if any(word in text for word in ("eat", "snack")) or ("berry" in text and any(word in text for word in ("find", "go"))):
        return "go_eat_berry"
    return "go_to_point"


def stage_from_command(command: str) -> str:
    text = command.lower()
    if any(word in text for word in ("pick", "grab", "eat", "berry")):
        return "approach"
    if "run" in text:
        return "circle"
    return "navigate"


def heuristic_route(command: str, request: dict[str, Any]) -> dict[str, Any]:
    task = task_from_command(command)
    skill = {
        "go_eat_berry": "find_and_eat_berry",
        "pick_up": "pick_up",
        "run_around": "run_around",
        "go_to_point": "walk_to",
    }[task]
    target = target_from_request(request)
    params = {
        "target_x": float(target[0]),
        "target_y": float(target[1]),
        "target_z": float(target[2]),
        "radius": 0.55 if skill == "run_around" else 0.0,
        "speed_hint": 1.0 if skill == "run_around" else 0.55 if skill == "walk_to" else 0.25,
        "object_is_berry": 1.0 if task in {"go_eat_berry", "pick_up"} else 0.0,
    }
    return {
        "skill": skill,
        "skill_id": int(SKILL_NAMES.index(skill)),
        "params": params,
        "dispatch": dispatch_for_skill(skill),
    }


def dispatch_for_skill(skill: str) -> str:
    return {
        "walk_to": "registry:walk_to",
        "run_around": "registry:run_around",
        "pick_up": "registry:pick_up",
        "find_and_eat_berry": "registry:find_and_eat_berry",
    }.get(skill, "registry:walk_to")


def bound_params(params: dict[str, float]) -> dict[str, float]:
    bounded = dict(params)
    bounded["target_x"] = float(np.clip(bounded.get("target_x", 0.0), -2.5, 2.5))
    bounded["target_y"] = float(np.clip(bounded.get("target_y", 0.0), -2.5, 2.5))
    bounded["target_z"] = float(np.clip(bounded.get("target_z", 0.0), -0.2, 1.2))
    bounded["radius"] = float(np.clip(bounded.get("radius", 0.0), 0.0, 1.4))
    bounded["speed_hint"] = float(np.clip(bounded.get("speed_hint", 0.0), 0.0, 1.5))
    bounded["object_is_berry"] = float(np.clip(bounded.get("object_is_berry", 0.0), 0.0, 1.0))
    return bounded


def stabilize_params(params: dict[str, float], heuristic: dict[str, Any], request: dict[str, Any]) -> dict[str, float]:
    stable = dict(params)
    if request_has_explicit_target(request):
        heuristic_params = heuristic.get("params") if isinstance(heuristic.get("params"), dict) else {}
        for key in ("target_x", "target_y", "target_z"):
            if key in heuristic_params:
                stable[key] = float(heuristic_params[key])
        if str(heuristic.get("skill")) in {"run_around", "walk_to", "pick_up", "find_and_eat_berry"}:
            for key in ("radius", "speed_hint", "object_is_berry"):
                if key in heuristic_params:
                    stable[key] = float(heuristic_params[key])
    return bound_params(stable)


def stabilize_skill(neural_skill: str, heuristic: dict[str, Any], request: dict[str, Any]) -> str:
    if request.get("force_neural_skill"):
        return neural_skill
    command = str(request.get("command") or request.get("message") or "").lower()
    explicit_terms = ("eat", "berry", "pick", "grab", "hold", "run", "walk", "go", "marker", "there", "sit", "chair", "seat")
    heuristic_skill = str(heuristic.get("skill") or "")
    if heuristic_skill in SKILL_NAMES and any(term in command for term in explicit_terms):
        return heuristic_skill
    return neural_skill


def request_has_explicit_target(request: dict[str, Any]) -> bool:
    for key in ("target", "target_pos", "target_position", "ball_pos"):
        value = request.get(key)
        if isinstance(value, list) and len(value) >= 2:
            return True
    scene = request.get("scene") if isinstance(request.get("scene"), dict) else {}
    objects = scene.get("objects") if isinstance(scene.get("objects"), list) else []
    return any(isinstance(obj, dict) for obj in objects)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--request-json", type=Path)
    parser.add_argument("--command", default="go find berry and eat it")
    parser.add_argument("--fallback-only", action="store_true")
    args = parser.parse_args()
    request = {"command": args.command}
    if args.request_json:
        request.update(json.loads(args.request_json.read_text(encoding="utf-8")))
    if args.fallback_only:
        print(json.dumps(route_with_fallback(request), indent=2))
        return
    router = FireboyVLARouter(args.checkpoint)
    print(json.dumps(router.route(request), indent=2))


if __name__ == "__main__":
    main()
