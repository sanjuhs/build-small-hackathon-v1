# Mixamo Download Drop Folder

Put downloaded Mixamo FBX files here, grouped by character:

- `squeaky/*.fbx`
- `electraica/*.fbx`
- `fire-boy/*.fbx`
- `shark-girl/*.fbx`

Recommended Mixamo download settings for direct viewer tests:

- Format: `FBX Binary`
- Skin: `With Skin`
- Frames per second: `30`
- Keyframe reduction: `None`

Then run:

```bash
./scripts/import_mixamo_motions.sh
```

Converted GLBs will be written to:

```text
assets/generated/part-models/mixamo-motion-tests/<character>/
```
