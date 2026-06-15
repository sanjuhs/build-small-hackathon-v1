from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np

from fireboy_articulated_mjcf import ACTUATED_JOINTS, DEFAULT_XML_PATH, write_default_mjcf


DEFAULT_OUT_DIR = Path("fireboy-vla-physics/build/articulated")
EAT_DISTANCE = 0.14
RIGHT_IK_JOINTS = [
    "root_x",
    "root_y",
    "shoulder_R_yaw",
    "shoulder_R_pitch",
    "shoulder_R_roll",
    "elbow_R",
    "wrist_R_pitch",
    "wrist_R_roll",
]
RIGHT_ARM_ONLY_IK_JOINTS = [
    "shoulder_R_yaw",
    "shoulder_R_pitch",
    "shoulder_R_roll",
    "elbow_R",
    "wrist_R_pitch",
    "wrist_R_roll",
]
RIGHT_TO_MOUTH_IK_JOINTS = [
    "spine_pitch",
    "chest_yaw",
    "shoulder_R_yaw",
    "shoulder_R_pitch",
    "shoulder_R_roll",
    "elbow_R",
    "wrist_R_pitch",
    "wrist_R_roll",
]


@dataclass
class RolloutResult:
    mode: str
    success: bool
    frames: int
    gif_path: str | None
    mp4_path: str | None
    report: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "success": self.success,
            "frames": self.frames,
            "gif_path": self.gif_path,
            "mp4_path": self.mp4_path,
            "report": self.report,
        }


class ArticulatedFireboyDemo:
    def __init__(self, width: int = 640, height: int = 480, camera: str = "body_cam", render_enabled: bool = True):
        try:
            import mujoco
        except ImportError as exc:
            raise RuntimeError("Install fireboy-vla-physics requirements before rendering articulated Fireboy") from exc

        self.mujoco = mujoco
        write_default_mjcf()
        self.model = mujoco.MjModel.from_xml_path(str(DEFAULT_XML_PATH))
        self.data = mujoco.MjData(self.model)
        self.renderer = mujoco.Renderer(self.model, height=height, width=width) if render_enabled else None
        self.camera = camera
        self.free_cameras = {
            "body_cam": self.make_camera([0.08, 0.00, 0.56], 1.35, 190, -12),
            "front_cam": self.make_camera([0.20, -0.05, 0.50], 1.24, 150, -14),
            "world_cam": self.make_camera([0.03, 0.03, 0.50], 1.90, 165, -18),
        }
        self.actuator_ids = {
            name: mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, f"{name}_pos")
            for name in ACTUATED_JOINTS
        }
        self.joint_ids = {
            name: mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, name)
            for name in ACTUATED_JOINTS
        }
        self.qpos_addr = {name: int(self.model.jnt_qposadr[jid]) for name, jid in self.joint_ids.items()}
        self.dof_addr = {name: int(self.model.jnt_dofadr[jid]) for name, jid in self.joint_ids.items()}
        self.site_ids = {
            "right_hand": mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "right_hand_site"),
            "left_hand": mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "left_hand_site"),
            "mouth": mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "mouth_site"),
        }
        self.right_gripper_geom_ids = [
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, name)
            for name in ("palm_R", "finger_R_a_pad", "finger_R_b_pad")
        ]
        self._make_fireboy_visual_collision_light()
        berry_joint = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "berry_free")
        self.berry_qpos = int(self.model.jnt_qposadr[berry_joint])
        self.berry_qvel = int(self.model.jnt_dofadr[berry_joint])
        self.berry_body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "berry")

    def close(self) -> None:
        if self.renderer is not None:
            self.renderer.close()

    def reset(self) -> dict[str, float]:
        self.mujoco.mj_resetData(self.model, self.data)
        pose = self.rest_pose()
        self.set_pose(pose)
        self.set_berry(np.array([0.40, -0.10, 0.295], dtype=np.float64))
        self.mujoco.mj_forward(self.model, self.data)
        return pose

    def rest_pose(self) -> dict[str, float]:
        return {
            "root_x": 0.0,
            "root_y": 0.0,
            "root_z": 0.03,
            "root_yaw": deg(0),
            "spine_pitch": deg(0),
            "chest_yaw": deg(0),
            "neck_yaw": deg(0),
            "head_pitch": deg(0),
            "shoulder_R_yaw": deg(0),
            "shoulder_R_pitch": deg(0),
            "shoulder_R_roll": deg(0),
            "elbow_R": deg(0),
            "wrist_R_pitch": deg(0),
            "wrist_R_roll": deg(0),
            "finger_R_a": 0.055,
            "finger_R_b": 0.055,
            "shoulder_L_yaw": deg(0),
            "shoulder_L_pitch": deg(0),
            "shoulder_L_roll": deg(0),
            "elbow_L": deg(0),
            "wrist_L_pitch": deg(0),
            "wrist_L_roll": deg(0),
            "finger_L_a": 0.055,
            "finger_L_b": 0.055,
            "hip_R_yaw": deg(0),
            "hip_R_pitch": deg(0),
            "knee_R": deg(0),
            "ankle_R": deg(0),
            "hip_L_yaw": deg(0),
            "hip_L_pitch": deg(0),
            "knee_L": deg(0),
            "ankle_L": deg(0),
        }

    def set_pose(self, pose: dict[str, float]) -> None:
        for name, value in pose.items():
            if name not in self.qpos_addr:
                continue
            low, high = self.joint_range(name)
            clipped = float(np.clip(value, low, high))
            self.data.qpos[self.qpos_addr[name]] = clipped
            self.data.ctrl[self.actuator_ids[name]] = clipped
        self.mujoco.mj_forward(self.model, self.data)

    def set_ctrl(self, pose: dict[str, float]) -> None:
        for name, value in pose.items():
            if name not in self.actuator_ids:
                continue
            low, high = self.joint_range(name)
            self.data.ctrl[self.actuator_ids[name]] = float(np.clip(value, low, high))

    def blend_pose(self, start: dict[str, float], target: dict[str, float], alpha: float) -> dict[str, float]:
        return {name: lerp(start.get(name, 0.0), target.get(name, start.get(name, 0.0)), alpha) for name in start}

    def joint_range(self, name: str) -> tuple[float, float]:
        jid = self.joint_ids[name]
        low, high = self.model.jnt_range[jid]
        return float(low), float(high)

    def step(self, pose: dict[str, float], n: int = 1) -> None:
        self.set_ctrl(pose)
        for _ in range(n):
            self.mujoco.mj_step(self.model, self.data)

    def render(self) -> np.ndarray:
        if self.renderer is None:
            raise RuntimeError("This ArticulatedFireboyDemo was created with render_enabled=False")
        camera = self.free_cameras.get(self.camera, self.camera)
        self.renderer.update_scene(self.data, camera=camera)
        return self.renderer.render()

    def make_camera(self, lookat: list[float], distance: float, azimuth: float, elevation: float):
        cam = self.mujoco.MjvCamera()
        cam.type = self.mujoco.mjtCamera.mjCAMERA_FREE
        cam.lookat[:] = lookat
        cam.distance = distance
        cam.azimuth = azimuth
        cam.elevation = elevation
        return cam

    def site_pos(self, name: str) -> np.ndarray:
        return np.asarray(self.data.site_xpos[self.site_ids[name]], dtype=np.float64).copy()

    def berry_pos(self) -> np.ndarray:
        return np.asarray(self.data.xpos[self.berry_body], dtype=np.float64).copy()

    def set_berry(self, xyz: np.ndarray) -> None:
        self.data.qpos[self.berry_qpos:self.berry_qpos + 7] = np.array([xyz[0], xyz[1], xyz[2], 1, 0, 0, 0], dtype=np.float64)
        self.data.qvel[self.berry_qvel:self.berry_qvel + 6] = 0.0
        self.mujoco.mj_forward(self.model, self.data)

    def set_camera(self, camera: str) -> None:
        self.camera = camera

    def set_right_gripper_collision(self, enabled: bool) -> None:
        value = 1 if enabled else 0
        for gid in self.right_gripper_geom_ids:
            self.model.geom_contype[gid] = value
            self.model.geom_conaffinity[gid] = value

    def _make_fireboy_visual_collision_light(self) -> None:
        keep_contact = {"floor", "berry_table", "berry_geom"}
        for gid in range(self.model.ngeom):
            name = self.model.geom(gid).name
            if name in keep_contact:
                continue
            self.model.geom_contype[gid] = 0
            self.model.geom_conaffinity[gid] = 0

    def solve_right_hand_ik(
        self,
        pose: dict[str, float],
        target: np.ndarray,
        iterations: int = 34,
        joint_names: list[str] | None = None,
    ) -> dict[str, float]:
        q = pose.copy()
        names = joint_names or RIGHT_IK_JOINTS
        ik_cols = np.array([self.dof_addr[name] for name in names], dtype=np.int32)
        ik_qpos = [self.qpos_addr[name] for name in names]
        for _ in range(iterations):
            self.set_pose(q)
            current = self.site_pos("right_hand")
            err = np.asarray(target, dtype=np.float64) - current
            if float(np.linalg.norm(err)) < 0.012:
                break
            jacp = np.zeros((3, self.model.nv), dtype=np.float64)
            jacr = np.zeros((3, self.model.nv), dtype=np.float64)
            self.mujoco.mj_jacSite(self.model, self.data, jacp, jacr, self.site_ids["right_hand"])
            j = jacp[:, ik_cols]
            dq = j.T @ np.linalg.solve(j @ j.T + 0.035 * np.eye(3), 0.55 * err)
            for name, qadr, delta in zip(names, ik_qpos, dq):
                low, high = self.joint_range(name)
                q[name] = float(np.clip(self.data.qpos[qadr] + delta, low, high))
        self.set_pose(q)
        return q

    def solve_right_hand_to_mouth(
        self,
        pose: dict[str, float],
        attach_offset: np.ndarray,
        iterations: int = 64,
        joint_names: list[str] | None = None,
    ) -> dict[str, float]:
        q = pose.copy()
        names = joint_names or RIGHT_TO_MOUTH_IK_JOINTS
        ik_cols = np.array([self.dof_addr[name] for name in names], dtype=np.int32)
        ik_qpos = [self.qpos_addr[name] for name in names]
        for _ in range(iterations):
            self.set_pose(q)
            berry_from_hand = self.site_pos("right_hand") + attach_offset
            mouth = self.site_pos("mouth")
            err = mouth - berry_from_hand
            if float(np.linalg.norm(err)) < 0.018:
                break
            hand_jac = np.zeros((3, self.model.nv), dtype=np.float64)
            mouth_jac = np.zeros((3, self.model.nv), dtype=np.float64)
            jacr = np.zeros((3, self.model.nv), dtype=np.float64)
            self.mujoco.mj_jacSite(self.model, self.data, hand_jac, jacr, self.site_ids["right_hand"])
            self.mujoco.mj_jacSite(self.model, self.data, mouth_jac, jacr, self.site_ids["mouth"])
            j = hand_jac[:, ik_cols] - mouth_jac[:, ik_cols]
            dq = j.T @ np.linalg.solve(j @ j.T + 0.03 * np.eye(3), 0.65 * err)
            for name, qadr, delta in zip(names, ik_qpos, dq):
                low, high = self.joint_range(name)
                q[name] = float(np.clip(self.data.qpos[qadr] + delta, low, high))
        self.set_pose(q)
        return q


def render_articulated(mode: str, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    demo = ArticulatedFireboyDemo()
    try:
        if mode == "body":
            result = render_body(demo, out_dir)
        elif mode == "run":
            result = render_run(demo, out_dir)
        elif mode == "go":
            result = render_go_to_point(demo, out_dir)
        elif mode == "pick":
            result = render_pick(demo, out_dir, eat=False)
        elif mode == "eat":
            result = render_pick(demo, out_dir, eat=True)
        elif mode == "all":
            body = render_body(demo, out_dir)
            go = render_go_to_point(demo, out_dir)
            run = render_run(demo, out_dir)
            pick = render_pick(demo, out_dir, eat=False)
            eat = render_pick(demo, out_dir, eat=True)
            result = {
                "mode": "all",
                "body": body.as_dict(),
                "go": go.as_dict(),
                "run": run.as_dict(),
                "pick": pick.as_dict(),
                "eat": eat.as_dict(),
            }
        else:
            raise ValueError(f"Unknown articulated mode: {mode}")
    finally:
        demo.close()
    return result.as_dict() if isinstance(result, RolloutResult) else result


def render_body(demo: ArticulatedFireboyDemo, out_dir: Path) -> RolloutResult:
    demo.reset()
    demo.set_camera("body_cam")
    frames = []
    pose = demo.rest_pose()
    for i in range(88):
        wave = math.sin(i * 0.08)
        pose["head_pitch"] = deg(-5 + 3 * wave)
        pose["shoulder_R_pitch"] = deg(24 + 6 * wave)
        pose["shoulder_L_pitch"] = deg(24 - 6 * wave)
        demo.step(pose, 3)
        frames.append(demo.render())
    report = model_report(demo)
    media = save_media(frames, out_dir / "fireboy_articulated_body")
    imageio.imwrite(out_dir / "fireboy_articulated_body.png", frames[10])
    return RolloutResult("body", True, len(frames), media["gif"], media["mp4"], report)


def render_run(demo: ArticulatedFireboyDemo, out_dir: Path) -> RolloutResult:
    pose = demo.reset()
    demo.set_camera("world_cam")
    frames = []
    radius = 0.34
    center = np.array([0.04, 0.04], dtype=np.float64)
    for i in range(160):
        phase = i * 0.18
        theta = i / 159 * math.tau * 1.05
        pose["root_x"] = float(center[0] + radius * math.cos(theta))
        pose["root_y"] = float(center[1] + radius * math.sin(theta))
        pose["root_yaw"] = theta + math.pi / 2
        pose["spine_pitch"] = deg(4 + 2 * math.sin(phase))
        pose["chest_yaw"] = deg(8 * math.sin(phase))
        pose["hip_R_pitch"] = deg(20 * math.sin(phase))
        pose["knee_R"] = deg(22 + 28 * max(0.0, math.sin(phase + math.pi)))
        pose["ankle_R"] = deg(-8 * math.sin(phase))
        pose["hip_L_pitch"] = deg(20 * math.sin(phase + math.pi))
        pose["knee_L"] = deg(22 + 28 * max(0.0, math.sin(phase)))
        pose["ankle_L"] = deg(-8 * math.sin(phase + math.pi))
        pose["shoulder_R_pitch"] = deg(26 + 14 * math.sin(phase + math.pi))
        pose["shoulder_L_pitch"] = deg(26 + 14 * math.sin(phase))
        pose["elbow_R"] = deg(36 + 10 * max(0.0, math.sin(phase)))
        pose["elbow_L"] = deg(36 + 10 * max(0.0, math.sin(phase + math.pi)))
        demo.step(pose, 3)
        if i % 2 == 0:
            frames.append(demo.render())
    media = save_media(frames, out_dir / "fireboy_articulated_run_around")
    report = model_report(demo) | {
        "truth": "Run-around is an assisted root locomotion controller with articulated leg/arm gait. It is not a learned ProtoMotions policy yet.",
        "skill": "run_around",
    }
    return RolloutResult("run", True, len(frames), media["gif"], media["mp4"], report)


def render_go_to_point(demo: ArticulatedFireboyDemo, out_dir: Path) -> RolloutResult:
    pose = demo.reset()
    demo.set_camera("world_cam")
    frames = []
    target_xy = np.array([0.46, 0.18], dtype=np.float64)
    demo.set_berry(np.array([target_xy[0], target_xy[1], 0.295], dtype=np.float64))
    start_xy = np.array([pose["root_x"], pose["root_y"]], dtype=np.float64)
    heading = math.atan2(float(target_xy[1] - start_xy[1]), float(target_xy[0] - start_xy[0]))
    final_dist = float("inf")
    for i in range(150):
        alpha = smoothstep(i / 149)
        phase = i * 0.24
        xy = start_xy + (target_xy - start_xy) * alpha
        pose["root_x"] = float(xy[0])
        pose["root_y"] = float(xy[1])
        pose["root_yaw"] = heading
        pose["spine_pitch"] = deg(3 + 1.5 * math.sin(phase))
        pose["chest_yaw"] = deg(4 * math.sin(phase))
        add_walk_cycle(pose, phase, speed=0.85)
        demo.step(pose, 3)
        final_dist = float(np.linalg.norm(xy - target_xy))
        if i % 2 == 0:
            frames.append(demo.render())
    media = save_media(frames, out_dir / "fireboy_articulated_go_to_point")
    report = model_report(demo) | {
        "truth": "Go-to-point is an assisted controller baseline. The learned policy MP4 is rendered separately after training.",
        "skill": "go_to_point",
        "target_xy": target_xy.round(4).tolist(),
        "final_distance": round(final_dist, 4),
    }
    return RolloutResult("go", final_dist < 0.08, len(frames), media["gif"], media["mp4"], report)


def render_pick(demo: ArticulatedFireboyDemo, out_dir: Path, eat: bool) -> RolloutResult:
    pose = demo.reset()
    demo.set_camera("front_cam")
    demo.set_right_gripper_collision(False)
    frames: list[np.ndarray] = []
    grasped = False
    eaten = False
    berry_attached = False
    attach_offset = np.zeros(3, dtype=np.float64)
    min_mouth_dist = float("inf")

    stages = [
        ("approach", 38, np.array([0.10, -0.02, 0.0])),
        ("reach_above", 42, np.array([0.40, -0.10, 0.420])),
        ("descend", 34, np.array([0.40, -0.10, 0.305])),
        ("close", 28, np.array([0.40, -0.10, 0.305])),
        ("lift", 42, np.array([0.33, -0.10, 0.555])),
    ]
    if eat:
        stages.append(("mouth", 58, np.array([0.0, 0.0, 0.0])))

    current_pose = pose.copy()
    for stage, steps, target in stages:
        start_pose = current_pose.copy()
        if stage == "approach":
            target_pose = start_pose.copy()
            target_pose["root_x"] = float(target[0])
            target_pose["root_y"] = float(target[1])
            target_pose["root_yaw"] = deg(4)
            for i in range(steps):
                alpha = smoothstep(i / max(1, steps - 1))
                current_pose = demo.blend_pose(start_pose, target_pose, alpha)
                add_walk_cycle(current_pose, i * 0.35, speed=0.6)
                demo.step(current_pose, 4)
                if i % 2 == 0:
                    frames.append(demo.render())
            continue

        if stage == "mouth":
            target_pose = demo.solve_right_hand_to_mouth(start_pose, attach_offset, iterations=80)
        else:
            target_pose = demo.solve_right_hand_ik(start_pose, target)
        if stage in {"reach_above", "descend"}:
            target_pose["finger_R_a"] = 0.056
            target_pose["finger_R_b"] = 0.056
        if stage in {"close", "lift", "mouth"}:
            target_pose["finger_R_a"] = 0.014
            target_pose["finger_R_b"] = 0.014

        for i in range(steps):
            alpha = smoothstep(i / max(1, steps - 1))
            current_pose = demo.blend_pose(start_pose, target_pose, alpha)
            demo.set_right_gripper_collision(stage in {"close", "lift", "mouth"})
            demo.step(current_pose, 4)

            hand = demo.site_pos("right_hand")
            berry = demo.berry_pos()
            if stage == "close" and np.linalg.norm(hand - berry) < 0.14:
                grasped = True
                berry_attached = True
                attach_offset = berry - hand
                attach_offset[2] = np.clip(attach_offset[2], -0.018, 0.026)
            if berry_attached:
                berry_target = hand + attach_offset
                berry_target[2] = max(berry_target[2], 0.29)
                demo.set_berry(berry_target)
                berry = demo.berry_pos()
            if eat and stage == "mouth" and np.linalg.norm(demo.berry_pos() - demo.site_pos("mouth")) < EAT_DISTANCE:
                eaten = True
            min_mouth_dist = min(min_mouth_dist, float(np.linalg.norm(demo.berry_pos() - demo.site_pos("mouth"))))
            if i % 2 == 0:
                frames.append(demo.render())

    stem = out_dir / ("fireboy_articulated_go_eat_berry" if eat else "fireboy_articulated_pick_up")
    media = save_media(frames, stem)
    final_berry = demo.berry_pos()
    success = bool(eaten if eat else (grasped and final_berry[2] > 0.36))
    report = model_report(demo) | {
        "skill": "go_eat_berry" if eat else "pick_up",
        "success": success,
        "grasped": grasped,
        "eaten": eaten,
        "final_berry_pos": final_berry.round(4).tolist(),
        "min_mouth_dist": round(min_mouth_dist, 4) if math.isfinite(min_mouth_dist) else None,
        "truth": (
            "This uses the connected articulated Fireboy arm/wrist/gripper. "
            "The high-level rollout is still an expert/controller proof, not a trained general VLA policy."
        ),
    }
    return RolloutResult("eat" if eat else "pick", success, len(frames), media["gif"], media["mp4"], report)


def add_walk_cycle(pose: dict[str, float], phase: float, speed: float) -> None:
    pose["hip_R_pitch"] = deg(12 * math.sin(phase) * speed)
    pose["knee_R"] = deg(12 + 18 * max(0.0, math.sin(phase + math.pi)) * speed)
    pose["hip_L_pitch"] = deg(12 * math.sin(phase + math.pi) * speed)
    pose["knee_L"] = deg(12 + 18 * max(0.0, math.sin(phase)) * speed)
    pose["shoulder_R_pitch"] = deg(28 + 8 * math.sin(phase + math.pi) * speed)
    pose["shoulder_L_pitch"] = deg(28 + 8 * math.sin(phase) * speed)


def save_media(frames: list[np.ndarray], stem: Path) -> dict[str, str | None]:
    if not frames:
        return {"gif": None, "mp4": None}
    gif_path = stem.with_suffix(".gif")
    mp4_path = stem.with_suffix(".mp4")
    imageio.mimsave(gif_path, frames, duration=0.05)
    try:
        imageio.mimsave(mp4_path, frames, fps=20)
        mp4 = str(mp4_path)
    except Exception:
        mp4 = None
    return {"gif": str(gif_path), "mp4": mp4}


def model_report(demo: ArticulatedFireboyDemo) -> dict[str, Any]:
    return {
        "xml_path": str(DEFAULT_XML_PATH),
        "nbody": int(demo.model.nbody),
        "njnt": int(demo.model.njnt),
        "nu": int(demo.model.nu),
        "actuated_joints": list(ACTUATED_JOINTS),
        "body_tree": [
            "root slides/yaw -> pelvis",
            "pelvis -> spine -> chest -> neck -> head/flame",
            "chest -> right shoulder -> right elbow -> right wrist -> right gripper fingers",
            "chest -> left shoulder -> left elbow -> left wrist -> left gripper fingers",
            "pelvis -> hips -> knees -> ankles -> feet",
        ],
        "resembles_fireboy": [
            "orange capsule/sphere body",
            "round head and flame/crown",
            "short broad body proportions",
            "visible joint markers",
            "hands attached through shoulder/elbow/wrist chains",
        ],
        "not_yet": [
            "not using the original GLB mesh as a MuJoCo visual asset",
            "not a free-balanced humanoid locomotion policy",
            "not ProtoMotions yet",
        ],
    }


def deg(value: float) -> float:
    return math.radians(value)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(t: float) -> float:
    t = float(np.clip(t, 0.0, 1.0))
    return t * t * (3.0 - 2.0 * t)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["body", "go", "run", "pick", "eat", "all"], default="all")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    result = render_articulated(args.mode, args.out_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "articulated_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
