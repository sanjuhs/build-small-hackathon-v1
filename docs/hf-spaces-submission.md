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

Current measured fallback policy speed after the latest restart:

- Median `/api/pet-action` latency: about `322.5 ms`
- Mean `/api/pet-action` latency: about `330.5 ms`
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

For the Modal MiniCPM-o v3 demo:

```bash
TOYBOX_MODAL_OMNI_ACTION=1
TOYBOX_MODAL_OMNI_URL=https://sanjuhs123--minicpm-omni-demo.modal.run
TOYBOX_MODAL_OMNI_MODEL=openbmb/MiniCPM-o-4_5
TOYBOX_MODAL_OMNI_SEND_IMAGE=1
TOYBOX_MODAL_OMNI_CONNECT_TIMEOUT=45
TOYBOX_MODAL_OMNI_TIMEOUT=120
TOYBOX_TRACE_POLICY=0
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

It is the official MiniCPM-o 4.5 demo running on Modal. Modal logs confirm the worker loads `openbmb/MiniCPM-o-4_5`, places the LLM, vision, audio, and TTS components on `cuda:0`, and serves a healthy gateway after cold start.

This qualifies the project for Modal usage because Modal is used as the live multimodal MiniCPM runtime for Toy Room v3. `src/modal_omni_policy.py` adapts the Modal `/ws/chat` stream into validated PET action JSON, so typed/spoken commands directly drive Fire Boy's animation, speech, powers, and toy interactions.

Useful Modal commands:

```bash
modal app list
modal container list --json
modal app logs minicpm-omni-45 --since 15m
curl --max-time 45 https://sanjuhs123--minicpm-omni-demo.modal.run/health
modal deploy modal-minicpm-omni/modal_minicpm_omni.py
```

## Demo Video

Local output path:

```text
demo/fire-boy-v3-demo.mp4
```

Hosted file:

```text
https://huggingface.co/spaces/build-small-hackathon/toy-room-v3/resolve/main/demo/fire-boy-v3-demo.mp4
```

Recommended demo beats:

- Open `/toy-v3` and show the Fire Boy rig loaded.
- Command "Fire Boy, pick up the box."
- Command "Fire Boy, fireball the cube."
- Command "Fire Boy, run around the toy room."
- End with the runtime panel showing loop metrics and model-status truth.

## Submission Checklist

- Space builds successfully.
- `/toy-v3` opens directly.
- Fire Boy rig appears as the live body.
- Commands verified:
  - "pick up the box"
  - "fireball the cube"
  - "run around"
- Runtime panel shows honest model status.
- README has Build Small tags, MiniCPM/Modal/Codex evidence, architecture link, prize evidence link, and demo video path.
- Discord post includes Space URL, GitHub URL, demo MP4, demo commands, and model-status caveat.
