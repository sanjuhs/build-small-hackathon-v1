# Hugging Face Spaces And Submission Notes

## Local Verification

```bash
./start.sh
open http://127.0.0.1:65372/toy-v3
```

Expected local status today:

- `MiniCPM brain: trace policy`
- `Vision: camera frame`
- `Rigs: 1/1 meshes`
- `Loop`: updates after commands, such as `218ms / 8 ops`

Run the smoke tests:

```bash
uv run python -m unittest discover -s tests
uv run python scripts/measure_runtime.py --base-url http://127.0.0.1:65372 --samples 5
```

Current measured fallback policy speed:

- Median `/api/pet-action` latency: about `143 ms`
- Mean `/api/pet-action` latency: about `150 ms`
- Ollama running, but `ollama ps` reports no loaded model
- Token/sec: not available unless a live LLM endpoint is configured

## Space Creation

Recommended Space name:

```text
build-small-hackathon-toy-room-v3
```

The repository is Docker SDK compatible because `README.md` has Space metadata and `Dockerfile` exposes port `7860`.

Create the Space:

```bash
hf repo create build-small-hackathon/toy-room-v3 --type space --space-sdk docker --public
```

Upload from the repository root:

```bash
hf upload-large-folder \
  build-small-hackathon/toy-room-v3 \
  . \
  --repo-type space \
  --exclude ".git/*" \
  --exclude ".venv/*" \
  --exclude ".env" \
  --exclude ".env.*" \
  --exclude "**/.env" \
  --exclude "**/.env.*" \
  --exclude ".claude/*" \
  --exclude "**/__pycache__/**" \
  --exclude ".toybox.*" \
  --exclude "*.blend*" \
  --exclude "node_modules/*"
```

Then open:

```text
https://huggingface.co/spaces/build-small-hackathon/toy-room-v3
https://build-small-hackathon-toy-room-v3.hf.space/toy-v3
```

## Space Variables

For the reliable hackathon demo:

```bash
TOYBOX_TRACE_POLICY=1
TOYBOX_ALLOW_HEURISTIC_FALLBACK=1
```

For a hosted PET LLM:

```bash
TOYBOX_LLM_ENDPOINT=https://router.huggingface.co/v1/chat/completions
TOYBOX_LLM_MODEL=<provider-model-id>
TOYBOX_LLM_API_KEY=<secret>
```

For MiniCPM-V visual cortex:

```bash
TOYBOX_VISION_ENDPOINT=https://api.modelbest.cn/v1/chat/completions
TOYBOX_VISION_MODEL=MiniCPM-V-4.6-Instruct
TOYBOX_VISION_API_KEY=<secret>
```

Never commit these secrets. Put real values in Hugging Face Space secrets.

## Modal Notes

The current Modal deployment is:

```text
minicpm-omni-45
https://sanjuhs123--minicpm-omni-demo.modal.run
```

It is the official MiniCPM-o 4.5 demo, not the Toy Room action-brain endpoint. It can be shown as supporting work, but Toy Room v3 needs an adapter before it can use that Modal deployment as the live control brain.

Useful Modal commands:

```bash
modal app list
modal app logs minicpm-omni-45 --since 15m
modal deploy modal-minicpm-omni/modal_minicpm_omni.py
```

## Submission Checklist

- Space builds successfully.
- `/toy-v3` opens directly.
- Fire Boy rig appears as the live body.
- Commands verified:
  - "pick up the box"
  - "fireball the cube"
  - "run around"
- Runtime panel shows honest model status.
- README links to the architecture doc.
- Discord post includes Space URL, GitHub URL, demo commands, and model-status caveat.
