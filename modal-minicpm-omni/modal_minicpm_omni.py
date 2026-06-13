from __future__ import annotations

import json
from pathlib import Path

import modal


APP_NAME = "minicpm-omni-45"
HF_SECRET_NAME = "huggingface-token"
VOLUME_NAME = "minicpm-omni-cache"
MODEL_REPO = "openbmb/MiniCPM-o-4_5"
MODEL_DIR = Path("/models") / MODEL_REPO
DEMO_DIR = Path("/app")
DEMO_PORT = 8006
WORKER_PORT = 22400
WORKER_STARTUP_TIMEOUT_SECONDS = 25 * 60
GATEWAY_STARTUP_TIMEOUT_SECONDS = 3 * 60

app = modal.App(APP_NAME)
model_volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
hf_secret = modal.Secret.from_name(HF_SECRET_NAME)


download_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("huggingface_hub[hf_xet]==0.36.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)


demo_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.8.1-devel-ubuntu22.04",
        add_python="3.10",
    )
    .apt_install(
        "build-essential",
        "curl",
        "ffmpeg",
        "git",
        "openssl",
        "python3-dev",
        "python3-venv",
    )
    .run_commands(
        "git clone --depth 1 https://github.com/OpenBMB/MiniCPM-o-Demo.git /app",
        "cd /app && python -m venv .venv/base",
        "cd /app && .venv/base/bin/python -m pip install --upgrade pip setuptools wheel",
        "cd /app && .venv/base/bin/pip install torch==2.8.0 torchaudio==2.8.0",
        "cd /app && .venv/base/bin/pip install -r requirements.txt",
        "cd /app && .venv/base/bin/pip install 'setuptools==80.9.0'",
        "cd /app && cp config.example.json config.json",
        "cd /app && mkdir -p tmp data torch_compile_cache",
    )
    .add_local_file(
        local_path="modal-minicpm-omni/patches/patch_turnbased_presets.py",
        remote_path="/tmp/patch_turnbased_presets.py",
        copy=True,
    )
    .run_commands("python /tmp/patch_turnbased_presets.py")
    .env(
        {
            "PYTHONPATH": "/app",
            "PYTHONUNBUFFERED": "1",
            "SKIP_MOBILE_BUILD": "1",
            "SKIP_DOCS_BUILD": "1",
            "TORCHINDUCTOR_CACHE_DIR": "/app/torch_compile_cache",
        }
    )
)


@app.function(
    image=download_image,
    secrets=[hf_secret],
    volumes={"/models": model_volume},
    timeout=7200,
    scaledown_window=60,
)
def download_weights(revision: str | None = None) -> dict[str, str | int]:
    from huggingface_hub import snapshot_download

    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
    local_dir = snapshot_download(
        repo_id=MODEL_REPO,
        revision=revision,
        local_dir=str(MODEL_DIR),
        local_dir_use_symlinks=False,
    )
    model_volume.commit()

    total_files = sum(1 for p in Path(local_dir).rglob("*") if p.is_file())
    return {
        "repo": MODEL_REPO,
        "local_dir": local_dir,
        "files": total_files,
    }


@app.function(
    image=download_image,
    volumes={"/models": model_volume},
    timeout=300,
    scaledown_window=60,
)
def cache_status(max_files: int = 40) -> dict[str, object]:
    root = MODEL_DIR
    files = []
    total_bytes = 0
    if root.exists():
        for path in sorted(root.rglob("*")):
            if path.is_file():
                size = path.stat().st_size
                total_bytes += size
                if len(files) < max_files:
                    files.append(
                        {
                            "path": str(path.relative_to(root)),
                            "size_mb": round(size / (1024 * 1024), 2),
                        }
                    )
    return {
        "model_dir": str(root),
        "exists": root.exists(),
        "shown_files": files,
        "total_size_gb": round(total_bytes / (1024**3), 2),
    }


@app.function(
    image=demo_image,
    gpu="L40S",
    timeout=600,
    scaledown_window=60,
    min_containers=0,
)
def gpu_probe() -> dict[str, object]:
    import subprocess

    probe = """
import json
import torch

if not torch.cuda.is_available():
    print(json.dumps({"cuda": False, "torch": torch.__version__}))
else:
    device = torch.cuda.current_device()
    props = torch.cuda.get_device_properties(device)
    print(json.dumps({
        "cuda": True,
        "torch": torch.__version__,
        "device_name": props.name,
        "total_memory_gb": round(props.total_memory / (1024 ** 3), 2),
    }))
"""
    output = subprocess.check_output(
        [str(DEMO_DIR / ".venv/base/bin/python"), "-c", probe],
        text=True,
    )
    return json.loads(output)


def _write_demo_config() -> None:
    config = {
        "model": {
            "model_path": str(MODEL_DIR),
            "pt_path": None,
            "attn_implementation": "auto",
        },
        "audio": {
            "ref_audio_path": "assets/ref_audio/ref_minicpm_signature.wav",
            "playback_delay_ms": 200,
            "chat_vocoder": "token2wav",
        },
        "service": {
            "gateway_port": DEMO_PORT,
            "worker_base_port": 22400,
            "max_queue_size": 1000,
            "request_timeout": 300.0,
            "compile": False,
            "data_dir": "data",
            "eta_chat_s": 15.0,
            "eta_streaming_s": 20.0,
            "eta_audio_duplex_s": 120.0,
            "eta_omni_duplex_s": 90.0,
            "eta_ema_alpha": 0.3,
            "eta_ema_min_samples": 3,
        },
        "duplex": {"pause_timeout": 60.0},
    }
    (DEMO_DIR / "config.json").write_text(json.dumps(config, indent=2))


@app.function(
    image=demo_image,
    gpu="L40S",
    secrets=[hf_secret],
    volumes={"/models": model_volume},
    timeout=6 * 60 * 60,
    startup_timeout=45 * 60,
    scaledown_window=60,
    min_containers=0,
    max_containers=1,
    memory=96 * 1024,
)
@modal.web_server(DEMO_PORT, startup_timeout=45 * 60, label="minicpm-omni-demo")
def serve_demo() -> None:
    import os
    import subprocess
    import threading
    import time
    import urllib.error
    import urllib.request

    if not MODEL_DIR.exists():
        raise RuntimeError(
            f"{MODEL_DIR} does not exist. Run: modal run "
            "modal-minicpm-omni/modal_minicpm_omni.py --action download"
        )

    os.chdir(DEMO_DIR)
    _write_demo_config()

    env = os.environ.copy()
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": "0",
            "PYTHONPATH": str(DEMO_DIR),
            "SKIP_MOBILE_BUILD": "1",
            "SKIP_DOCS_BUILD": "1",
        }
    )

    def stream_process(name: str, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            print(f"[{name}] {line}", end="", flush=True)

    def wait_for_health(
        name: str,
        url: str,
        process: subprocess.Popen[str],
        timeout_seconds: int,
        require_model_loaded: bool = False,
    ) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"{name} exited early with code {process.returncode}")
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not require_model_loaded or payload.get("model_loaded"):
                    print(f"[{name}] health ready: {payload}", flush=True)
                    return
                print(f"[{name}] health waiting: {payload}", flush=True)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"[{name}] health not ready: {exc}", flush=True)
            time.sleep(5)
        raise RuntimeError(f"{name} did not become healthy within {timeout_seconds}s")

    worker = subprocess.Popen(
        [
            str(DEMO_DIR / ".venv/base/bin/python"),
            "worker.py",
            "--port",
            str(WORKER_PORT),
            "--gpu-id",
            "0",
            "--worker-index",
            "0",
        ],
        cwd=str(DEMO_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    threading.Thread(target=stream_process, args=("worker", worker), daemon=True).start()

    wait_for_health(
        "worker",
        f"http://localhost:{WORKER_PORT}/health",
        worker,
        WORKER_STARTUP_TIMEOUT_SECONDS,
        require_model_loaded=True,
    )

    gateway = subprocess.Popen(
        [
            str(DEMO_DIR / ".venv/base/bin/python"),
            "gateway.py",
            "--port",
            str(DEMO_PORT),
            "--workers",
            f"localhost:{WORKER_PORT}",
            "--http",
        ],
        cwd=str(DEMO_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    threading.Thread(target=stream_process, args=("gateway", gateway), daemon=True).start()

    wait_for_health(
        "gateway",
        f"http://localhost:{DEMO_PORT}/health",
        gateway,
        GATEWAY_STARTUP_TIMEOUT_SECONDS,
    )


@app.local_entrypoint()
def main(action: str = "cache") -> None:
    if action == "download":
        print(download_weights.remote())
    elif action == "cache":
        print(json.dumps(cache_status.remote(), indent=2))
    elif action == "gpu":
        print(json.dumps(gpu_probe.remote(), indent=2))
    else:
        raise ValueError("action must be one of: download, cache, gpu")
