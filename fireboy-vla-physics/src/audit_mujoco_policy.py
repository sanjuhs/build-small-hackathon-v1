from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw

from eval_policy import state_from_obs
from fireboy_mjcf import ACTUATED_JOINTS, write_default_mjcf
from ik_expert import PickBallIkExpert
from pick_ball_env import PickBallConfig, PickBallEnv
from rollout_numpy_policy import DEFAULT_POLICY_PATH, policy_action


DEFAULT_OUT_DIR = Path("fireboy-vla-physics/build/audit")
MODES = ("expert", "learned_raw", "learned_smooth")


def run_audit(
    out_dir: Path = DEFAULT_OUT_DIR,
    policy_path: Path = DEFAULT_POLICY_PATH,
    seed: int = 5000,
    smooth_alpha: float = 0.25,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_default_mjcf()
    rollouts = []
    for mode in MODES:
        rollouts.append(run_rollout(mode, out_dir, policy_path, seed, smooth_alpha))

    distance_plot = out_dir / "policy_distance_plot.png"
    action_plot = out_dir / "policy_action_plot.png"
    draw_distance_plot(rollouts, distance_plot)
    draw_action_plot(rollouts, action_plot)

    report = {
        "truth": "This audit shows the actual MuJoCo harness and policies. The current body is not a full humanoid skeleton.",
        "body": {
            "type": "bimanual manipulation harness",
            "visual": "static Fire Boy costume geoms",
            "actuated_joints": list(ACTUATED_JOINTS),
            "action_dim": len(ACTUATED_JOINTS),
        },
        "policy_diagnosis": diagnose(rollouts),
        "rollouts": rollouts,
        "plots": {
            "distance_path": str(distance_plot),
            "action_path": str(action_plot),
        },
    }
    report_path = out_dir / "policy_audit_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def run_rollout(mode: str, out_dir: Path, policy_path: Path, seed: int, smooth_alpha: float) -> dict[str, Any]:
    env = PickBallEnv(PickBallConfig(camera="world_cam", task="eat_berry", render=True, width=480, height=368, max_steps=240))
    expert = PickBallIkExpert(env) if mode == "expert" else None
    policy = None
    input_dim = 0
    if mode.startswith("learned"):
        raw = np.load(policy_path)
        policy = {key: raw[key] for key in raw.files}
        input_dim = int(policy["input_dim"])
    obs = env.reset(seed=seed)
    previous_action = np.asarray(obs["previous_action"], dtype=np.float32)
    frames = []
    records = []
    success = False
    try:
        for step in range(env.config.max_steps):
            if mode == "expert":
                action = expert.act(obs)  # type: ignore[union-attr]
                applied_action = action
            else:
                state = state_from_obs(obs, input_dim)
                action = policy_action(policy, state)  # type: ignore[arg-type]
                if mode == "learned_smooth":
                    applied_action = smooth_alpha * previous_action + (1.0 - smooth_alpha) * action
                else:
                    applied_action = action
                applied_action = np.clip(applied_action, -1.0, 1.0)

            next_obs, reward, done, truncated, info = env.step(applied_action)
            previous_action = np.asarray(applied_action, dtype=np.float32)
            mouth_dist = float(np.linalg.norm(next_obs["ball_pos"] - next_obs["mouth_pos"]))
            records.append(
                {
                    "step": step,
                    "reward": float(reward),
                    "mouth_dist": mouth_dist,
                    "ball_pos": to_float_list(next_obs["ball_pos"]),
                    "mouth_pos": to_float_list(next_obs["mouth_pos"]),
                    "right_hand_pos": to_float_list(next_obs["right_hand_pos"]),
                    "left_hand_pos": to_float_list(next_obs["left_hand_pos"]),
                    "action": to_float_list(applied_action),
                    "raw_action": to_float_list(action),
                    "grasped": bool(info.get("grasped")),
                    "eaten": bool(info.get("eaten")),
                    "success": bool(info.get("success")),
                }
            )
            if len(frames) < 180:
                frames.append(annotate_frame(next_obs["image"], mode, step, mouth_dist, info))
            success = bool(info.get("success"))
            obs = next_obs
            if done or truncated:
                for _ in range(10):
                    frames.append(annotate_frame(next_obs["image"], mode, step, mouth_dist, info))
                break
    finally:
        env.close()

    stem = out_dir / f"policy_audit_{mode}"
    gif_path, mp4_path = save_media(frames, stem)
    trace_path = stem.with_suffix(".json")
    trace_path.write_text(json.dumps({"mode": mode, "records": records}, indent=2), encoding="utf-8")
    distances = [row["mouth_dist"] for row in records]
    actions = np.asarray([row["action"] for row in records], dtype=np.float32) if records else np.zeros((0, 6), dtype=np.float32)
    action_jump = np.linalg.norm(np.diff(actions, axis=0), axis=1) if len(actions) > 1 else np.zeros(0, dtype=np.float32)
    eaten_steps = [row["step"] for row in records if row["eaten"]]
    return {
        "mode": mode,
        "success": success,
        "grasped": bool(records[-1]["grasped"]) if records else False,
        "eaten": bool(records[-1]["eaten"]) if records else False,
        "eaten_step": int(eaten_steps[0]) if eaten_steps else None,
        "frames": len(frames),
        "steps": len(records),
        "min_mouth_dist": round(float(min(distances)), 4) if distances else None,
        "final_mouth_dist": round(float(distances[-1]), 4) if distances else None,
        "mean_action_jump": round(float(action_jump.mean()), 4) if len(action_jump) else 0.0,
        "max_action_jump": round(float(action_jump.max()), 4) if len(action_jump) else 0.0,
        "gif_path": str(gif_path),
        "mp4_path": str(mp4_path),
        "trace_path": str(trace_path),
        "records": compact_records(records),
    }


def diagnose(rollouts: list[dict[str, Any]]) -> list[str]:
    by_mode = {rollout["mode"]: rollout for rollout in rollouts}
    notes = [
        "Expert rollout is the demonstration generator used to create training data.",
        "learned_raw is the behavior-cloned checkpoint without the low-pass controller.",
        "learned_smooth is the deployable controller wrapper used by the local demo.",
    ]
    raw = by_mode.get("learned_raw", {})
    smooth = by_mode.get("learned_smooth", {})
    if raw and smooth and not raw.get("success") and smooth.get("success"):
        notes.append("Main bug: raw BC drifts/jitters; action smoothing stabilizes the same checkpoint.")
    if raw and raw.get("max_action_jump", 0) > smooth.get("max_action_jump", 999):
        notes.append("Raw policy has larger action jumps than the stabilized controller.")
    notes.append("Better fix than smoothing: collect recovery rollouts / DAgger data and train a policy that sees its own off-expert states.")
    notes.append("For a true VLA: replace state input with camera+language features, keep this action space first, then move to a full humanoid body.")
    return notes


def compact_records(records: list[dict[str, Any]], limit: int = 60) -> list[dict[str, Any]]:
    if len(records) <= limit:
        return records
    indices = np.linspace(0, len(records) - 1, limit).round().astype(int)
    return [records[int(index)] for index in indices]


def annotate_frame(frame: np.ndarray, mode: str, step: int, mouth_dist: float, info: dict[str, Any]) -> np.ndarray:
    image = Image.fromarray(np.asarray(frame, dtype=np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(image)
    title = mode.replace("_", " ").upper()
    status = f"step {step:03d} | mouth dist {mouth_dist:.3f} | grasped {bool(info.get('grasped'))} | eaten {bool(info.get('eaten'))}"
    draw.rectangle((0, 0, image.width, 38), fill=(12, 15, 16))
    draw.text((10, 8), f"{title}  {status}", fill=(242, 246, 244))
    return np.asarray(image, dtype=np.uint8)


def save_media(frames: list[np.ndarray], stem: Path) -> tuple[Path, Path]:
    gif_path = stem.with_suffix(".gif")
    mp4_path = stem.with_suffix(".mp4")
    imageio.mimsave(gif_path, frames, duration=0.05)
    imageio.mimsave(mp4_path, frames, fps=20)
    return gif_path, mp4_path


def draw_distance_plot(rollouts: list[dict[str, Any]], path: Path) -> None:
    series = []
    for rollout in rollouts:
        values = [row["mouth_dist"] for row in rollout["records"]]
        series.append((rollout["mode"], values))
    draw_line_plot(
        path,
        title="Berry-to-mouth distance over time",
        y_label="meters",
        series=series,
        colors={"expert": (35, 111, 106), "learned_raw": (190, 48, 71), "learned_smooth": (54, 88, 184)},
    )


def draw_action_plot(rollouts: list[dict[str, Any]], path: Path) -> None:
    series = []
    for rollout in rollouts:
        records = rollout["records"]
        if not records:
            values = []
        else:
            actions = np.asarray([row["action"] for row in records], dtype=np.float32)
            jumps = np.linalg.norm(np.diff(actions, axis=0), axis=1)
            values = [0.0] + jumps.tolist()
        series.append((rollout["mode"], values))
    draw_line_plot(
        path,
        title="Action jump per step",
        y_label="normalized action delta",
        series=series,
        colors={"expert": (35, 111, 106), "learned_raw": (190, 48, 71), "learned_smooth": (54, 88, 184)},
    )


def draw_line_plot(path: Path, title: str, y_label: str, series: list[tuple[str, list[float]]], colors: dict[str, tuple[int, int, int]]) -> None:
    width, height = 1100, 520
    pad_left, pad_right, pad_top, pad_bottom = 82, 34, 58, 78
    image = Image.new("RGB", (width, height), (250, 252, 251))
    draw = ImageDraw.Draw(image)
    plot = (pad_left, pad_top, width - pad_right, height - pad_bottom)
    all_values = [value for _, values in series for value in values if np.isfinite(value)]
    ymax = max(all_values) if all_values else 1.0
    ymax = max(0.05, ymax * 1.08)
    xmax = max((len(values) - 1 for _, values in series), default=1)
    xmax = max(1, xmax)

    draw.text((pad_left, 18), title, fill=(24, 32, 35))
    draw.text((pad_left, height - 36), "simulation step", fill=(88, 100, 104))
    draw.text((12, pad_top + 8), y_label, fill=(88, 100, 104))
    draw.rectangle(plot, outline=(207, 216, 214), width=1)
    for i in range(5):
        y = plot[3] - (plot[3] - plot[1]) * i / 4
        value = ymax * i / 4
        draw.line((plot[0], y, plot[2], y), fill=(228, 234, 232))
        draw.text((18, y - 7), f"{value:.2f}", fill=(88, 100, 104))

    legend_x = plot[0]
    legend_y = height - 58
    for name, values in series:
        color = colors.get(name, (40, 40, 40))
        draw.rectangle((legend_x, legend_y, legend_x + 14, legend_y + 14), fill=color)
        draw.text((legend_x + 20, legend_y - 1), name.replace("_", " "), fill=(24, 32, 35))
        legend_x += 165
        if len(values) < 2:
            continue
        points = []
        for i, value in enumerate(values):
            x = plot[0] + (plot[2] - plot[0]) * i / xmax
            y = plot[3] - (plot[3] - plot[1]) * float(value) / ymax
            points.append((x, y))
        draw.line(points, fill=color, width=3)

    image.save(path)


def to_float_list(value: Any) -> list[float]:
    return [float(item) for item in np.asarray(value, dtype=np.float32).reshape(-1)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--seed", type=int, default=5000)
    parser.add_argument("--smooth-alpha", type=float, default=0.25)
    args = parser.parse_args()
    print(json.dumps(run_audit(args.out_dir, args.policy, args.seed, args.smooth_alpha), indent=2))


if __name__ == "__main__":
    main()
