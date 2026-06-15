from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class PetPose:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    holding: str | None = None


@dataclass
class SkillResult:
    skill: str
    lane: str
    success: bool
    pose: PetPose
    path: list[tuple[float, float]] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class PetSkillController:
    """High-level pet skills that a VLA can select and parameterize."""

    def __init__(self) -> None:
        self.pose = PetPose()

    def route_text(self, instruction: str) -> tuple[str, dict[str, Any]]:
        text = instruction.lower()
        if "berry" in text and ("eat" in text or "find" in text):
            return "find_and_eat_berry", {"object": "berry"}
        if "pick" in text or "grab" in text:
            return "pick_up", {}
        if "drop" in text or "put down" in text:
            return "drop_object", {}
        if "run" in text and "around" in text:
            return "run_around", {"radius": 0.55}
        if "walk" in text and "around" in text:
            return "walk_around", {"radius": 0.45}
        if "run" in text or "dash" in text or "sprint" in text:
            return "run_to", {"target": (0.8, 0.0)}
        if "walk" in text or "come" in text or "go to" in text or "move to" in text or "toward" in text or "towards" in text or "sit" in text:
            return "walk_to", {"target": (0.55, 0.0)}
        if "turn" in text or "look" in text:
            return "turn_to", {"yaw": math.radians(30.0)}
        if "wave" in text:
            return "wave", {}
        if "sit" in text:
            return "sit", {}
        if "dance" in text:
            return "dance", {}
        return "idle", {}

    def execute_text(self, instruction: str) -> SkillResult:
        skill, params = self.route_text(instruction)
        return self.execute(skill, **params)

    def execute(self, skill: str, **params: Any) -> SkillResult:
        if skill in {"walk_to", "run_to"}:
            target = params.get("target", (0.5, 0.0))
            speed = 1.4 if skill == "run_to" else 0.55
            return self._move_to(skill, target, speed)
        if skill in {"walk_around", "run_around"}:
            radius = float(params.get("radius", 0.45))
            speed = 1.3 if skill == "run_around" else 0.5
            return self._move_around(skill, radius, speed)
        if skill == "turn_to":
            self.pose.yaw = float(params.get("yaw", self.pose.yaw))
            return SkillResult(skill, "protomotions_locomotion", True, self.pose, details={"yaw": self.pose.yaw})
        if skill in {"idle", "wave", "sit", "dance"}:
            lane = "protomotions_pose" if skill in {"sit", "dance"} else "local_pose"
            return SkillResult(skill, lane, True, self.pose, details={"animation": skill})
        if skill in {"pick_up", "pick_ball"}:
            self.pose.holding = "ball"
            return SkillResult(skill, "mujoco_bimanual", True, self.pose, details={"object": "ball"})
        if skill == "drop_object":
            dropped = self.pose.holding
            self.pose.holding = None
            return SkillResult(skill, "mujoco_bimanual", dropped is not None, self.pose, details={"object": dropped})
        if skill == "find_and_eat_berry":
            self.pose.holding = None
            return SkillResult(
                skill,
                "mujoco_bimanual_policy",
                True,
                self.pose,
                details={
                    "object": params.get("object", "berry"),
                    "steps": ["search", "approach", "two_hand_grasp", "bring_to_mouth", "eat"],
                },
            )
        if skill == "recover_balance":
            return SkillResult(skill, "protomotions_locomotion", True, self.pose, details={"recover": True})
        raise ValueError(f"unknown skill: {skill}")

    def _move_to(self, skill: str, target: tuple[float, float], speed: float) -> SkillResult:
        tx, ty = float(target[0]), float(target[1])
        start = np.array([self.pose.x, self.pose.y], dtype=np.float32)
        end = np.array([tx, ty], dtype=np.float32)
        delta = end - start
        distance = float(np.linalg.norm(delta))
        steps = max(2, int(distance / max(speed * 0.1, 1e-3)))
        path = []
        for alpha in np.linspace(0.0, 1.0, steps):
            point = start * (1.0 - alpha) + end * alpha
            path.append((float(point[0]), float(point[1])))
        self.pose.x = tx
        self.pose.y = ty
        if distance > 1e-5:
            self.pose.yaw = math.atan2(float(delta[1]), float(delta[0]))
        return SkillResult(skill, "protomotions_locomotion", True, self.pose, path, {"speed": speed})

    def _move_around(self, skill: str, radius: float, speed: float) -> SkillResult:
        center = np.array([self.pose.x, self.pose.y], dtype=np.float32)
        points = []
        for theta in np.linspace(0.0, 2.0 * math.pi, 17):
            point = center + np.array([math.cos(theta), math.sin(theta)], dtype=np.float32) * radius
            points.append((float(point[0]), float(point[1])))
        self.pose.x, self.pose.y = points[-1]
        self.pose.yaw += 2.0 * math.pi
        return SkillResult(skill, "protomotions_locomotion", True, self.pose, points, {"speed": speed, "radius": radius})


SUPPORTED_SKILLS = [
    "idle",
    "walk_to",
    "walk_around",
    "run_to",
    "run_around",
    "turn_to",
    "wave",
    "sit",
    "dance",
    "pick_up",
    "pick_ball",
    "find_and_eat_berry",
    "drop_object",
    "recover_balance",
]
