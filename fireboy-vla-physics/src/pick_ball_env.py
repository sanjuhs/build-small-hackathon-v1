from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from fireboy_mjcf import ACTUATED_JOINTS, DEFAULT_XML_PATH, write_default_mjcf


@dataclass
class PickBallConfig:
    xml_path: Path = DEFAULT_XML_PATH
    width: int = 160
    height: int = 120
    max_steps: int = 180
    camera: str = "agent_cam"
    frame_skip: int = 6
    seed: int = 1
    render: bool = True
    task: str = "pick_ball"


class PickBallEnv:
    def __init__(self, config: PickBallConfig | None = None):
        self.config = config or PickBallConfig()
        if self.config.xml_path == DEFAULT_XML_PATH or not self.config.xml_path.exists():
            write_default_mjcf(self.config.xml_path)
        try:
            import mujoco
        except ImportError as exc:
            raise RuntimeError("Install fireboy-vla-physics/requirements.txt before using PickBallEnv") from exc

        self.mujoco = mujoco
        self.model = mujoco.MjModel.from_xml_path(str(self.config.xml_path))
        self.data = mujoco.MjData(self.model)
        self.renderer = mujoco.Renderer(self.model, height=self.config.height, width=self.config.width) if self.config.render else None
        self.rng = np.random.default_rng(self.config.seed)
        self.step_count = 0
        self.start_ball_z = 0.82
        self.grasped = False
        self.eaten = False
        self.grasp_offset = np.zeros(3, dtype=np.float64)
        self.last_action = np.zeros(self.model.nu, dtype=np.float32)
        self.ctrl_low, self.ctrl_high = self._ctrl_ranges()
        self.actuated_joint_names = list(ACTUATED_JOINTS)
        self._ids = self._lookup_ids()
        self._joint_qpos = self._joint_qpos_addresses()

    @property
    def action_dim(self) -> int:
        return int(self.model.nu)

    @property
    def proprio_dim(self) -> int:
        return int(self.model.nq + self.model.nv + self.model.nu)

    def reset(self, seed: int | None = None) -> dict[str, Any]:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.mujoco.mj_resetData(self.model, self.data)
        self.step_count = 0
        self.grasped = False
        self.eaten = False
        self.grasp_offset[:] = 0
        self.last_action[:] = 0
        self._randomize_ball()
        self.mujoco.mj_forward(self.model, self.data)
        ball = np.asarray(self.data.xpos[self._ids["ball_body"]], dtype=np.float64).copy()
        self._set_hand_positions(*self.pregrasp_targets(ball))
        self.mujoco.mj_forward(self.model, self.data)
        return self._obs()

    def step(self, action: np.ndarray) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        action = np.asarray(action, dtype=np.float32).reshape(-1)
        if action.shape[0] != self.model.nu:
            raise ValueError(f"action must have shape ({self.model.nu},), got {action.shape}")
        clipped = np.clip(action, -1.0, 1.0)
        ctrl = self.ctrl_low + (clipped + 1.0) * 0.5 * (self.ctrl_high - self.ctrl_low)
        self.data.ctrl[:] = ctrl
        for _ in range(self.config.frame_skip):
            self.mujoco.mj_step(self.model, self.data)
            self._update_grasp_constraint()
        self.step_count += 1
        self.last_action[:] = clipped
        obs = self._obs()
        reward, success = self._reward(obs)
        terminated = bool(success)
        truncated = self.step_count >= self.config.max_steps
        return obs, reward, terminated, truncated, {
            "success": bool(success),
            "grasped": bool(self.grasped),
            "eaten": bool(self.eaten),
        }

    def render_rgb(self) -> np.ndarray:
        if self.renderer is None:
            return np.zeros((self.config.height, self.config.width, 3), dtype=np.uint8)
        self.renderer.update_scene(self.data, camera=self.config.camera)
        return self.renderer.render()

    def pregrasp_targets(self, ball: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        ball = np.asarray(ball, dtype=np.float64)
        return (
            ball + np.array([0.0, -0.30, 0.30], dtype=np.float64),
            ball + np.array([0.0, 0.30, 0.30], dtype=np.float64),
        )

    def action_for_hand_targets(self, right_target: np.ndarray, left_target: np.ndarray) -> np.ndarray:
        ctrl = np.array(
            [
                right_target[0],
                right_target[1],
                right_target[2],
                left_target[0],
                left_target[1],
                left_target[2],
            ],
            dtype=np.float32,
        )
        ctrl = np.clip(ctrl, self.ctrl_low, self.ctrl_high)
        return self.normalized_action_from_ctrl(ctrl)

    def normalized_action_from_ctrl(self, ctrl: np.ndarray) -> np.ndarray:
        ctrl = np.asarray(ctrl, dtype=np.float32)
        return np.clip(2.0 * (ctrl - self.ctrl_low) / np.maximum(1e-6, self.ctrl_high - self.ctrl_low) - 1.0, -1.0, 1.0)

    def close(self) -> None:
        if self.renderer is not None:
            self.renderer.close()

    def _set_hand_positions(self, right_target: np.ndarray, left_target: np.ndarray) -> None:
        targets = {
            "hand_R_x": float(right_target[0]),
            "hand_R_y": float(right_target[1]),
            "hand_R_z": float(right_target[2]),
            "hand_L_x": float(left_target[0]),
            "hand_L_y": float(left_target[1]),
            "hand_L_z": float(left_target[2]),
        }
        for index, name in enumerate(self.actuated_joint_names):
            value = float(np.clip(targets[name], self.ctrl_low[index], self.ctrl_high[index]))
            self.data.qpos[self._joint_qpos[name]] = value
            self.data.ctrl[index] = value
        self.data.qvel[:] = 0.0

    def _ctrl_ranges(self) -> tuple[np.ndarray, np.ndarray]:
        ranges = np.asarray(self.model.actuator_ctrlrange, dtype=np.float32)
        return ranges[:, 0], ranges[:, 1]

    def _lookup_ids(self) -> dict[str, int]:
        mujoco = self.mujoco
        ball_joint_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "ball_free")
        return {
            "right_hand_site": mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "right_hand_site"),
            "left_hand_site": mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "left_hand_site"),
            "mouth_site": mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "mouth_site"),
            "ball_body": mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "ball"),
            "ball_joint_qpos": self.model.jnt_qposadr[ball_joint_id],
            "ball_joint_qvel": self.model.jnt_dofadr[ball_joint_id],
        }

    def _joint_qpos_addresses(self) -> dict[str, int]:
        out = {}
        for name in self.actuated_joint_names:
            jid = self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_JOINT, name)
            out[name] = int(self.model.jnt_qposadr[jid])
        return out

    def _randomize_ball(self) -> None:
        x = self.rng.uniform(0.61, 0.70)
        y = self.rng.uniform(-0.03, 0.03)
        z = 0.82
        self.start_ball_z = z
        qadr = self._ids["ball_joint_qpos"]
        self.data.qpos[qadr:qadr + 7] = np.array([x, y, z, 1, 0, 0, 0], dtype=np.float64)
        vadr = self.model.jnt_dofadr[self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_JOINT, "ball_free")]
        self.data.qvel[vadr:vadr + 6] = 0

    def _obs(self) -> dict[str, Any]:
        right_hand = np.asarray(self.data.site_xpos[self._ids["right_hand_site"]], dtype=np.float32).copy()
        left_hand = np.asarray(self.data.site_xpos[self._ids["left_hand_site"]], dtype=np.float32).copy()
        mouth = np.asarray(self.data.site_xpos[self._ids["mouth_site"]], dtype=np.float32).copy()
        ball = np.asarray(self.data.xpos[self._ids["ball_body"]], dtype=np.float32).copy()
        return {
            "image": self.render_rgb(),
            "instruction": "find the berry and eat it" if self.config.task == "eat_berry" else "pick up the berry with both hands",
            "qpos": np.asarray(self.data.qpos, dtype=np.float32).copy(),
            "qvel": np.asarray(self.data.qvel, dtype=np.float32).copy(),
            "ctrl": np.asarray(self.data.ctrl, dtype=np.float32).copy(),
            "previous_action": self.last_action.copy(),
            "right_hand_pos": right_hand,
            "left_hand_pos": left_hand,
            "mouth_pos": mouth,
            "ball_pos": ball,
            "grasped": self.grasped,
            "eaten": self.eaten,
            "step": self.step_count,
        }

    def _reward(self, obs: dict[str, Any]) -> tuple[float, bool]:
        right = obs["right_hand_pos"]
        left = obs["left_hand_pos"]
        ball = obs["ball_pos"]
        center = 0.5 * (right + left)
        center_dist = float(np.linalg.norm(center - ball))
        hand_span = float(np.linalg.norm(right - left))
        reach = max(0.0, 1.0 - center_dist / 0.55)
        clamp = max(0.0, 1.0 - abs(hand_span - 0.19) / 0.30)
        lift = max(0.0, float(ball[2] - self.start_ball_z) / 0.20)
        if self.config.task == "eat_berry":
            mouth = obs["mouth_pos"]
            mouth_dist = float(np.linalg.norm(ball - mouth))
            eat_reach = max(0.0, 1.0 - mouth_dist / 0.8)
            success = bool(self.eaten)
            return reach + clamp + 2.0 * lift + 3.0 * eat_reach + (12.0 if success else 0.0), success
        success = bool(ball[2] > self.start_ball_z + 0.09 and center_dist < 0.18)
        return reach + clamp + 3.0 * lift + (8.0 if success else 0.0), success

    def _update_grasp_constraint(self) -> None:
        if self.eaten:
            return
        right = np.asarray(self.data.site_xpos[self._ids["right_hand_site"]], dtype=np.float64)
        left = np.asarray(self.data.site_xpos[self._ids["left_hand_site"]], dtype=np.float64)
        ball = np.asarray(self.data.xpos[self._ids["ball_body"]], dtype=np.float64)
        mouth = np.asarray(self.data.site_xpos[self._ids["mouth_site"]], dtype=np.float64)
        center = 0.5 * (right + left)
        center_dist = float(np.linalg.norm(center - ball))
        hand_span = float(np.linalg.norm(right - left))

        if not self.grasped:
            hand_center_above_ball_bottom = center[2] > ball[2] - 0.02
            enclosed = hand_span < 0.58 and center_dist < 0.32 and ball[2] > 0.55 and hand_center_above_ball_bottom
            if not enclosed:
                return
            self.grasped = True
            self.grasp_offset[:] = ball - center
            self.grasp_offset[2] = np.clip(self.grasp_offset[2], -0.08, 0.02)

        qadr = self._ids["ball_joint_qpos"]
        vadr = self._ids["ball_joint_qvel"]
        target = center + self.grasp_offset
        target[2] = max(target[2], 0.74)
        self.data.qpos[qadr:qadr + 3] = target
        self.data.qpos[qadr + 3:qadr + 7] = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self.data.qvel[vadr:vadr + 6] = 0.0
        if self.config.task == "eat_berry" and np.linalg.norm(target - mouth) < 0.13:
            self.eaten = True
            self.data.qpos[qadr:qadr + 3] = np.array([0.0, 0.0, -2.0], dtype=np.float64)
            self.data.qvel[vadr:vadr + 6] = 0.0
        self.mujoco.mj_forward(self.model, self.data)
