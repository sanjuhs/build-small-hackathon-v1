# Living Build Plan: Tiny Toybox

## Product Brief

Build a delightful Gradio-hosted virtual toy: a chibi AI pet in a small 3D room that sees objects, notices forces, talks back in short characterful lines, and chooses powers that create visible physics effects.

Current visual direction comes from the provided plush references:

- Squeaky: elephant/time keeper, bowler hat, tiny clock, soft blue-gray plush.
- Electraica: yellow robot/lightbulb, cheerful electric helper.
- Fire Boy: flame hood, extinguisher pack, fireball chaos.
- Shark Girl: blue sea creature, wave powers, ukulele sweetness.

The first playable vertical slice is **Squeaky's Time Room**.

## Hackathon Fit

Track: An Adventure in Thousand Token Wood.

Primary judging goals:

- Genuinely delightful enough to show a friend.
- AI is load-bearing: the pet decides what to do from scene state, not only from fixed buttons.
- Original concept: toy-room creature with powers, perception, forces, and a small-model personality brain.
- Polished Gradio app with a custom UI, not the default chatbot look.

Bonus quests we can realistically target:

- Off-Brand: custom Three.js UI inside Gradio.
- Well-Tuned: fine-tune/publish a small pet-action policy model after we collect traces.
- Llama Champion: run a MiniCPM/Nemotron-compatible quantized model through llama.cpp if practical.
- Field Notes: write a short build report.
- Sharing is Caring: publish agent traces / interaction traces.

## Core Loop

1. User enters the room and sees a pet already alive.
2. User drags/throws objects or says something.
3. The app captures:
   - user message
   - room object positions
   - recent collisions / force events
   - lightweight detected objects from the pet perspective
   - optional canvas screenshot as camera frame
4. AI policy returns compact JSON:
   - speech
   - emotion
   - animation
   - chosen power
   - target object
   - power parameters
5. Three.js executes the action:
   - facial expression changes
   - pet moves/gestures
   - physics objects react
   - effects appear
6. Interaction trace is stored for future distillation/fine-tuning.

## AI Contract

The runtime model should output only this schema:

```json
{
  "pet": "squeaky",
  "speech": "Tick-tock. I paused the loud cube.",
  "emotion": "glee",
  "animation": "trunk_wiggle",
  "intent": "playful_intervention",
  "power": {
    "name": "time_freeze",
    "targetId": "all-moving",
    "strength": 0.8,
    "durationMs": 2200
  },
  "sound": "clock_chime"
}
```

Valid powers:

- Squeaky: `time_freeze`, `shrink`, `rewind`, `clock_bubble`
- Electraica: `shock`, `lamp_burst`, `magnet_pull`
- Fire Boy: `fireball`, `ember_jump`, `smoke_poof`
- Shark Girl: `wave`, `bubble_lift`, `tide_pull`

## Model Strategy

Phase 1 uses a deterministic local fallback policy so the toy is always playable.

Phase 2 adds an OpenAI-compatible local endpoint hook:

- `TOYBOX_LLM_ENDPOINT`
- `TOYBOX_LLM_MODEL`

This lets us plug in MiniCPM-V, Nemotron, llama.cpp, Ollama, vLLM, or SGLang without rewriting the room.

Recommended first model path:

1. MiniCPM5-1B for the current PET-LLM action policy.
2. MiniCPM-V 4.6 for sparse multimodal room/camera interpretation because it is small and OpenBMB-aligned.
3. A smaller distilled action policy trained from traces, with a 1.58-bit / BitNet-style edge experiment after the Q4 baseline works.
4. Optional MiniCPM-o 4.5 or Nemotron Omni for a Modal-hosted full-duplex wow demo, not the first mobile loop.

Modal is now available for remote jobs. Use it for trace cleaning, evals, LoRA/SFT experiments, and heavier multimodal tests.

Efficiency rule: the pet's body should react instantly from local code, then let the model add personality. Keep model calls small, measured, and replaceable.

## What Makes A Good Virtual Pet

The pet should feel alive because it has:

- Idle behavior: breathing, looking around, fidgeting, blinking.
- Agency: it sometimes chooses actions without being directly commanded.
- Preferences: likes clocks, soft balls, music, and gentle chaos; dislikes loud crashes.
- Memory: remembers recent events and callbacks.
- Embodied limits: can only affect objects in the room and powers have cooldowns.
- Short speech: toy-like, quotable, not essay-like.
- Cute failure: when it misunderstands, it still does something charming.
- Touch response: reacts to being clicked, dragged near objects, or surrounded.
- Object curiosity: comments on specific objects, not generic chat.
- Power identity: each pet has one mechanic that is instantly legible on video.

## Step-By-Step Build Plan

### 0. Project Setup

1. Create Gradio app entrypoint.
2. Add FastAPI routes for custom HTML and AI action API.
3. Add frontend static files.
4. Add a clean requirements file for Hugging Face Spaces.
5. Add a living plan and model notes.

### 1. First Toy Room

1. Create a Three.js scene.
2. Add a camera with constrained orbit controls.
3. Add physically lit floor, walls, and soft shadows.
4. Add Cannon physics world.
5. Add draggable blocks, balls, dominoes, a lamp, and a clock.
6. Add collision event tracking.
7. Add a scene-state serializer.
8. Add a camera-frame capture hook.

### 2. First Pet Model: Procedural Squeaky

1. Build a plush elephant body from primitives.
2. Add soft ears, trunk, hat, suit, suitcase, and clock.
3. Add face texture states: happy, curious, surprised, glee, focused, sleepy.
4. Add blend-state interpolation in code.
5. Add idle breathing and blinking.
6. Add movement states: bounce, look, wiggle, shrink, recover.
7. Confirm the first generator model moves correctly before building Blender assets.

### 3. Powers And Effects

1. `time_freeze`: freeze moving objects and tint the room.
2. `shrink`: pet shrinks and scurries.
3. `rewind`: an object snaps back through recent history.
4. `clock_bubble`: a transparent clock bubble expands from Squeaky.
5. Add particle effects with lifetimes.
6. Add cooldowns so effects feel intentional.
7. Add audio hooks later if time permits.

### 4. AI Policy

1. Define a strict output schema.
2. Implement deterministic fallback policy.
3. Add OpenAI-compatible endpoint adapter.
4. Add JSON repair and validation.
5. Add prompt with pet profiles and behavior constraints.
6. Add trace logging.
7. Add reward rubric for future alignment:
   - visible action happened
   - short cute speech
   - object-aware
   - power matched character
   - avoids repetitive actions
   - avoids unsafe/mean behavior

### 5. Model Input Expansion

1. Send scene state: objects, positions, speeds, nearest objects.
2. Send collision/force events.
3. Send detected objects from pet view.
4. Send canvas screenshot as a camera frame.
5. Send explicit pointer/touch interactions: mouse, finger/touch, pen, screen coordinates, NDC, and pet hit point.
6. If using MiniCPM-V, include image input through the local endpoint.
7. Add a debug panel that shows what the pet saw without making the UI feel like a lab dashboard.

### 6. Additional Pets

1. Add Electraica procedural model.
2. Add Fire Boy procedural model.
3. Add Shark Girl procedural model.
4. Add pet selection.
5. Add power-specific objects:
   - Electraica: lamp, coils, metal blocks.
   - Fire Boy: candles, paper blocks, extinguishable props.
   - Shark Girl: puddles, shells, floating toys.
6. Give each pet a distinct behavior prompt and fallback policy.

### 7. Blender Asset Pipeline

1. Create a Blender script for each pet.
2. Export GLB files with:
   - body rig or grouped primitives
   - face shape keys / blend shapes
   - idle animation
   - gesture animation
3. Load GLB in Three.js.
4. Map AI emotions to morph target influences.
5. Keep procedural fallback for robustness.

### 8. Distillation And Fine-Tuning

1. Log every input/output pair.
2. Mark the best interactions manually.
3. Generate synthetic variants from successful traces.
4. Fine-tune a small policy model or LoRA.
5. Publish the model on Hugging Face.
6. Swap the fallback policy to the published fine-tune for the Well-Tuned badge.
7. Benchmark MiniCPM5 Q4, Q3/Q4 distilled policies, and a native 1-bit BitNet/Bonsai-style action model with `scripts/measure_runtime.py`.

### 9. Polish

1. Improve lighting and material softness.
2. Add expressive particles.
3. Add smooth transitions between actions.
4. Add short, punchy pet lines.
5. Add a replayable demo script.
6. Ensure mobile layout does not overlap.
7. Verify the room renders in desktop and mobile viewports.
8. Record demo video with three strong moments:
   - pet notices thrown object
   - pet chooses a power
   - power changes the room.

### 10. Submission

1. Host as Hugging Face Space.
2. Add README with model constraints and local-first notes.
3. Add demo video.
4. Add social post.
5. Add field notes/report.
6. Publish trace or sample dataset if useful.

## Immediate Milestone

Milestone 1 is complete when:

- Gradio app launches locally.
- The room renders.
- Squeaky appears in the room.
- Objects can be dragged/thrown.
- Squeaky can speak and change expression.
- AI/fallback policy can trigger at least `time_freeze`, `shrink`, and `rewind`.
