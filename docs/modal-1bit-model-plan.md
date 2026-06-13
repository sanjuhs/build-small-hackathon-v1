# Modal And 1-Bit Model Plan

## Recommendation

Use a two-brain architecture:

1. **Visual cortex:** MiniCPM-V 4.6, quantized at Q4/Q3, called sparsely for rendered camera frames.
2. **Action brain:** a tiny text/state-to-action policy, distilled from traces, called frequently for pet behavior.

Do not make MiniCPM-o 4.5 the first runtime brain. It is exciting for full-duplex video/audio/speech, but it is a 9B-class omni model. It is better for a later Modal-hosted wow demo than for a tiny always-on room pet.

Do not make 1-bit MiniCPM-V the first target either. The practical 1-bit path is strongest for the text/action policy, not the full vision-language stack. MiniCPM-V includes a vision encoder, projector, and language model; aggressive post-training 1-bit quantization risks breaking visual grounding exactly where the demo needs reliability.

The cleanest 1-bit lesson from Bonsai/BitNet is: train or adapt for the low-bit architecture first, then run it with kernels that actually exploit the representation. A generic post-training squeeze of a normal multimodal model is the risky path.

## Current Best Candidates

### PET-LLM action model

- Current local baseline: `hf.co/openbmb/MiniCPM5-1B-GGUF:Q4_K_M`
- Why: small, already running, OpenBMB-aligned, and the MiniCPM5 model card explicitly references a locally driven desktop pet use case.
- Role: takes compact state JSON plus recent text/touch/force history and outputs action JSON.

### Vision model

- First choice: `openbmb/minicpm-v4.6` or `openbmb/MiniCPM-V-4.6-gguf:Q4_K_M`
- Why: MiniCPM-V 4.6 is the smallest current MiniCPM-V route for image/video understanding. It uses SigLIP2-400M plus Qwen3.5-0.8B and is designed for edge deployment.
- Role: reads a canvas frame every 1-3 seconds or after important events, then returns perception and blendshape hints.

### 1-bit policy candidate

- First 1-bit experiment: `microsoft/bitnet-b1.58-2B-4T` or a smaller compatible BitNet-family model.
- Why: BitNet is native 1.58-bit rather than a fragile post-training squeeze of a normal model. It has an official inference stack, `bitnet.cpp`, for CPU/mobile-style deployment.
- Role: text/state-to-action JSON policy only.

### Omni model candidate

- Later wow-demo path: `openbmb/MiniCPM-o-4_5` or an int4/GGUF variant.
- Why: it can process continuous video and audio input while producing concurrent text and speech output.
- Constraint: it is a 9B-class omni model, so it belongs on Modal or a GPU box first. For Three.js movement, it still needs to emit our action JSON schema; "movement" is an app-level tool output, not a native audio/video modality.

## Current Measurement Baseline

Before the context/output cap patch, the local MiniCPM5 Ollama runner was observed as:

- Tiny Toybox app process: about 145 MB RSS.
- Ollama server process: about 95 MB RSS.
- Ollama MiniCPM5 runner: about 1.56 GB RSS while generating.
- `ollama ps`: about 2.5 GB model size, 100% GPU, 32768 context.
- `/api/pet-action` latency over 5 calls: min 1.71s, median 2.98s, mean 3.02s, max 4.49s.
- Power: not measured yet because macOS `powermetrics` requires sudo.

The runtime now caps Ollama action calls by default:

```bash
TOYBOX_LLM_NUM_CTX=2048
TOYBOX_LLM_NUM_PREDICT=180
TOYBOX_VISION_NUM_CTX=4096
TOYBOX_VISION_NUM_PREDICT=220
```

After restarting with the cap and unloading/reloading the Ollama runner:

- `ollama ps`: about 890 MB model size, 100% GPU, 2048 context.
- Ollama MiniCPM5 runner RSS: about 890 MB.
- Tiny Toybox app process: about 144-145 MB RSS.
- `/api/pet-action` latency over 5 warmed calls: min 1.18s, median 2.90s, mean 2.58s, max 3.89s.

The memory win is large; latency is still too variable for "instant" pet behavior, so immediate local animations should stay deterministic while the model response catches up.

Use this after each model/runtime change:

```bash
uv run python scripts/measure_runtime.py --samples 5
```

For macOS power sampling:

```bash
uv run python scripts/measure_runtime.py --samples 5 --power
```

The `--power` mode only works when `sudo -n powermetrics` is allowed.

## Efficiency Playbook

1. Keep the renderer deterministic at 60 FPS; never block touch feedback on a model call.
2. Send compact state JSON and pointer/touch facts to the action model.
3. Cap context and output tokens aggressively for the action policy.
4. Call MiniCPM-V only after meaningful events or every few seconds, not every frame.
5. Distill high-rated traces into a tiny action brain.
6. Benchmark three action brains with the same script:
   - current MiniCPM5 Q4
   - a smaller Qwen/MiniCPM-style Q4/Q3 policy
   - BitNet/Bonsai-style 1-bit candidate
7. Promote the 1-bit model only if JSON validity, visible-action score, and latency all improve.

## Unsloth / Fine-Tuning Read

Unsloth is useful for LoRA/QLoRA-style fine-tuning and now documents vision/multimodal training workflows. It is not the first tool I would use for "make MiniCPM-V 4.6 a 1-bit multimodal model." That is a different systems problem: the low-bit architecture and inference kernels matter as much as the fine-tune.

Recommended order:

1. Fine-tune or distill the action policy first with standard LoRA/SFT.
2. Export/quantize to Q4/Q3 GGUF and verify behavior.
3. Try a native BitNet/Bonsai-style 1-bit action model separately.
4. Keep MiniCPM-V or MiniCPM-o as perception/audio specialists rather than forcing everything into one 1-bit model.

## Training Plan

1. Keep logging traces to `data/traces/pet-actions.jsonl`.
2. Add ratings for the best clips:
   - touched/petted reaction felt alive
   - action affected a real object
   - speech stayed short
   - face blendshape matched emotion
   - no invalid JSON
3. Use Modal for remote jobs:
   - clean traces into SFT rows
   - generate synthetic variants
   - run LoRA/SFT for MiniCPM5-1B first
   - evaluate JSON validity and visible-action score
4. Quantize the best action model:
   - Q4/Q3 GGUF first for reliability
   - then test 1.58-bit / BitNet route as an edge experiment
5. Keep MiniCPM-V 4.6 separate from the action model:
   - vision outputs compact perception
   - action model decides behavior
   - renderer executes deterministic powers

## Realtime Budget

For a pet, "realtime" should mean:

- 60 FPS renderer and physics stay local.
- Touch/hover/pet responses happen immediately via deterministic animation.
- Text/action policy responds in under 300-800 ms when local.
- Vision perception can be slower, around 1-3 seconds, because it enriches context rather than gating touch feedback.

## Modal Smoke Test

The local Modal client was verified with:

```bash
uv run --with modal modal run scripts/modal_square_smoke.py
```

Expected result:

```text
modal_square_result 1764
```

## Next Build Step

Add a Modal training/eval script that reads local traces, validates them into an SFT dataset, and runs a tiny reward/eval table before any expensive fine-tuning.
