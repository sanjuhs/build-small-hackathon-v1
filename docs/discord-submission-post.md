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

MiniCPM / Modal / Codex:

- The shipped demo currently runs reliably in trace-retrieval plus heuristic mode.
- MiniCPM/OpenAI-compatible PET LLM and MiniCPM-V visual cortex hooks are implemented behind endpoint variables/secrets.
- `minicpm-v-serverless/` contains a ModelBest/OpenBMB MiniCPM-V 4.6 helper and API tester.
- `modal-minicpm-omni/` deploys `openbmb/MiniCPM-o-4_5` on Modal with an L40S GPU, Modal Volume, and Modal Secret.
- The repo has Codex-attributed commits for the v3 toy room, Fire Boy command loop, MiniCPM-V helper, and submission docs.

Links:

- Space: `https://build-small-hackathon-toy-room-v3.hf.space/toy-v3`
- GitHub: `https://github.com/sanjuhs/build-small-hackathon-v1`
- Demo MP4: `https://huggingface.co/spaces/build-small-hackathon/toy-room-v3/resolve/main/demo/fire-boy-v3-demo.mp4`
- Architecture notes: `docs/virtual-toy-v3-architecture.md`
- Prize evidence: `docs/prize-qualification.md`

Target prizes: Best MiniCPM Build, Best Use of Modal, Best Use of Codex, Best Agent, Off Brand, and Best Demo.
