from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"
DEFAULT_XML_PATH = BUILD_DIR / "fireboy_two_hand_pick_ball.xml"


ACTUATED_JOINTS = [
    "hand_R_x",
    "hand_R_y",
    "hand_R_z",
    "hand_L_x",
    "hand_L_y",
    "hand_L_z",
]


def build_fireboy_pick_ball_mjcf() -> str:
    """Return a bimanual MuJoCo pickup harness with high-friction hand tips."""

    actuator_xml = "\n".join(
        f'    <position name="{joint}_pos" joint="{joint}" kp="{kp_for_joint(joint)}" ctrlrange="{ctrlrange_for_joint(joint)}"/>'
        for joint in ACTUATED_JOINTS
    )

    xml = f"""
    <mujoco model="fireboy_two_hand_pick_ball">
      <compiler angle="degree" coordinate="local"/>
      <option timestep="0.004" gravity="0 0 -9.81" iterations="160" noslip_iterations="20" solver="Newton" cone="elliptic"/>

      <default>
        <geom contype="1" conaffinity="1" friction="1.2 0.04 0.002" density="450" rgba="0.9 0.35 0.22 1"/>
        <joint damping="3.0" armature="0.04" limited="true"/>
        <position ctrllimited="true" forcelimited="true" forcerange="-20000 20000"/>
      </default>

      <asset>
        <texture name="grid" type="2d" builtin="checker" rgb1="0.74 0.70 0.62" rgb2="0.86 0.82 0.72" width="256" height="256"/>
        <material name="floor_mat" texture="grid" texrepeat="5 5" reflectance="0.05"/>
        <material name="fireboy_body" rgba="0.95 0.32 0.16 1"/>
        <material name="fireboy_head" rgba="1.0 0.58 0.25 1"/>
        <material name="flame" rgba="1.0 0.74 0.18 1"/>
        <material name="hand" rgba="1.0 0.70 0.43 1"/>
        <material name="grip_tip" rgba="0.10 0.10 0.10 1"/>
        <material name="ball_yellow" rgba="1.0 0.74 0.12 1"/>
        <material name="berry_red" rgba="0.72 0.05 0.16 1"/>
        <material name="mouth_marker" rgba="0.1 0.9 0.4 1"/>
      </asset>

      <worldbody>
        <light name="key" pos="0 -4 5" dir="0 1 -1" diffuse="0.9 0.86 0.78"/>
        <light name="fill" pos="-3 2 3" diffuse="0.35 0.45 0.55"/>
        <geom name="floor" type="plane" size="4 4 0.05" material="floor_mat"/>

        <camera name="world_cam" pos="2.1 -3.5 2.0" xyaxes="1 0 0 0 0.45 0.89" fovy="46"/>
        <geom name="pickup_table" type="box" pos="0.66 0 0.66" size="0.10 0.06 0.04" rgba="0.45 0.31 0.18 1"/>
        <site name="mouth_site" pos="0.30 0 1.48" size="0.045" material="mouth_marker"/>

        <body name="fireboy_visual" pos="0 0 0.62">
          <geom name="hips" type="capsule" fromto="0 0 0 0 0 0.46" size="0.22" material="fireboy_body" contype="0" conaffinity="0"/>
          <geom name="torso" type="capsule" fromto="0 0 0.38 0 0 0.92" size="0.24" material="fireboy_body" contype="0" conaffinity="0"/>
          <geom name="chest_geom" type="sphere" pos="0 0 0.88" size="0.28" material="fireboy_body" contype="0" conaffinity="0"/>
          <geom name="neck_geom" type="capsule" fromto="0 0 1.05 0 0 1.18" size="0.08" material="fireboy_body" contype="0" conaffinity="0"/>
          <geom name="head_geom" type="sphere" pos="0 0 1.35" size="0.22" material="fireboy_head" contype="0" conaffinity="0"/>
          <geom name="flame_geom" type="capsule" fromto="0 0 1.50 0 0 1.80" size="0.09" material="flame" contype="0" conaffinity="0"/>
          <geom name="arm_R_visual" type="capsule" fromto="0 -0.24 0.96 0.46 -0.22 0.78" size="0.07" material="fireboy_body" contype="0" conaffinity="0"/>
          <geom name="arm_L_visual" type="capsule" fromto="0 0.24 0.96 0.46 0.22 0.78" size="0.07" material="fireboy_body" contype="0" conaffinity="0"/>
          <geom name="leg_R_geom" type="capsule" fromto="0.12 0 -0.02 0.20 0 -0.48" size="0.08" material="fireboy_body" contype="0" conaffinity="0"/>
          <geom name="leg_L_geom" type="capsule" fromto="-0.12 0 -0.02 -0.20 0 -0.48" size="0.08" material="fireboy_body" contype="0" conaffinity="0"/>
          <geom name="foot_R_geom" type="box" pos="0.22 -0.04 -0.52" size="0.14 0.08 0.04" material="hand" contype="0" conaffinity="0"/>
          <geom name="foot_L_geom" type="box" pos="-0.22 -0.04 -0.52" size="0.14 0.08 0.04" material="hand" contype="0" conaffinity="0"/>
          <camera name="agent_cam" pos="0 -0.08 1.42" xyaxes="1 0 0 0 0.45 0.89" fovy="58"/>
        </body>

        <body name="hand_R" pos="0 0 0">
          <joint name="hand_R_x" type="slide" axis="1 0 0" range="0.20 0.95"/>
          <joint name="hand_R_y" type="slide" axis="0 1 0" range="-0.55 0.10"/>
          <joint name="hand_R_z" type="slide" axis="0 0 1" range="0.70 1.65"/>
          <site name="right_hand_site" pos="0 0 0" size="0.025" rgba="0 0.9 1 1"/>
          <geom name="hand_R_visual" type="sphere" size="0.065" material="hand" contype="0" conaffinity="0"/>
          <geom name="hand_R_tip" type="box" pos="0 0.035 0" size="0.16 0.045 0.11" material="grip_tip" contype="0" conaffinity="0"/>
          <geom name="hand_R_lower_lip" type="box" pos="0 0.075 -0.18" size="0.30 0.14 0.035" material="grip_tip" friction="12.0 0.35 0.03" condim="6"/>
        </body>

        <body name="hand_L" pos="0 0 0">
          <joint name="hand_L_x" type="slide" axis="1 0 0" range="0.20 0.95"/>
          <joint name="hand_L_y" type="slide" axis="0 1 0" range="-0.10 0.55"/>
          <joint name="hand_L_z" type="slide" axis="0 0 1" range="0.70 1.65"/>
          <site name="left_hand_site" pos="0 0 0" size="0.025" rgba="0 0.9 1 1"/>
          <geom name="hand_L_visual" type="sphere" size="0.065" material="hand" contype="0" conaffinity="0"/>
          <geom name="hand_L_tip" type="box" pos="0 -0.035 0" size="0.16 0.045 0.11" material="grip_tip" contype="0" conaffinity="0"/>
          <geom name="hand_L_lower_lip" type="box" pos="0 -0.075 -0.18" size="0.30 0.14 0.035" material="grip_tip" friction="12.0 0.35 0.03" condim="6"/>
        </body>

        <body name="ball" pos="0.66 0 0.82">
          <freejoint name="ball_free"/>
          <geom name="ball_geom" type="sphere" size="0.115" mass="0.045" material="berry_red" friction="6.0 0.25 0.015" condim="6"/>
        </body>
      </worldbody>

      <actuator>
{actuator_xml}
      </actuator>

      <sensor>
        <framepos name="right_hand_pos" objtype="site" objname="right_hand_site"/>
        <framepos name="left_hand_pos" objtype="site" objname="left_hand_site"/>
        <framepos name="mouth_pos" objtype="site" objname="mouth_site"/>
        <framepos name="ball_pos" objtype="body" objname="ball"/>
      </sensor>
    </mujoco>
    """
    return dedent(xml).strip() + "\n"


def kp_for_joint(joint: str) -> float:
    if joint.endswith("_z"):
        return 6000.0
    return 5000.0


def ctrlrange_for_joint(joint: str) -> str:
    ranges: dict[str, str] = {
        "hand_R_x": "0.20 0.95",
        "hand_R_y": "-0.55 0.10",
        "hand_R_z": "0.70 1.65",
        "hand_L_x": "0.20 0.95",
        "hand_L_y": "-0.10 0.55",
        "hand_L_z": "0.70 1.65",
    }
    return ranges[joint]


def write_default_mjcf(path: Path = DEFAULT_XML_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    xml = build_fireboy_pick_ball_mjcf()
    ElementTree.fromstring(xml)
    path.write_text(xml, encoding="utf-8")
    return path


if __name__ == "__main__":
    out = write_default_mjcf()
    print(out)
