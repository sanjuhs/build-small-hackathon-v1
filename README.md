---
title: Toy Room V3
sdk: docker
app_port: 7860
pinned: false
short_description: Fire Boy MiniCPM virtual pet toy room.
---

# Tiny Toybox

A Gradio-hosted Three.js virtual pet room for the Build Small Hackathon.

**Toy Room v3** is the shipped hackathon cut: one controllable Fire Boy virtual pet using the unclothed generated rig as the live body. Fire Boy can be dragged, lifted, dropped, asked to act, asked what he sees, and prompted to create or interact with room objects. The room keeps the MiniCPM/OpenBMB-compatible brain hooks, MiniCPM-V vision hook, browser speech synthesis, WebAudio effects, trace logging, and readiness evidence from v2, but focuses the demo on one character.

Local ship route:

- `http://localhost:65372/toy-v3`
- `http://localhost:65372/toy` also opens v3

**Toy Room v2** is the hackathon build: a larger shared physics room with Squeaky, Fire Boy, Shark Girl, and Electraica active at the same time. The agents have draggable/drop-able balance bodies, toggleable generated GLB rig meshes, opt-in microphone hearing, generated WebAudio sound recipes, live room/agent vision panes, generated spell operations, waste/recycling interactions, persistent JSONL memories, and MiniCPM/OpenBMB-compatible model hooks.

Hosted Space:

- v3 target: `https://build-small-hackathon-toy-room-v3.hf.space/toy-v3`
- previous v2 build: `https://build-small-hackathon-toy-room-v2.hf.space/toy-v2`

Key docs:

- [Toy Room v3 architecture](docs/virtual-toy-v3-architecture.md)
- [Hugging Face Spaces and submission notes](docs/hf-spaces-submission.md)
- [Discord submission draft](docs/discord-submission-post.md)

## Toy Room v3

V3 adds:

- one Fire Boy virtual pet as the main controllable character
- the unclothed Fire Boy full-rig GLB rendered as the live body instead of a faint overlay
- brighter room and rig-viewer lighting for clearer mesh reads
- Fire Boy GLB animation clips connected to actions such as jump, throw, wave, sit, dance, and spin
- a babyish Fire Boy speech profile with higher-pitched browser voice settings
- a focused toy room with food, books, chairs, lamps, plants, balls, blocks, dominos, waste, a recycle bin, and a ramp
- commanded virtual-pet actions: ask Fire Boy to pick up/carry a box, fireball a cube, or run around the toy room
- a visible warm fireball projectile for Fire Boy's `fireball` power
- runtime loop metrics for command latency, server policy latency, approximate renderer state ops, approximate state-changing function calls, and token/sec when a model reports it
- a Fire Boy-specific judge demo for memory, vision, force input, generated objects, recycling, speech, and traces
- `/toy-v3` as the explicit v3 route, with `/toy` now pointing to the shipped v3 experience

Try these commands in `/toy-v3`:

```text
Fire Boy, pick up the box
Fire Boy, fireball the cube
Fire Boy, run around the toy room
```

Current local model status for this commit:

- The live demo runs in `trace_retrieval+heuristic` mode unless you configure `TOYBOX_LLM_ENDPOINT`.
- MiniCPM-V is wired through `TOYBOX_VISION_ENDPOINT` and `TOYBOX_VISION_MODEL`, but it is not active unless those variables are set.
- Modal currently hosts the separate `minicpm-omni-45` MiniCPM-o 4.5 demo. It needs a JSON action adapter before Toy Room v3 can use it as the live control brain.
- Measured local fallback `/api/pet-action` latency was about `143 ms` median across 5 samples. Token/sec is blank in fallback mode because no LLM tokens are generated.

## Toy Room v2

V2 adds:

- four simultaneous AI toy agents in one larger room
- active-agent power dock for one-click ability tests across Squeaky, Fire Boy, Shark Girl, and Electraica
- draggable objects and draggable agents with standing/balance physics
- active-agent force dock for lift, toss, spin, drop, and upright-settle ragdoll-style input
- force-aware rescue behavior: toss, spin, lift, or drop an agent and nearby agents visibly move in, speak, and comfort them
- toggleable generated GLB rig meshes loaded into the live room for all four agents
- waste objects, a recycle bin, food, books, chairs, lamps, plants, balls, blocks, dominos, and a ramp
- scored recycling challenge: drag recyclable waste into the bin or let Electraica sort it during the judge demo
- generic spell ops: impulse, freeze, scale, attract, particles, lights, and pet nudges
- vision-grounded decisions: "what do you see" prompts choose an action from the active agent's camera/detected-object payload
- council vision scan: the judge demo asks all four agents to inspect the room from their own agent-view cameras
- agent vision board: all four agents continuously expose their closest perceived objects and next local action affordance
- low-level motor loop: agents execute small local perception-driven moves between slower policy calls, making the AI loop feel embodied on video
- generated object recipes: prompts such as "wish for a tiny piano" can create new physical toys from simple parts
- browser speech-synthesis talkback with per-agent voice profiles plus procedural WebAudio effects
- generated sound recipes: the model can emit bounded oscillator tones for a new spell, object, or heard sound
- opt-in microphone hearing: agents receive structured sound-input summaries and can react to loud room audio
- visible learning loop: players can teach durable rules or terms, then the runtime stack shows when a remembered lesson is used
- trace-to-training export: `/api/training-dataset` summarizes valid action traces and `/api/training-dataset?format=jsonl&limit=200` emits a compact MiniCPM/PET action-policy SFT JSONL pack
- trace-retrieval fallback policy: when no live MiniCPM endpoint is configured, the backend first retrieves a similar validated action trace before falling back to hand-written heuristics
- trace-backed AI evidence: `/api/ai-evidence` summarizes distinct player inputs, generated spell ops, wishable objects, sound recipes, memories, vision-grounded actions, and policy-source counts
- partner play and reciprocal dialogue: fallback and model actions can name another agent for talk, play, share, comfort, or gather interactions, and the partner visibly answers back
- physical charades: agents receive detected stacks, lines, huddles, and wished toys from the physics scene and can guess what the player built
- one-button judge demo that teaches a rule, uses that remembered lesson, makes all four agents inspect what they see, drops an agent to trigger rescue behavior, generates an object, triggers partner play, solves a physical charade, and recycles waste through the live action loop
- live judge scorecard plus `/api/judge-status` readiness endpoint that reports hosting, assets, MiniCPM/trace-policy status, AI-load-bearing evidence, SFT traces, runtime demo proof, and remaining optional endpoint warnings
- in-room Brain Trace plus runtime stack chips for text, vision, sound, learning, trace training readiness, council scans, reciprocal dialogue, force, memory, action JSON, model status, and rig readiness
- persistent runtime memories at `data/memories/toy-room-v2.jsonl`
- action traces at `data/traces/pet-actions.jsonl`
- optional MiniCPM5 text-policy and MiniCPM-V 4.6 vision endpoints
- a Docker-backed Hugging Face Space that still serves a Gradio-mounted FastAPI app

## Run Locally

This project uses `uv` for Python dependency management. The local virtual environment is pinned to Python 3.12 via `.python-version`.

Current local setup was verified with:

- `uv 0.11.2`
- `Python 3.12.13`

```bash
./start.sh
```

`start.sh` stops previous Tiny Toybox `app.py` processes from this workspace, starts a fresh server, and prints the active URLs. Open `http://localhost:65372` for the page directory.

Useful local URLs:

- Page directory: `http://localhost:65372/pages`
- Toy Room v3: `http://localhost:65372/toy-v3`
- Toy Room v2: `http://localhost:65372/toy-v2`
- Toy room: `http://localhost:65372/toy`
- Procedural model lab: `http://localhost:65372/models`
- Blender rig previews and GLBs: `http://localhost:65372/blender-models`
- Layered part concept refs: `http://localhost:65372/parts-lab`
- Fire Boy rigged viewer: `http://localhost:65372/fireboy-rigged`

The default app port is `65372` to avoid common local preview conflicts. To choose another port for a one-off run:

```bash
PORT=65400 ./start.sh
```

To stop it:

```bash
./shutdown.sh
```

To restart everything from this project, run:

```bash
./start.sh
```

Manual uv flow:

```bash
uv sync --python 3.12
.venv/bin/python app.py
```

`start.sh` uses `uv sync` first, then runs the uv-created `.venv/bin/python` directly so `shutdown.sh` can stop the app cleanly by PID.

## Blender And SAM Character Assets

Blender is expected on PATH as `blender`. On this machine that is a wrapper in `~/.local/bin/blender` pointing at `/Applications/Blender.app/Contents/MacOS/Blender`.

Regenerate all character assets, rig previews, beauty renders, object lineups, GLBs, and the contact sheet with:

```bash
./scripts/render_blender_models.sh
```

Outputs are written to:

- `assets/generated/rigged/*.glb`
- `assets/generated/previews/*.png`

Clean raw fal/SAM GLB extractions from `potential-char-images/extracted-from-sam` with:

```bash
./scripts/clean_sam_models.sh
```

Cleaned SAM outputs are written to:

- `assets/generated/sam-cleaned/*.glb`
- `assets/generated/sam-standing-rigged/*.glb`
- `assets/generated/previews/*-sam-cleaned.png`
- `assets/generated/previews/*-sam-standing-*.png`

Layered 2D part concept outputs are written to:

- `assets/generated/part-concepts/*-parts-sheet.png`
- `assets/generated/part-concepts/individual/*/*.png` for the original sheet-derived v1 crops
- `assets/generated/part-concepts/individual-v2/*/*.png` for the cleaner individually generated v2 refs
- `assets/generated/part-concepts/*-individual-v2-contact.png`
- `assets/generated/part-concepts/parts-individual-v2-contact.png`
- `assets/generated/part-concepts/parts-manifest.json`

The v2 refs are the better input set for fal/SAM object extraction because each base body or prop is generated as one isolated image. The four base bodies are standing, while props stay separate for later Blender bone/socket attachment.

Generate fal SAM 3D Object GLBs from the four local source images with:

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 scripts/generate_sam_3d_models.py
```

That script sends images as data URLs, which avoids needing `fal files upload` permissions.

Generate fal SAM 3D Object GLBs from the v2 isolated base bodies, clothing, backpacks, and props with:

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 scripts/generate_sam_part_models.py
```

Part-level SAM outputs are written to:

- `assets/generated/part-models/raw/*/*-sam.glb`
- `assets/generated/part-models/raw/*/*-sam-result.json`
- `assets/generated/part-models/sam-part-inputs.json`

You can also run a focused pass, for example:

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 scripts/generate_sam_part_models.py --bases-only
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 scripts/generate_sam_part_models.py fire-boy-flute
```

Rig the four v2 standing base bodies and build socketed assembly test GLBs with:

```bash
./scripts/rig_part_base_models.sh
```

The rig/assembly pass writes:

- `assets/generated/part-models/rigged-bases/*-base-rigged.glb`
- `assets/generated/part-models/assemblies/*-assembled.glb`
- `assets/generated/part-models/mixamo-fbx/*-base-mesh.fbx` for Mixamo auto-rig upload tests
- `assets/generated/part-models/mixamo-fbx/*-base-rigged.fbx` for rigged FBX inspection
- `assets/generated/part-models/blend-scenes/*-assembly.blend`
- `assets/generated/previews/*-part-base-rigged.png`
- `assets/generated/previews/*-part-assembly.png`

## Optional Local Model Hook

The app can use a local OpenAI-compatible PET LLM endpoint. MiniCPM5 local mode is the recommended first text-policy brain:

```bash
scripts/start_with_minicpm5.sh
```

That script uses Ollama and `hf.co/openbmb/MiniCPM5-1B-GGUF:Q4_K_M`.

Manual PET LLM flow:

```bash
scripts/pull_minicpm5_ollama.sh
export TOYBOX_LLM_ENDPOINT=http://127.0.0.1:11434/v1/chat/completions
export TOYBOX_LLM_MODEL=hf.co/openbmb/MiniCPM5-1B-GGUF:Q4_K_M
./start.sh
```

Check the model endpoint:

```bash
uv run python scripts/check_pet_llm.py
```

## Optional Hosted Model Hook

The hosted Space can call any OpenAI-compatible chat-completions endpoint. For Hugging Face Inference Providers, set these Space variables/secrets:

```bash
hf spaces variables add build-small-hackathon/toy-room-v2 \
  -e TOYBOX_LLM_ENDPOINT=https://router.huggingface.co/v1/chat/completions \
  -e TOYBOX_LLM_MODEL=provider-backed/chat-model-id

hf spaces secrets add build-small-hackathon/toy-room-v2 \
  -s TOYBOX_LLM_API_KEY
```

Optional org billing header:

```bash
hf spaces variables add build-small-hackathon/toy-room-v2 \
  -e TOYBOX_LLM_BILL_TO=your-hf-org-or-username
```

`TOYBOX_LLM_API_KEY` may also be supplied as `HF_TOKEN` for Hugging Face endpoints, or `OPENAI_API_KEY` for OpenAI endpoints. The `/api/model-status` endpoint reports whether a hosted endpoint is active, configured but missing a secret, or falling back.

RunPod serverless endpoints are also supported when they expose an OpenAI-compatible chat-completions route:

```bash
hf spaces variables add build-small-hackathon/toy-room-v2 \
  -e TOYBOX_LLM_ENDPOINT=https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/openai/v1/chat/completions \
  -e TOYBOX_LLM_MODEL=openbmb/MiniCPM5-1B-or-your-served-model-id

hf spaces secrets add build-small-hackathon/toy-room-v2 \
  -s RUNPOD_API_KEY
```

For a RunPod MiniCPM-V visual cortex, set `TOYBOX_VISION_ENDPOINT` and `TOYBOX_VISION_MODEL` to the corresponding OpenAI-compatible vision endpoint/model. The same `RUNPOD_API_KEY` secret is reused unless `TOYBOX_VISION_API_KEY` is supplied. `/api/model-status` reports `provider: runpod` and `mode: runpod-openai-compatible` for these endpoints.

If no endpoint is configured, the public build uses a deterministic heuristic fallback so the game stays playable. If an endpoint is configured but unavailable, the pet enters visible asleep/model-off mode by default. Set `TOYBOX_ALLOW_HEURISTIC_FALLBACK=1` only for local debugging when you want heuristic behavior even after a model endpoint fails.

The current OpenBMB/MiniCPM path is local-first through Ollama because the public HF router metadata did not expose provider-backed OpenBMB MiniCPM chat models during this build. The game still uses the same action JSON contract, so a hosted MiniCPM endpoint can be connected by setting `TOYBOX_LLM_ENDPOINT`, `TOYBOX_LLM_MODEL`, and a secret token.

Check Modal remote execution:

```bash
uv run --with modal modal run scripts/modal_square_smoke.py
```

Measure the current local runtime:

```bash
uv run python scripts/measure_runtime.py --samples 5
```

On macOS, power sampling needs sudo. If you already have a cached sudo session:

```bash
uv run python scripts/measure_runtime.py --samples 5 --power
```

MiniCPM-V 4.6 can be added as the pet's visual cortex. It reads the rendered room camera frame and returns perception plus face blendshape hints, while MiniCPM5 remains the faster action/personality model:

```bash
scripts/start_with_minicpmv46_vision.sh
```

That script uses Ollama models:

- `hf.co/openbmb/MiniCPM5-1B-GGUF:Q4_K_M` for PET-LLM actions
- `openbmb/minicpm-v4.6` for vision perception

MiniCPM-V 4.6 local vision currently needs Ollama `0.30.0` or newer. The script checks this before pulling the vision model.

Check only the vision endpoint:

```bash
TOYBOX_VISION_ENDPOINT=http://127.0.0.1:11434/api/chat \
TOYBOX_VISION_MODEL=openbmb/minicpm-v4.6 \
uv run python scripts/check_vision_endpoint.py
```

If no endpoint is configured, the app uses a deterministic fallback policy so the toy remains playable. If an endpoint is configured but cannot be used, the default behavior is visible asleep/model-off mode rather than silently pretending a heuristic is the model.

Action traces are written to `data/traces/pet-actions.jsonl` by default. These become the seed dataset for a later distilled pet-policy model.

## Code Shape

- `src/pet_policy.py` is the small orchestration layer.
- `src/model_policy.py` talks to text/PET-LLM endpoints.
- `src/vision_policy.py` talks to MiniCPM-V-style image endpoints.
- `src/pet_actions.py` validates actions, face blendshapes, powers, and fallback behavior.
- `objectRecipe` in pet actions is the bounded generated-content path for wishable physical toys.
- `src/pet_payload.py` owns scene compaction, target selection, and touch detection.
- `src/pet_payload.py` also detects physical arrangements so model/fallback policies can ground guesses in object positions.
- `frontend/toybox/pet.js` owns character meshes, face drawing, and blendshape interpolation.
- `frontend/toybox/pet_balance.js` owns the hidden weighted standing/balance physics rig.
- `frontend/toybox/senses.js` owns user-view, pet-view, audio, and balance feeds.
- `frontend/toybox/room.js` owns the room shell, physics objects, and history.
- `frontend/toybox/powers.js` owns executable pet powers and target selection.

See `docs/modal-1bit-model-plan.md` for the current Modal, MiniCPM-V, MiniCPM5, and 1-bit policy plan.
