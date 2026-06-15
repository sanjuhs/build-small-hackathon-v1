from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


class EpisodeWriter:
    def __init__(
        self,
        root: Path,
        task: str = "fireboy_pick_ball",
        save_images: bool = True,
        language_templates: list[str] | None = None,
        state_keys: list[str] | None = None,
        image_stride: int = 1,
    ):
        self.root = Path(root)
        self.task = task
        self.save_images = save_images
        self.image_stride = max(1, int(image_stride))
        self.language_templates = language_templates or ["pick up the ball", "grab the yellow ball", "lift the ball"]
        self.state_keys = state_keys or ["qpos", "qvel", "ctrl", "previous_action"]
        self.episodes_dir = self.root / "episodes"
        self.images_dir = self.root / "images"
        self.episodes_dir.mkdir(parents=True, exist_ok=True)
        if self.save_images:
            self.images_dir.mkdir(parents=True, exist_ok=True)
        self._write_meta()

    def write_episode(self, episode_id: int, rows: list[dict[str, Any]]) -> Path:
        eid = f"{episode_id:06d}"
        image_dir = self.images_dir / eid
        if self.save_images:
            image_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = self.episodes_dir / f"{eid}.jsonl"
        with jsonl_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                image = row.pop("image", None)
                if self.save_images and image is not None and int(row["step"]) % self.image_stride == 0:
                    image_path = image_dir / f"{int(row['step']):06d}.jpg"
                    Image.fromarray(np.asarray(image, dtype=np.uint8)).save(image_path, quality=88)
                    row["image_path"] = str(image_path.relative_to(self.root))
                else:
                    row["image_path"] = None
                handle.write(json.dumps(to_jsonable(row), ensure_ascii=True) + "\n")
        return jsonl_path

    def _write_meta(self) -> None:
        meta = {
            "task": self.task,
            "simulator": "mujoco",
            "action_type": "normalized_joint_targets",
            "camera_keys": ["agent_rgb"],
            "state_keys": self.state_keys,
            "language_templates": self.language_templates,
            "image_stride": self.image_stride if self.save_images else None,
        }
        (self.root / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=True), encoding="utf-8")


def to_jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    return value
