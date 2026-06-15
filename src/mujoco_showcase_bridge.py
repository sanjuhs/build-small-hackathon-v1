from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIREBOY_VLA_ROOT = ROOT / "fireboy-vla-physics"
SHOWCASE_DIR = FIREBOY_VLA_ROOT / "build" / "showcase"


def run_mujoco_showcase(mode: str = "learned") -> dict[str, Any]:
    if mode not in {"rest", "expert", "learned"}:
        raise ValueError(f"unknown showcase mode: {mode}")
    SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)
    python_bin = _python_bin()
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{FIREBOY_VLA_ROOT / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    env.setdefault("MUJOCO_GL", "glfw")
    cmd = [
        str(python_bin),
        str(FIREBOY_VLA_ROOT / "src" / "render_mujoco_showcase.py"),
        "--mode",
        mode,
        "--out-dir",
        str(SHOWCASE_DIR),
    ]
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=float(os.getenv("TOYBOX_MUJOCO_TIMEOUT", "60")),
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "unknown MuJoCo showcase error")[-1000:])
    result = json.loads(proc.stdout)
    for key in ("gif_path", "mp4_path"):
        if result.get(key):
            result[key.replace("_path", "_url")] = _static_url_for(Path(result[key]))
    return result


def _python_bin() -> Path:
    configured = os.getenv("TOYBOX_MUJOCO_PYTHON")
    if configured:
        return Path(configured)
    venv_python = FIREBOY_VLA_ROOT / ".venv" / "bin" / "python"
    return venv_python if venv_python.exists() else Path(sys.executable)


def _static_url_for(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(FIREBOY_VLA_ROOT.resolve())
    except ValueError:
        return ""
    return "/fireboy-vla/" + rel.as_posix()
