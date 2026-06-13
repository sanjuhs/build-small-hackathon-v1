# Discord Submission Draft

Hey everyone, I shipped **Toy Room v3: Fire Boy Virtual Pet** for Build Small Hackathon.

It is a tiny Talking Tom / Pokemon-like toy room where Fire Boy is the single controllable character. He uses a rigged unclothed GLB mesh as the live body, speaks in a babyish voice, and turns commands into visible room actions.

Demo commands:

- "Fire Boy, pick up the box"
- "Fire Boy, fireball the cube"
- "Fire Boy, run around the toy room"

What is load-bearing AI here:

- The app sends a compact scene payload to `/api/pet-action`.
- The brain returns strict PET action JSON: speech, emotion, animation, interaction verb, power, spell ops, sound, and debug timings.
- The renderer executes that JSON as Three.js/Cannon physics changes, rig clips, particles, projectile fireballs, object pickup/carry, and speech.
- The runtime panel shows which brain is active, whether vision is configured, how long the loop took, and how many state ops ran.

Current model status:

- The shipped demo currently runs reliably in trace-retrieval plus heuristic mode.
- MiniCPM/OpenAI-compatible PET LLM and MiniCPM-V visual cortex hooks are implemented but require endpoint variables/secrets.
- I also have a Modal MiniCPM-o 4.5 experiment, but it is currently the official demo server and needs a JSON-action adapter before it can be the live Toy Room control brain.

Links:

- Space: `https://build-small-hackathon-toy-room-v3.hf.space/toy-v3`
- GitHub: `https://github.com/sanjuhs/build-small-hackathon-v1`
- Architecture notes: `docs/virtual-toy-v3-architecture.md`

Tiny warm sparkle mode activated.
