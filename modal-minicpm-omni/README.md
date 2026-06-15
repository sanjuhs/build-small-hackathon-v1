# MiniCPM-o 4.5 On Modal

This folder contains the first Modal experiment for running the official MiniCPM-o 4.5 PyTorch demo on a Modal GPU.

The goal is a short-lived browser demo, not a production deployment. The setup uses:

- Modal GPU: `L40S` by default.
- Modal Secret: `huggingface-token`, containing `HF_TOKEN`.
- Modal Volume: `minicpm-omni-cache`, used for the Hugging Face model cache.
- Official demo source: `https://github.com/OpenBMB/MiniCPM-o-Demo`.
- Model: `openbmb/MiniCPM-o-4_5`.

Do not place Hugging Face tokens in this folder. Store them only in Modal Secrets.

## Current Run

The first working deployment is live at:

```text
https://YOUR-MODAL-WORKSPACE--minicpm-omni-demo.modal.run
```

Verified on 2026-06-13:

- `/health` returned HTTP `200`.
- The root page returned `MiniCPMO45 — Multimodal Inference Service`.
- The worker loaded `openbmb/MiniCPM-o-4_5` successfully on an `L40S`.
- Modal GPU probe reported `NVIDIA L40S`, PyTorch `2.8.0+cu128`, and about `44.39 GB` available GPU memory.
- The model cache volume contains about `18.67 GB` for the full PyTorch model.
- The upstream turn-based `english_call` preset is patched to `Helpful Chat` because the original voice-cloning preset caused one-token echo responses for normal text prompts.

The owner-specific live endpoint is intentionally not committed; keep it in
local `.env`, Modal dashboard notes, or Hugging Face Space variables.

Useful live commands:

```bash
modal app logs minicpm-omni-45 --since 5m
modal container list --json
modal container stop <container-id> --yes
```

Avoid `modal app stop minicpm-omni-45 --yes` unless you want to stop the deployed app itself. If you use it, run `modal deploy modal-minicpm-omni/modal_minicpm_omni.py` afterward to restore the web endpoint.

## Token, Volume, And Cold Starts

The Hugging Face token is not used by the local browser UI. It is only attached to Modal functions that need authenticated Hugging Face access.

In this setup:

- `download_weights` uses the token to download `openbmb/MiniCPM-o-4_5`.
- The downloaded files are stored in the Modal Volume `minicpm-omni-cache`.
- `serve_demo` mounts that Volume at `/models` and reads weights from disk.
- The model is loaded into GPU memory each time a fresh Modal container cold-starts.

So the token is not needed for every browser interaction, and the model is not re-downloaded every time the app wakes up. The persistent part is the Volume. The non-persistent part is the running container's RAM/GPU memory.

With `min_containers=0`, Modal can scale to zero. The next request then starts a new GPU container and reloads the model from the Volume. Keeping `min_containers=1` would reduce that cold start but would bill continuously.

## Local Frontend

The local chat UI lives in `local-frontend/`.

Run it from the repository root:

```bash
node modal-minicpm-omni/local-frontend/server.mjs --port 5174
```

Then open:

```text
http://localhost:5174
```

The local server proxies REST status calls to Modal and the browser connects directly to the official `/ws/chat` WebSocket for streaming chat. The local chat UI intentionally keeps streaming enabled because the Gateway currently rejects non-streaming text chat with a tensor-size error. It supports prompt text, uploads, mic recordings, camera snapshots, and camera clips as turn-based multimodal attachments. The `Speak` toggle uses browser-local speech playback; the official remote pages remain the best place to test full-duplex audio/video.

## Cost Behavior

The Modal functions are configured with:

```python
min_containers=0
scaledown_window=60
```

That means the GPU should scale down after the web session goes idle. While the demo is open and serving browser/WebSocket/WebRTC traffic, the L40S GPU is billed. When the session is closed and no requests remain, Modal should stop billing for that GPU shortly after the idle window.

## One-Time Setup

Create the Modal secret:

```bash
modal secret create huggingface-token HF_TOKEN="$HF_TOKEN"
```

Create the model cache volume:

```bash
modal volume create minicpm-omni-cache
```

Both were created for this experiment before the first run.

## Commands

From the repository root:

```bash
modal run modal-minicpm-omni/modal_minicpm_omni.py --action gpu
```

Download the model weights into the Modal Volume:

```bash
modal run modal-minicpm-omni/modal_minicpm_omni.py --action download
```

Inspect cached files:

```bash
modal run modal-minicpm-omni/modal_minicpm_omni.py --action cache
```

Deploy the browser demo:

```bash
modal deploy modal-minicpm-omni/modal_minicpm_omni.py
```

The deploy output prints a `modal.run` URL for the `serve_demo` web endpoint. Open that URL in the browser.

## What The Modal App Does

1. Builds a CUDA 12.8 / Python 3.10 image.
2. Clones `OpenBMB/MiniCPM-o-Demo` into `/app`.
3. Creates the demo's expected `.venv/base` virtual environment.
4. Installs PyTorch 2.8, torchaudio 2.8, and the demo requirements.
5. Pins `setuptools==80.9.0` because `librosa==0.9.0` imports `pkg_resources`.
6. Downloads `openbmb/MiniCPM-o-4_5` into `/models/openbmb/MiniCPM-o-4_5`.
7. Starts the official `worker.py` and `gateway.py` processes directly.
8. Exposes port `8006` through Modal as HTTPS.

## Notes

- First image build can be slow because PyTorch and demo dependencies are large.
- First model download can be slow because the full PyTorch weights are about 20 GB.
- The web demo uses a worker plus gateway process. The Modal wrapper streams both process logs to `modal app logs minicpm-omni-45`.
- If the PyTorch demo proves too heavy or startup is awkward, the fallback is a second Modal wrapper around the GGUF / llama.cpp-omni demo.
