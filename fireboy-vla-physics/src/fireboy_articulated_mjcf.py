from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"
DEFAULT_XML_PATH = BUILD_DIR / "fireboy_articulated.xml"


ROOT_JOINTS = [
    "root_x",
    "root_y",
    "root_z",
    "root_yaw",
]

UPPER_BODY_JOINTS = [
    "spine_pitch",
    "chest_yaw",
    "neck_yaw",
    "head_pitch",
]

RIGHT_ARM_JOINTS = [
    "shoulder_R_yaw",
    "shoulder_R_pitch",
    "shoulder_R_roll",
    "elbow_R",
    "wrist_R_pitch",
    "wrist_R_roll",
    "finger_R_a",
    "finger_R_b",
]

LEFT_ARM_JOINTS = [
    "shoulder_L_yaw",
    "shoulder_L_pitch",
    "shoulder_L_roll",
    "elbow_L",
    "wrist_L_pitch",
    "wrist_L_roll",
    "finger_L_a",
    "finger_L_b",
]

LEG_JOINTS = [
    "hip_R_yaw",
    "hip_R_pitch",
    "knee_R",
    "ankle_R",
    "hip_L_yaw",
    "hip_L_pitch",
    "knee_L",
    "ankle_L",
]

ACTUATED_JOINTS = ROOT_JOINTS + UPPER_BODY_JOINTS + RIGHT_ARM_JOINTS + LEFT_ARM_JOINTS + LEG_JOINTS


FIREBOY_GLB_POINTS = {
    # Canonicalized from fire-boy-rig/fire-boy-rigged-full.glb:
    # GLB Z is vertical and body width is mapped onto MuJoCo Y.
    "ankle_L": (0.00693, 0.11839, 0.05498),
    "ankle_R": (0.01167, -0.12179, 0.05498),
    "chest": (0.00193, 0.0, 0.39984),
    "crown": (0.0, 0.0, 1.15953),
    "elbow_L": (-0.00546, 0.23479, 0.35741),
    "elbow_R": (0.00011, -0.23561, 0.36300),
    "foot_L": (-0.08373, 0.12702, 0.00570),
    "foot_R": (-0.06928, -0.13015, -0.00904),
    "hand_L": (-0.01852, 0.35605, 0.20273),
    "hand_R": (-0.00641, -0.36212, 0.20594),
    "head": (0.0, 0.0, 0.55977),
    "hip_L": (0.00693, 0.11839, 0.25989),
    "hip_R": (0.01167, -0.12179, 0.25989),
    "knee_L": (-0.00806, 0.11839, 0.15744),
    "knee_R": (-0.00332, -0.12179, 0.15744),
    "neck": (0.0, 0.0, 0.49980),
    "pelvis": (0.00772, 0.0, 0.15994),
    "shoulder_L": (0.00222, 0.16346, 0.44840),
    "shoulder_R": (0.00395, -0.16119, 0.45539),
    "spine": (0.00386, 0.0, 0.27989),
    "wrist_L": (-0.01199, 0.29542, 0.28007),
    "wrist_R": (-0.00315, -0.29886, 0.28447),
}


def fmt_vec(value: tuple[float, float, float]) -> str:
    return f"{value[0]:.5f} {value[1]:.5f} {value[2]:.5f}"


def rel_vec(child: str, parent: str) -> str:
    c = FIREBOY_GLB_POINTS[child]
    p = FIREBOY_GLB_POINTS[parent]
    return fmt_vec((c[0] - p[0], c[1] - p[1], c[2] - p[2]))


def point_vec(name: str) -> str:
    return fmt_vec(FIREBOY_GLB_POINTS[name])


def build_fireboy_articulated_mjcf() -> str:
    actuator_xml = "\n".join(
        f'    <position name="{joint}_pos" joint="{joint}" kp="{kp_for_joint(joint)}" '
        f'ctrlrange="{ctrlrange_for_joint(joint)}"/>'
        for joint in ACTUATED_JOINTS
    )

    xml = f"""
    <mujoco model="fireboy_articulated">
      <compiler angle="degree" coordinate="local"/>
      <option timestep="0.004" gravity="0 0 -9.81" iterations="120" noslip_iterations="20" solver="Newton" cone="elliptic"/>

      <visual>
        <global offwidth="960" offheight="720"/>
      </visual>

      <default>
        <joint damping="2.0" armature="0.035" limited="true"/>
        <geom contype="1" conaffinity="1" density="500" friction="1.4 0.05 0.002" rgba="0.95 0.32 0.16 1"/>
        <position ctrllimited="true" forcelimited="true" forcerange="-300 300"/>
      </default>

      <asset>
        <texture name="grid" type="2d" builtin="checker" rgb1="0.50 0.23 0.16" rgb2="0.72 0.34 0.22" width="256" height="256"/>
        <material name="floor_mat" texture="grid" texrepeat="7 7" reflectance="0.04"/>
        <material name="fire_body" rgba="0.95 0.30 0.13 1"/>
        <material name="fire_head" rgba="1.0 0.55 0.23 1"/>
        <material name="face_cream" rgba="0.96 0.90 0.82 1"/>
        <material name="eye_dark" rgba="0.08 0.07 0.06 1"/>
        <material name="cheek" rgba="1.0 0.68 0.58 1"/>
        <material name="flame" rgba="1.0 0.72 0.10 1"/>
        <material name="flame_tip" rgba="1.0 0.95 0.20 1"/>
        <material name="joint_marker" rgba="0.1 0.9 0.35 1"/>
        <material name="hand_pad" rgba="1.0 0.56 0.25 1"/>
        <material name="berry" rgba="0.72 0.05 0.16 1"/>
        <material name="table" rgba="0.38 0.24 0.14 1"/>
      </asset>

      <worldbody>
        <light name="key" pos="1 -4 5" dir="-0.2 0.7 -1" diffuse="0.95 0.86 0.76"/>
        <light name="fill" pos="-4 2 4" diffuse="0.35 0.45 0.55"/>
        <geom name="floor" type="plane" size="5 5 0.05" material="floor_mat"/>
        <camera name="world_cam" pos="2.1 -3.2 1.45" xyaxes="1 0 0 0 0.42 0.91" fovy="45"/>
        <camera name="body_cam" pos="1.45 -2.0 1.02" xyaxes="1 0 0 0 0.42 0.91" fovy="42"/>
        <camera name="front_cam" pos="1.45 -0.72 0.78" xyaxes="0.42 0.91 0 -0.22 0.10 0.97" fovy="46"/>

        <geom name="berry_table" type="box" pos="0.40 -0.10 0.215" size="0.105 0.080 0.025" material="table"/>
        <body name="berry" pos="0.40 -0.10 0.295">
          <freejoint name="berry_free"/>
          <geom name="berry_geom" type="sphere" size="0.055" mass="0.018" material="berry" friction="8.0 0.35 0.03" condim="6"/>
        </body>

        <body name="fireboy_root" pos="0 0 0">
          <joint name="root_x" type="slide" axis="1 0 0" range="-2.4 2.4"/>
          <joint name="root_y" type="slide" axis="0 1 0" range="-2.0 2.0"/>
          <joint name="root_z" type="slide" axis="0 0 1" range="0.00 0.20"/>
          <joint name="root_yaw" type="hinge" axis="0 0 1" range="-180 180"/>
          <site name="root_site" pos="{point_vec("pelvis")}" size="0.018" material="joint_marker"/>

          <geom name="pelvis" type="capsule" fromto="{point_vec("pelvis")} {point_vec("spine")}" size="0.145" mass="0.73" material="fire_body"/>
          <geom name="hip_glow" type="sphere" pos="{point_vec("pelvis")}" size="0.170" mass="0.60" material="fire_body"/>

          <body name="spine" pos="{point_vec("spine")}">
            <joint name="spine_pitch" type="hinge" axis="0 1 0" range="-25 25"/>
            <geom name="spine_geom" type="capsule" fromto="0 0 0 {rel_vec("chest", "spine")}" size="0.135" mass="0.55" material="fire_body"/>
            <site name="spine_site" pos="0 0 0" size="0.014" material="joint_marker"/>

            <body name="chest" pos="{rel_vec("chest", "spine")}">
              <joint name="chest_yaw" type="hinge" axis="0 0 1" range="-35 35"/>
              <geom name="chest_geom" type="sphere" pos="0.000 0.000 0.040" size="0.215" mass="1.15" material="fire_body"/>
              <geom name="shirt_panel" type="ellipsoid" pos="0.185 0 0.010" size="0.026 0.108 0.092" material="face_cream" density="0" contype="0" conaffinity="0"/>

              <body name="neck" pos="{rel_vec("neck", "chest")}">
                <joint name="neck_yaw" type="hinge" axis="0 0 1" range="-45 45"/>
                <geom name="neck_geom" type="capsule" fromto="0 0 0 {rel_vec("head", "neck")}" size="0.050" mass="0.08" material="fire_body"/>

                <body name="head" pos="{rel_vec("head", "neck")}">
                  <joint name="head_pitch" type="hinge" axis="0 1 0" range="-35 35"/>
                  <geom name="head_geom" type="sphere" pos="0.020 0 0.100" size="0.260" mass="2.05" material="fire_body"/>
                  <geom name="face_panel" type="ellipsoid" pos="0.285 0 0.065" size="0.024 0.155 0.105" material="face_cream" density="0" contype="0" conaffinity="0"/>
                  <geom name="eye_R" type="sphere" pos="0.306 -0.064 0.095" size="0.025" material="eye_dark" density="0" contype="0" conaffinity="0"/>
                  <geom name="eye_L" type="sphere" pos="0.306 0.064 0.095" size="0.025" material="eye_dark" density="0" contype="0" conaffinity="0"/>
                  <geom name="cheek_R" type="sphere" pos="0.307 -0.118 0.012" size="0.028" material="cheek" density="0" contype="0" conaffinity="0"/>
                  <geom name="cheek_L" type="sphere" pos="0.307 0.118 0.012" size="0.028" material="cheek" density="0" contype="0" conaffinity="0"/>
                  <geom name="tiny_nose" type="sphere" pos="0.320 0 0.032" size="0.014" material="eye_dark" density="0" contype="0" conaffinity="0"/>
                  <geom name="smile" type="capsule" fromto="0.326 -0.050 -0.026 0.326 0.050 -0.026" size="0.007" material="eye_dark" density="0" contype="0" conaffinity="0"/>
                  <site name="mouth_site" pos="0.320 0 -0.020" size="0.004" material="eye_dark"/>
                  <geom name="flame_core" type="ellipsoid" pos="0.020 0 0.350" size="0.105 0.100 0.250" mass="0.25" material="flame" contype="0" conaffinity="0"/>
                  <geom name="flame_highlight" type="ellipsoid" pos="0.040 0 0.410" size="0.060 0.055 0.180" density="0" material="flame_tip" contype="0" conaffinity="0"/>
                  <geom name="flame_tip" type="sphere" pos="{rel_vec("crown", "head")}" size="0.032" mass="0.05" material="flame_tip" contype="0" conaffinity="0"/>
                  <camera name="head_cam" pos="0.15 0 0.03" xyaxes="0 -1 0 0.25 0 0.97" fovy="58"/>
                </body>
              </body>

              <body name="upper_arm_R" pos="{rel_vec("shoulder_R", "chest")}">
                <joint name="shoulder_R_yaw" type="hinge" axis="0 0 1" range="-105 105"/>
                <joint name="shoulder_R_pitch" type="hinge" axis="0 1 0" range="-130 110"/>
                <joint name="shoulder_R_roll" type="hinge" axis="1 0 0" range="-95 95"/>
                <site name="shoulder_R_site" pos="0 0 0" size="0.018" material="joint_marker"/>
                <geom name="upper_arm_R_geom" type="capsule" fromto="0 0 0 {rel_vec("elbow_R", "shoulder_R")}" size="0.056" mass="0.16" material="fire_body"/>

                <body name="lower_arm_R" pos="{rel_vec("elbow_R", "shoulder_R")}">
                  <joint name="elbow_R" type="hinge" axis="0 1 0" range="-10 145"/>
                  <site name="elbow_R_site" pos="0 0 0" size="0.016" material="joint_marker"/>
                  <geom name="lower_arm_R_geom" type="capsule" fromto="0 0 0 {rel_vec("wrist_R", "elbow_R")}" size="0.049" mass="0.12" material="fire_body"/>

                  <body name="hand_R" pos="{rel_vec("wrist_R", "elbow_R")}">
                    <joint name="wrist_R_pitch" type="hinge" axis="0 1 0" range="-75 75"/>
                    <joint name="wrist_R_roll" type="hinge" axis="1 0 0" range="-75 75"/>
                    <site name="right_hand_site" pos="{rel_vec("hand_R", "wrist_R")}" size="0.016" material="joint_marker"/>
                    <geom name="palm_R" type="sphere" pos="{rel_vec("hand_R", "wrist_R")}" size="0.052" mass="0.08" material="fire_head" friction="6.0 0.25 0.02" condim="6"/>
                    <body name="finger_R_a_body" pos="{rel_vec("hand_R", "wrist_R")}">
                      <joint name="finger_R_a" type="slide" axis="0 1 0" range="0.010 0.060"/>
                      <geom name="finger_R_a_pad" type="box" pos="0.015 0 0" size="0.030 0.014 0.040" mass="0.02" material="hand_pad" friction="14.0 0.5 0.04" condim="6"/>
                    </body>
                    <body name="finger_R_b_body" pos="{rel_vec("hand_R", "wrist_R")}">
                      <joint name="finger_R_b" type="slide" axis="0 -1 0" range="0.010 0.060"/>
                      <geom name="finger_R_b_pad" type="box" pos="0.015 0 0" size="0.030 0.014 0.040" mass="0.02" material="hand_pad" friction="14.0 0.5 0.04" condim="6"/>
                    </body>
                  </body>
                </body>
              </body>

              <body name="upper_arm_L" pos="{rel_vec("shoulder_L", "chest")}">
                <joint name="shoulder_L_yaw" type="hinge" axis="0 0 1" range="-105 105"/>
                <joint name="shoulder_L_pitch" type="hinge" axis="0 1 0" range="-130 110"/>
                <joint name="shoulder_L_roll" type="hinge" axis="1 0 0" range="-95 95"/>
                <site name="shoulder_L_site" pos="0 0 0" size="0.018" material="joint_marker"/>
                <geom name="upper_arm_L_geom" type="capsule" fromto="0 0 0 {rel_vec("elbow_L", "shoulder_L")}" size="0.056" mass="0.16" material="fire_body"/>

                <body name="lower_arm_L" pos="{rel_vec("elbow_L", "shoulder_L")}">
                  <joint name="elbow_L" type="hinge" axis="0 1 0" range="-10 145"/>
                  <site name="elbow_L_site" pos="0 0 0" size="0.016" material="joint_marker"/>
                  <geom name="lower_arm_L_geom" type="capsule" fromto="0 0 0 {rel_vec("wrist_L", "elbow_L")}" size="0.049" mass="0.12" material="fire_body"/>

                  <body name="hand_L" pos="{rel_vec("wrist_L", "elbow_L")}">
                    <joint name="wrist_L_pitch" type="hinge" axis="0 1 0" range="-75 75"/>
                    <joint name="wrist_L_roll" type="hinge" axis="1 0 0" range="-75 75"/>
                    <site name="left_hand_site" pos="{rel_vec("hand_L", "wrist_L")}" size="0.016" material="joint_marker"/>
                    <geom name="palm_L" type="sphere" pos="{rel_vec("hand_L", "wrist_L")}" size="0.052" mass="0.08" material="fire_head" friction="6.0 0.25 0.02" condim="6"/>
                    <body name="finger_L_a_body" pos="{rel_vec("hand_L", "wrist_L")}">
                      <joint name="finger_L_a" type="slide" axis="0 1 0" range="0.010 0.060"/>
                      <geom name="finger_L_a_pad" type="box" pos="0.015 0 0" size="0.030 0.014 0.040" mass="0.02" material="hand_pad" friction="14.0 0.5 0.04" condim="6"/>
                    </body>
                    <body name="finger_L_b_body" pos="{rel_vec("hand_L", "wrist_L")}">
                      <joint name="finger_L_b" type="slide" axis="0 -1 0" range="0.010 0.060"/>
                      <geom name="finger_L_b_pad" type="box" pos="0.015 0 0" size="0.030 0.014 0.040" mass="0.02" material="hand_pad" friction="14.0 0.5 0.04" condim="6"/>
                    </body>
                  </body>
                </body>
              </body>
            </body>
          </body>

          <body name="upper_leg_R" pos="{point_vec("hip_R")}">
            <joint name="hip_R_yaw" type="hinge" axis="0 0 1" range="-35 35"/>
            <joint name="hip_R_pitch" type="hinge" axis="0 1 0" range="-70 70"/>
            <geom name="upper_leg_R_geom" type="capsule" fromto="0 0 0 {rel_vec("knee_R", "hip_R")}" size="0.060" mass="0.25" material="fire_body"/>
            <body name="lower_leg_R" pos="{rel_vec("knee_R", "hip_R")}">
              <joint name="knee_R" type="hinge" axis="0 1 0" range="-5 115"/>
              <geom name="lower_leg_R_geom" type="capsule" fromto="0 0 0 {rel_vec("ankle_R", "knee_R")}" size="0.055" mass="0.22" material="fire_body"/>
              <body name="foot_R" pos="{rel_vec("ankle_R", "knee_R")}">
                <joint name="ankle_R" type="hinge" axis="0 1 0" range="-35 35"/>
                <geom name="foot_R_geom" type="ellipsoid" pos="{rel_vec("foot_R", "ankle_R")}" size="0.090 0.060 0.035" mass="0.14" material="fire_head" friction="2.0 0.08 0.01"/>
              </body>
            </body>
          </body>

          <body name="upper_leg_L" pos="{point_vec("hip_L")}">
            <joint name="hip_L_yaw" type="hinge" axis="0 0 1" range="-35 35"/>
            <joint name="hip_L_pitch" type="hinge" axis="0 1 0" range="-70 70"/>
            <geom name="upper_leg_L_geom" type="capsule" fromto="0 0 0 {rel_vec("knee_L", "hip_L")}" size="0.060" mass="0.25" material="fire_body"/>
            <body name="lower_leg_L" pos="{rel_vec("knee_L", "hip_L")}">
              <joint name="knee_L" type="hinge" axis="0 1 0" range="-5 115"/>
              <geom name="lower_leg_L_geom" type="capsule" fromto="0 0 0 {rel_vec("ankle_L", "knee_L")}" size="0.055" mass="0.22" material="fire_body"/>
              <body name="foot_L" pos="{rel_vec("ankle_L", "knee_L")}">
                <joint name="ankle_L" type="hinge" axis="0 1 0" range="-35 35"/>
                <geom name="foot_L_geom" type="ellipsoid" pos="{rel_vec("foot_L", "ankle_L")}" size="0.090 0.060 0.035" mass="0.14" material="fire_head" friction="2.0 0.08 0.01"/>
              </body>
            </body>
          </body>
        </body>
      </worldbody>

      <actuator>
{actuator_xml}
      </actuator>

      <sensor>
        <framepos name="root_pos" objtype="site" objname="root_site"/>
        <framepos name="right_hand_pos" objtype="site" objname="right_hand_site"/>
        <framepos name="left_hand_pos" objtype="site" objname="left_hand_site"/>
        <framepos name="mouth_pos" objtype="site" objname="mouth_site"/>
        <framepos name="berry_pos" objtype="body" objname="berry"/>
      </sensor>
    </mujoco>
    """
    return dedent(xml).strip() + "\n"


def kp_for_joint(joint: str) -> float:
    if joint in {"root_x", "root_y"}:
        return 3200.0
    if joint == "root_z":
        return 5200.0
    if joint == "root_yaw":
        return 700.0
    if joint.startswith("finger_"):
        return 1500.0
    if "shoulder" in joint or "hip" in joint:
        return 950.0
    if "knee" in joint or "elbow" in joint:
        return 800.0
    if "wrist" in joint:
        return 550.0
    return 420.0


def ctrlrange_for_joint(joint: str) -> str:
    ranges: dict[str, str] = {
        "root_x": "-2.4 2.4",
        "root_y": "-2.0 2.0",
        "root_z": "0.00 0.20",
        "root_yaw": "-180 180",
        "spine_pitch": "-25 25",
        "chest_yaw": "-35 35",
        "neck_yaw": "-45 45",
        "head_pitch": "-35 35",
        "shoulder_R_yaw": "-105 105",
        "shoulder_R_pitch": "-130 110",
        "shoulder_R_roll": "-95 95",
        "elbow_R": "-10 145",
        "wrist_R_pitch": "-75 75",
        "wrist_R_roll": "-75 75",
        "finger_R_a": "0.010 0.060",
        "finger_R_b": "0.010 0.060",
        "shoulder_L_yaw": "-105 105",
        "shoulder_L_pitch": "-130 110",
        "shoulder_L_roll": "-95 95",
        "elbow_L": "-10 145",
        "wrist_L_pitch": "-75 75",
        "wrist_L_roll": "-75 75",
        "finger_L_a": "0.010 0.060",
        "finger_L_b": "0.010 0.060",
        "hip_R_yaw": "-35 35",
        "hip_R_pitch": "-70 70",
        "knee_R": "-5 115",
        "ankle_R": "-35 35",
        "hip_L_yaw": "-35 35",
        "hip_L_pitch": "-70 70",
        "knee_L": "-5 115",
        "ankle_L": "-35 35",
    }
    return ranges[joint]


def write_default_mjcf(path: Path = DEFAULT_XML_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    xml = build_fireboy_articulated_mjcf()
    ElementTree.fromstring(xml)
    path.write_text(xml, encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write_default_mjcf())
