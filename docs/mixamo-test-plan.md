# Mixamo Test Plan

Use the unrigged FBX exports first for Adobe Mixamo auto-rig tests:

- `assets/generated/part-models/mixamo-fbx/squeaky-base-mesh.fbx`
- `assets/generated/part-models/mixamo-fbx/electraica-base-mesh.fbx`
- `assets/generated/part-models/mixamo-fbx/fire-boy-base-mesh.fbx`
- `assets/generated/part-models/mixamo-fbx/shark-girl-base-mesh.fbx`

The local Blender rigged FBX exports are also available for inspection:

- `assets/generated/part-models/mixamo-fbx/squeaky-base-rigged.fbx`
- `assets/generated/part-models/mixamo-fbx/electraica-base-rigged.fbx`
- `assets/generated/part-models/mixamo-fbx/fire-boy-base-rigged.fbx`
- `assets/generated/part-models/mixamo-fbx/shark-girl-base-rigged.fbx`

Recommended Mixamo flow:

1. Upload one `*-base-mesh.fbx` file.
2. Place Mixamo auto-rig markers on chin, wrists, elbows, knees, and groin.
3. Download one neutral rigged FBX plus a batch of test animations.
4. Save downloaded animation files under `assets/generated/part-models/mixamo-downloads/<character>/`.
5. Run `./scripts/import_mixamo_motions.sh`.
6. Open `/blender-models`; converted files show up as `Mixamo motion test` assets.

Recommended starter batch for each character:

- Idle / breathing idle
- Walk
- Run
- Jump
- Wave
- Clap or cheering
- Turn / turn-in-place
- Sit or crouch, if the mesh tolerates it

Recommended Mixamo download settings for this direct viewer pipeline:

- Format: `FBX Binary`
- Skin: `With Skin`
- Frames per second: `30`
- Keyframe reduction: `None`

The converter reads:

- `assets/generated/part-models/mixamo-downloads/squeaky/*.fbx`
- `assets/generated/part-models/mixamo-downloads/electraica/*.fbx`
- `assets/generated/part-models/mixamo-downloads/fire-boy/*.fbx`
- `assets/generated/part-models/mixamo-downloads/shark-girl/*.fbx`

And writes:

- `assets/generated/part-models/mixamo-motion-tests/<character>/*.glb`
- `assets/generated/previews/<character>-mixamo-*.png`

Use the socketed assembly `.blend` files for object attachment and physics tuning:

- `assets/generated/part-models/blend-scenes/squeaky-assembly.blend`
- `assets/generated/part-models/blend-scenes/electraica-assembly.blend`
- `assets/generated/part-models/blend-scenes/fire-boy-assembly.blend`
- `assets/generated/part-models/blend-scenes/shark-girl-assembly.blend`
