# Toy Room v3 Animation Sequencer Handoff

Status as of pause:

- Last clean pushed commit before this pause: `093936f fix: add grounded Fire Boy gestures`.
- Local work after that commit is partially implemented and not yet tested/committed.
- Existing Toy v3 already has working grounded commands for:
  - `turn around`
  - `look at me`
  - `point at yellow ball`
  - `reach for blue cube`
  - `pick up yellow ball`
  - `drop it`
- Browser verification showed Ollama MiniCPM-V actions working with brain trace metrics around 110-140 tok/s for those commands.

Partial changes currently started:

- `src/pet_profiles.py`
  - Added `confused` emotion.
  - Expanded Fire Boy animation names with `listen`, `think`, `nod`, `shake`, `confused`, `search`, `hold`, `place`, `push`, `kick`, `cast`, `recover`.
- `frontend/toybox/config.js`
  - Added a `confused` face blend preset.
- `src/pet_actions.py`
  - Expanded `INTERACTION_VERBS` with `listen`, `think`, `confirm`, `deny`, `confused`, `search`, `place`, `push`, `roll`, `kick`.
- `frontend/toybox/pet.js`
  - Added procedural pose support for:
    - `listen` / `think`
    - `nod`
    - `shake`
    - `confused`
    - `search`
    - `hold`
    - `place`
    - `push`
    - `kick`
    - `cast`
    - `recover`
  - Important: this is procedural body/head/arm/flame animation. The eye texture is not separately rigged, so emotion is carried by pose plus existing face canvas/blendshape.

Not finished yet:

1. Finish `frontend/toybox/v2_main.js` sequencing.
   - Add `Copy` icon import to fix missing copy icon warning.
   - Bump pet module cache query to `pet.js?v=20260614-sequenced-gestures`.
   - Add rig clip fallbacks for `listen`, `think`, `nod`, `shake`, `confused`, `search`, `place`, `push`, `kick`, `cast`, `recover`.
   - Add `runActionSequence(agent, steps)` helper or equivalent.
   - Make pending model state play `listen`/`think`.
   - Add renderer handlers for:
     - `confirm` -> nod
     - `deny` -> shake
     - `confused` -> confused shrug
     - `search` -> scan/turn/point target
     - `place` -> put held object down softly
     - `push` / `roll` / `kick` -> approach object, pose, impulse object
     - fireball -> cast windup, projectile, recover

2. Finish backend command coercion.
   - Add natural-language routes:
     - yes / okay / nod -> `confirm`
     - no / stop / don't -> `deny`
     - confused / don't understand / which one -> `confused`
     - find / search / where is -> `search`
     - put it here / place it / set it down -> `place`
     - push / roll / kick ball/cube -> `push`, `roll`, `kick`
   - Update `fallback_policy` to choose these verbs.
   - Update MiniCPM/Modal/Ollama prompts with the new verbs.
   - Update `trace_policy.py` request satisfaction checks.

3. Add tests.
   - `test_confirm_uses_nod`
   - `test_deny_uses_shake`
   - `test_confused_uses_confused`
   - `test_search_yellow_ball_targets_soft_ball`
   - `test_push_blue_cube_targets_cube`
   - `test_kick_yellow_ball_targets_soft_ball`
   - `test_place_after_pickup_uses_place`

4. Run verification.
   - `node --check frontend/toybox/v2_main.js`
   - `node --check frontend/toybox/pet.js`
   - `python3 -m py_compile src/pet_actions.py src/command_coercion.py src/modal_omni_policy.py src/model_policy.py src/vision_action_policy.py src/pet_profiles.py src/trace_policy.py`
   - `uv run python -m unittest discover -s tests`
   - Restart local server.
   - Browser-verify `/toy-v3` with screenshots for:
     - "nod yes"
     - "shake no"
     - "look confused"
     - "find the yellow ball"
     - "push the blue cube"
     - "kick the yellow ball"
     - "fireball the blue cube"

Recommended next implementation order:

1. Finish `v2_main.js` renderer sequencing first, because visible behavior is the point.
2. Add command coercion and tests.
3. Run browser verification and capture screenshots.
4. Commit as something like `fix: add Toy v3 action sequencer`.

Notes:

- Do not try to animate the baked mesh eyes directly unless we decide to edit the model/texture pipeline. For now, use head tilt, body lean, arm pose, flame pulse, existing face blendshape, and speech.
- There is an untracked `fireboy-vla-physics/` directory in the worktree. It was not part of this sequencer work; inspect before touching.
