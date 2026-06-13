# Prize Qualification Evidence

Toy Room v3 is packaged for the Build Small Hackathon as a tiny-world virtual pet: Fire Boy is a controllable character with a rigged unclothed mesh, babyish speech, physical toy interactions, visible powers, runtime traces, and configurable MiniCPM model backends.

## Public Links

- Hugging Face Space: `https://build-small-hackathon-toy-room-v3.hf.space/toy-v3`
- GitHub repository: `https://github.com/sanjuhs/build-small-hackathon-v1`
- Demo MP4: `demo/fire-boy-v3-demo.mp4`
- Modal MiniCPM-o endpoint: `https://sanjuhs123--minicpm-omni-demo.modal.run`

## Prize Map

| Prize | Current evidence |
| --- | --- |
| Best MiniCPM Build | `src/vision_policy.py` implements the MiniCPM-V visual cortex hook; `minicpm-v-serverless/` implements a ModelBest/OpenBMB MiniCPM-V serverless tester and API wrapper; `scripts/start_with_minicpm5.sh` runs a MiniCPM5 PET action policy through Ollama; `modal-minicpm-omni/` deploys `openbmb/MiniCPM-o-4_5` on Modal. |
| Best Use of Modal | `modal-minicpm-omni/modal_minicpm_omni.py` builds the official MiniCPM-o demo into a Modal image, caches model weights in `minicpm-omni-cache`, loads them on an L40S GPU, and serves the web gateway through Modal. Modal CLI verification shows app `minicpm-omni-45` deployed with an active container. |
| Best Use of Codex | The repository history contains Codex-attributed commits for the v3 toy room, Fire Boy command loop, MiniCPM-V helper, docs, and submission hardening. |
| Best Agent | The backend emits strict PET action JSON. The frontend executes it as character animation, speech, projectile fireballs, object pickup/carry, run routes, particles, physics updates, and loop metrics. |
| Off Brand | The Space is a custom Three.js toy-room UI mounted inside a Gradio-compatible app, not a default chatbot. |
| Best Demo | The MP4 demo shows direct commands, visible actions, speech, metrics, and toy-room controls in roughly 30 seconds. |

## Runtime Truth

Toy Room v3 can run with no secrets. In that mode it uses trace retrieval plus bounded deterministic actions so the judge demo remains stable. The runtime panel and `/api/model-status` make this visible instead of pretending a hosted model is active.

When model endpoints are configured, the same PET action contract supports:

- MiniCPM5 through local Ollama or any OpenAI-compatible text endpoint.
- MiniCPM-V 4.6 through an OpenAI-compatible vision endpoint such as ModelBest/OpenBMB serverless.
- RunPod/Hugging Face/OpenAI-compatible hosted routes.
- A future Modal JSON adapter that wraps the deployed MiniCPM-o stack for direct Toy Room action decisions.

## Architecture

```mermaid
flowchart LR
  Player["Player command"] --> UI["Toy Room v3 UI"]
  UI --> Payload["Compact scene payload\nobjects, Fire Boy state, camera frame"]
  Payload --> API["FastAPI /api/pet-action"]
  API --> Brain{"Configured brain?"}
  Brain -->|MiniCPM/OpenAI endpoint| Model["PET action model"]
  Brain -->|no secret| Trace["Trace retrieval"]
  Trace --> Fallback["Bounded command policy"]
  Model --> Action["PET action JSON"]
  Fallback --> Action
  Action --> Renderer["Three.js + Cannon"]
  Renderer --> Result["Speech, animation,\nfireball, pickup, run, particles"]
```

## MiniCPM Paths

```mermaid
flowchart TD
  ToyRoom["Toy Room v3"] --> TextHook["src/model_policy.py\nOpenAI-compatible text action brain"]
  ToyRoom --> VisionHook["src/vision_policy.py\nMiniCPM-V visual cortex"]
  TextHook --> LocalMini["MiniCPM5 via Ollama\nhf.co/openbmb/MiniCPM5-1B-GGUF"]
  VisionHook --> ModelBest["ModelBest/OpenBMB serverless\nMiniCPM-V-4.6-Instruct"]
  VisionHook --> LocalVision["Ollama MiniCPM-V 4.6"]
  Modal["modal-minicpm-omni"] --> Omni["openbmb/MiniCPM-o-4_5 on Modal L40S"]
  Omni -. "adapter planned" .-> TextHook
```

## Modal Evidence

The Modal app uses:

- App name: `minicpm-omni-45`
- Model: `openbmb/MiniCPM-o-4_5`
- GPU: `L40S`
- Volume: `minicpm-omni-cache`
- Secret: `huggingface-token`
- Public endpoint: `https://sanjuhs123--minicpm-omni-demo.modal.run`

Validation commands:

```bash
modal app list
modal container list --json
modal app logs minicpm-omni-45
curl https://sanjuhs123--minicpm-omni-demo.modal.run/health
```

The Modal path is a real runtime/development component for the submission. Toy Room v3 itself remains fast by default and uses Modal as the heavy MiniCPM-o companion until the JSON action adapter is added.

## Security Hygiene

- `.env`, nested `.env` files, `.claude/`, logs, traces, model caches, and virtual environments are ignored.
- `.env.example` files are tracked for setup only.
- Hugging Face and Modal credentials belong in Hugging Face Space secrets or Modal Secrets, not in the repository.
- The current tracked file list includes `.env.example` files only; the real local Modal frontend `.env` is ignored.

