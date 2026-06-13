# Model And Alignment Notes

## Current Runtime Decision

Start with a deterministic action policy and an OpenAI-compatible endpoint hook. This prevents the app from feeling broken when no GPU model is attached.

## Preferred Small Model Path

Use two models instead of one giant pet brain:

- MiniCPM-V 4.6 as a sparse visual cortex for rendered camera frames.
- MiniCPM5-1B or a distilled 1-bit/BitNet-style text model as the fast action policy.

This keeps touch and mouse interactions snappy while still letting the pet "see" the room.

Nemotron 3 Nano remains useful for:

- text/personality reasoning
- NVIDIA-friendly story
- agentic JSON action planning

But the multimodal Nemotron Omni parameter count should be confirmed before relying on it for submission because model cards and metadata can be interpreted differently.

MiniCPM-o 4.5 is a strong later demo path for full-duplex video/audio/speech, but it is too heavy for the first mobile-style pet loop.

The 1-bit plan should target the action policy first. Native 1.58-bit models such as BitNet are more plausible than post-training 1-bit quantizing a multimodal MiniCPM-V stack.

## Multimodal I/O Decision

The app should treat multimodality as a modular contract:

- Inputs: text, pointer/touch, room state, forces, detected objects, optional camera frame, optional microphone transcript.
- Perception output: compact visual/audio facts and blendshape hints.
- Action output: the strict PET-LLM JSON schema that drives speech text, emotion, animation, blendshape, powers, and symbolic sound IDs.
- Audio output: start with local pet sounds for reliability; later add MiniCPM-o speech or a TTS model as a replaceable sound module.

MiniCPM-o 4.5 can support simultaneous video/audio input and text/speech output, but movement still needs our renderer-facing action schema. The model can choose `animation`, `blendshape`, and `power`; Three.js executes them.

## Inference Efficiency Checklist

- Keep `TOYBOX_LLM_NUM_CTX` small for action JSON.
- Keep `TOYBOX_LLM_NUM_PREDICT` small enough that invalid rambling is impossible.
- Use deterministic fallback reactions immediately for petting, poking, and hover.
- Let the model refine behavior asynchronously.
- Re-run `uv run python scripts/measure_runtime.py --samples 5` after every model/runtime swap.
- Use `--power` only when macOS `powermetrics` has sudo access.

## Reward Function Draft

Reward a pet action when it:

- references a real object or recent event
- uses the pet's signature power
- creates visible motion or visible state change
- keeps speech under 18 words
- remains cute, playful, and non-mean
- does not repeat the same action more than twice in a row
- chooses an action that can be executed by the renderer

Penalize when it:

- produces invalid JSON
- chooses an unavailable power
- talks abstractly without acting
- writes long explanations
- ignores collisions or user interaction
- makes the room too chaotic to read

## Dataset Shape

```json
{
  "input": {
    "pet": "squeaky",
    "user_message": "make the cube stop",
    "scene": {
      "objects": [
        {"id": "cube-1", "kind": "cube", "speed": 2.5, "distanceToPet": 1.2}
      ],
      "recentForces": [
        {"kind": "collision", "objectId": "cube-1", "impact": 0.7}
      ]
    }
  },
  "output": {
    "speech": "Hold still, noisy cube.",
    "emotion": "focused",
    "animation": "trunk_wiggle",
    "power": {"name": "time_freeze", "targetId": "cube-1", "durationMs": 1800}
  },
  "rating": 5
}
```
