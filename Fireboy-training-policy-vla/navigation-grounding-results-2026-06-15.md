# Navigation Grounding Results - 2026-06-15

## What was added

- Toy v3 now creates a virtual scene target:
  - `id=player-camera`
  - `kind=viewer`
  - tags: `me`, `camera`, `viewer`, `player`, `user`, `here`
  - affordances: `go_to`, `follow`, `look_at`
- The target is the viewer camera projected onto the room floor and clamped into the playable room.
- The VLA/MuJoCo bridge preserves this target for movement commands.
- The frontend command resolver treats phrases like `walk towards me`, `come here`, `walk to camera`, and `walk to viewer` as `player-camera`.
- Object navigation still works for phrases like `walk towards the ball`.

## Verified

- `walk towards me`
  - backend: `skill=walk_to`
  - backend interaction: `targetId=player-camera`
  - frontend: `vlaLiveTarget=player-camera`
  - frontend: `vlaLiveGrounding=player-camera`
  - retarget: `rigRetargetFrames=80`
  - retarget source: `mujoco_articulated_policy`

- `walk towards the ball`
  - frontend: `vlaLiveTarget=soft-ball`
  - frontend: `vlaLiveTargetKind=ball`
  - retarget: `rigRetargetFrames=80`
  - retarget source: `mujoco_articulated_policy`

## Training implication

We do not need a separate walking policy for every noun. The useful structure is:

`image + language + robot state + grounded target coordinates -> walk_to action chunk`

The VLM/VLA resolves the command into a target, then the locomotion policy uses the target coordinates. To train further, add rollouts with randomized targets:

- object targets: ball, cube, berry, chair, table, trash, generated toys
- viewer/camera targets: `player-camera`
- spatial targets: left side, right side, center, near wall, pointed location

That gives the action head enough examples to learn target-conditioned walking while keeping one reusable `walk_to` skill.
