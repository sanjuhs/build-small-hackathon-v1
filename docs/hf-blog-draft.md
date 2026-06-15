# Fire Boy: Turning MiniCPM-V 4.6 Into A Tiny Virtual Pet VLA

Fire Boy started as a very simple wish: make a virtual toy that feels closer to a living Tamagotchi than a chatbot. The final demo is a small Three.js room where a player can type or speak commands, and Fire Boy can walk, pick up objects, find and eat a berry, react with sound, and expose the evidence trail behind those decisions.

The core technical experiment is a MiniCPM-V 4.6 vision-language-action route. We froze the MiniCPM-V backbone, pooled the vision-language embedding, trained a small router/action head, and mapped the head into a bounded skill contract. That contract dispatches into MuJoCo policy proofs, then the web app retargets the result into the live Fire Boy character.

## Links

- Demo Space: https://build-small-hackathon-toy-room-v3.hf.space/toy-v3
- Research page: https://build-small-hackathon-toy-room-v3.hf.space/vla-research
- Policy gallery: https://build-small-hackathon-toy-room-v3.hf.space/fireboy-policy-gallery
- Model artifacts: https://huggingface.co/build-small-hackathon/fireboy-minicpm-v-4-6-vla
- Dataset artifacts: https://huggingface.co/datasets/build-small-hackathon/fireboy-vla-rollout-artifacts

## What Actually Runs

Toy Room v3 has two Modal model lanes:

- `fireboy-vla-router`: MiniCPM-V 4.6, frozen embedding, trained skill/parameter head, first embodied action route.
- `minicpm-omni-45`: MiniCPM-o 4.5, fallback/general PET action JSON route.

The backend path is intentionally inspectable:

```text
/api/pet-action
  -> run_vla_router_pet_action(payload)
  -> Modal fireboy-vla-router /route
  -> MiniCPM-V skill/parameter head
  -> MuJoCo policy registry
  -> retargeted PET JSON
  -> Three.js Fire Boy action
```

## Why This Direction Matters

The interesting part is not just that Fire Boy can pick up a ball. The interesting part is that a small multimodal model can become a controller when it is given a narrow, inspectable action interface. Instead of asking the model to directly output thousands of unstable joint torques, the first shipped route predicts a skill and a few target parameters, then uses physics policies and app-level guards to make the action visible and reliable.

That makes the demo small enough for a hackathon while still pointing toward a bigger idea: virtual pets, embodied agents, and eventually small consumer-friendly VLAs that can run cheaply, reason over vision, and act inside a simulated or physical body.

## Codex And Modal

OpenAI Codex was used throughout the build: scaffolding routes and pages, wiring the VLA router, debugging Modal cold-start behavior, packaging the research page and PDF, generating evidence views, tightening README/prize docs, and keeping the implementation in commit-sized chunks.

Modal made the runtime practical. The MiniCPM-V router and MiniCPM-o fallback both run as public Modal apps with GPU-backed workers and 180-second scale-down windows, so the Space can stay lightweight while still calling real MiniCPM-family models.

## Future Work

The next version should move beyond a frozen-backbone router into deeper adapters or full fine-tuning, potentially making a single MiniCPM-V or omni-style model the pet's perception, action, voice, and memory controller. It should also add richer rollouts, learned multi-agent interactions, stronger RL or imitation-learning loops, and lower-latency inference paths for real-time play.

