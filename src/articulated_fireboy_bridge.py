from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIREBOY_VLA_ROOT = ROOT / "fireboy-vla-physics"
ARTICULATED_DIR = FIREBOY_VLA_ROOT / "build" / "articulated"


def run_articulated_fireboy(mode: str = "all") -> dict[str, Any]:
    if mode not in {"body", "run", "pick", "eat", "all"}:
        raise ValueError(f"unknown articulated mode: {mode}")
    ARTICULATED_DIR.mkdir(parents=True, exist_ok=True)
    python_bin = _python_bin()
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{FIREBOY_VLA_ROOT / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    env.setdefault("MUJOCO_GL", "glfw")
    cmd = [
        str(python_bin),
        str(FIREBOY_VLA_ROOT / "src" / "render_articulated_fireboy.py"),
        "--mode",
        mode,
        "--out-dir",
        str(ARTICULATED_DIR),
    ]
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=float(os.getenv("TOYBOX_ARTICULATED_TIMEOUT", "90")),
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "unknown articulated Fireboy error")[-1400:])
    result = json.loads(proc.stdout)
    add_urls(result)
    return result


def add_urls(value: Any) -> None:
    if isinstance(value, dict):
        for key in list(value):
            item = value[key]
            if key.endswith("_path") and item:
                value[key.replace("_path", "_url")] = _static_url_for(Path(item))
            add_urls(item)
    elif isinstance(value, list):
        for item in value:
            add_urls(item)


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
