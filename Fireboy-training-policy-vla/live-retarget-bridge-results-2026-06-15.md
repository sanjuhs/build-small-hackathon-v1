# Live Fireboy Retarget Bridge Results - 2026-06-15

## Correct Fireboy asset

- Runtime GLB: `fire-boy-rig/fire-boy-rigged-full.glb`
- Rig bones detected in Toy v3: 20 usable Fireboy bones, including `Hand.L` and `Hand.R`
- Frontend script cache tag verified: `v2_main.js?v=20260615-vla-retarget3`

## What changed

- Backend policy bridge now attaches a `retargetTrajectory` payload to `debug.mujocoPolicy`.
- Movement skills (`run_around`, `go_to_point`) can use the articulated MuJoCo rollout trajectory directly.
- Pickup/eat skills use successful MiniCPM-V rollout-manifest joint states as the retarget source, while preserving the existing successful object interaction path.
- Toy v3 applies those retarget frames to the real Fireboy GLB bones instead of only showing a MuJoCo proof video.
- The simplified MuJoCo rollout popup is suppressed for live retargeted Toy v3 actions, so the main visual is the real Fireboy model.
- Picked objects now anchor to Fireboy's rigged hand bones when available (`heldObjectAnchor=fireboy-hands`).

## Verified commands

- `pick up the ball`
  - `vlaLiveBridge=pick_up:grasped`
  - `vlaLiveTarget=soft-ball`
  - `rigRetargetFrames=37`
  - `rigRetargetSource=minicpm_vla_rollout_manifest`
  - `heldObject=soft-ball`
  - `heldObjectAnchor=fireboy-hands`

- `go find berry and eat it`
  - `vlaLiveBridge=find_and_eat_berry:eaten`
  - `vlaLiveTarget=berry-rose`
  - `rigRetargetFrames=49`
  - `rigRetargetSource=minicpm_vla_rollout_manifest`

- `run around`
  - `vlaLiveBridge=run_around:live-route`
  - `rigRetargetFrames=90`
  - `rigRetargetSource=mujoco_articulated_policy`

## Proof screenshots

- `Fireboy-training-policy-vla/proofs/toy-v3-fireboy-hand-grasp.png`
- `Fireboy-training-policy-vla/proofs/toy-v3-fireboy-pickup-retarget-clean.png`

## Important limitation

This is now a live Fireboy GLB retarget/control bridge in Toy v3. It is not yet a fully learned contact-rich grasp policy where MuJoCo hand contacts alone lift the ball. The current practical demo combines:

1. MiniCPM-V / MuJoCo skill selection and rollout evidence.
2. Retargeted joint trajectories applied to the Fireboy GLB.
3. Toy v3 object anchoring to the Fireboy hand bones for visible grasp/carry.

The next physics-training step is to make the MuJoCo articulated body itself learn stable two-hand contact and then export those higher-quality contact rollouts back into this same retarget bridge.
