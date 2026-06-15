from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ExpertState:
    stage: str = "pregrasp"
    ticks: int = 0


class PickBallIkExpert:
    """Privileged bimanual demonstrator for bootstrapping behavior cloning."""

    def __init__(self, env):
        self.env = env
        self.action_dim = env.action_dim
        self.state = ExpertState()
        self.anchor: np.ndarray | None = None

    def reset(self) -> None:
        self.state = ExpertState()
        self.anchor = None

    def act(self, obs: dict) -> np.ndarray:
        ball = np.asarray(obs["ball_pos"], dtype=np.float32)
        mouth = np.asarray(obs.get("mouth_pos", [0.30, 0.0, 1.48]), dtype=np.float32)
        right_target, left_target = self._targets_for_stage(ball, mouth)
        action = self.env.action_for_hand_targets(right_target, left_target)
        self._advance(
            np.asarray(obs["right_hand_pos"], dtype=np.float32),
            np.asarray(obs["left_hand_pos"], dtype=np.float32),
            ball,
            mouth,
        )
        return action

    def _targets_for_stage(self, ball: np.ndarray, mouth: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        safe_ball = ball.copy()
        safe_ball[2] = max(float(safe_ball[2]), 0.82)
        anchored_ball = self.anchor if self.anchor is not None else safe_ball
        task = getattr(self.env.config, "task", "pick_ball")
        if self.state.stage == "pregrasp":
            return (
                safe_ball + np.array([0.00, -0.30, 0.30], dtype=np.float32),
                safe_ball + np.array([0.00, 0.30, 0.30], dtype=np.float32),
            )
        if self.state.stage == "descend":
            y_offset = 0.30 - min(0.10, 0.006 * self.state.ticks)
            z_offset = 0.30 - min(0.26, 0.012 * self.state.ticks)
            return (
                safe_ball + np.array([0.02, -y_offset, z_offset], dtype=np.float32),
                safe_ball + np.array([0.02, y_offset, z_offset], dtype=np.float32),
            )
        if self.state.stage == "close":
            y_offset = 0.20 - min(0.125, 0.0035 * self.state.ticks)
            return (
                anchored_ball + np.array([0.02, -y_offset, 0.04], dtype=np.float32),
                anchored_ball + np.array([0.02, y_offset, 0.04], dtype=np.float32),
            )
        if self.state.stage == "mouth" and task == "eat_berry":
            mouth_target = np.asarray(mouth if mouth is not None else [0.30, 0.0, 1.48], dtype=np.float32)
            return (
                mouth_target + np.array([0.03, -0.095, 0.045], dtype=np.float32),
                mouth_target + np.array([0.03, 0.095, 0.045], dtype=np.float32),
            )
        lift_height = min(0.24, 0.04 + 0.0025 * self.state.ticks)
        return (
            anchored_ball + np.array([0.02, -0.095, lift_height], dtype=np.float32),
            anchored_ball + np.array([0.02, 0.095, lift_height], dtype=np.float32),
        )

    def _advance(self, right: np.ndarray, left: np.ndarray, ball: np.ndarray, mouth: np.ndarray | None = None) -> None:
        self.state.ticks += 1
        task = getattr(self.env.config, "task", "pick_ball")
        right_target, left_target = self._targets_for_stage(ball, mouth)
        right_err = float(np.linalg.norm(right - right_target))
        left_err = float(np.linalg.norm(left - left_target))
        center = 0.5 * (right + left)
        center_dist = float(np.linalg.norm(center - ball))
        hand_span = float(np.linalg.norm(right - left))

        if self.state.stage == "pregrasp" and self.state.ticks > 3 and max(right_err, left_err) < 0.08:
            self.state = ExpertState("descend")
        elif self.state.stage == "descend" and self.state.ticks > 26 and (getattr(self.env, "grasped", False) or (center_dist < 0.24 and hand_span < 0.48)):
            self.anchor = ball.copy()
            self.anchor[2] = max(float(self.anchor[2]), 0.82)
            self.state = ExpertState("close")
        elif self.state.stage == "close" and self.state.ticks > 55:
            self.state = ExpertState("lift")
        elif self.state.stage == "lift" and task == "eat_berry" and self.state.ticks > 38:
            self.state = ExpertState("mouth")
