from __future__ import annotations

from pathlib import Path
from typing import Any

import modal


APP_NAME = "fireboy-vla-router"
VOLUME_NAME = "fireboy-vla-router-cache"
REMOTE_ROOT = Path("/root")
REMOTE_CHECKPOINT = (
    REMOTE_ROOT
    / "Fireboy-training-policy-vla"
    / "runpod-artifacts"
    / "checkpoints"
    / "fireboy_minicpm_vla_skill_param_head"
    / "minicpm_vla_skill_param_head.pt"
)

app = modal.App(APP_NAME)
cache_volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "libgl1", "libglib2.0-0")
    .pip_install(
        "numpy==2.3.5",
        "pillow==12.0.0",
        "torch==2.4.1",
        "torchvision==0.19.1",
        "transformers[torch]>=5.7.0",
        "accelerate>=1.12.0",
        "safetensors>=0.7.0",
        "huggingface_hub[hf_xet]>=1.2.1",
        "fastapi>=0.121.0",
    )
    .env(
        {
            "PYTHONPATH": str(REMOTE_ROOT / "fireboy-vla-physics" / "src"),
            "HF_HOME": "/cache/huggingface",
            "HF_XET_HIGH_PERFORMANCE": "1",
            "PYTHONUNBUFFERED": "1",
        }
    )
    .add_local_dir("fireboy-vla-physics/src", remote_path=str(REMOTE_ROOT / "fireboy-vla-physics" / "src"))
    .add_local_dir(
        "Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head",
        remote_path=str(REMOTE_CHECKPOINT.parent),
    )
)

_router: Any | None = None


def get_router() -> Any:
    global _router
    if _router is None:
        import sys

        sys.path.insert(0, str(REMOTE_ROOT / "fireboy-vla-physics" / "src"))
        from vla_router_runtime import FireboyVLARouter

        _router = FireboyVLARouter(REMOTE_CHECKPOINT)
    return _router


@app.function(
    image=image,
    gpu="L40S",
    volumes={"/cache": cache_volume},
    timeout=30 * 60,
    startup_timeout=30 * 60,
    scaledown_window=180,
    max_containers=1,
    memory=64 * 1024,
)
@modal.asgi_app(label="fireboy-vla-router")
def serve() -> Any:
    from fastapi import FastAPI

    api = FastAPI(title="Fire Boy MiniCPM-V VLA Router")

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "app": APP_NAME,
            "checkpoint": str(REMOTE_CHECKPOINT),
            "checkpoint_exists": REMOTE_CHECKPOINT.exists(),
            "model_loaded": _router is not None,
        }

    @api.post("/route")
    def route(payload: dict[str, Any]) -> dict[str, Any]:
        router = get_router()
        result = router.route(payload)
        result["served_by"] = "modal"
        result["promoted_router"] = True
        return result

    return api


@app.function(
    image=image,
    gpu="L40S",
    volumes={"/cache": cache_volume},
    timeout=30 * 60,
    startup_timeout=30 * 60,
    memory=64 * 1024,
)
def smoke_route(command: str = "go find berry and eat it") -> dict[str, Any]:
    router = get_router()
    return router.route(
        {
            "command": command,
            "scene": {
                "objects": [
                    {"id": "berry-rose", "kind": "berry", "affordances": ["eat", "pick_up"], "x": 0.42, "y": -0.1, "z": 0.08},
                    {"id": "yellow-marker", "kind": "marker", "affordances": ["go_to"], "x": 0.44, "y": 0.02, "z": 0.0},
                ]
            },
        }
    )


@app.local_entrypoint()
def main(action: str = "smoke", command: str = "go find berry and eat it") -> None:
    if action == "smoke":
        print(smoke_route.remote(command))
    elif action == "url":
        print("Deploy with: modal deploy fireboy-vla-physics/modal_vla_router.py")
    else:
        raise ValueError(f"Unknown action: {action}")
