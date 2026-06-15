---
license: mit
tags:
  - minicpm
  - minicpm-v
  - vision-language-action
  - vla
  - mujoco
  - robotics
  - synthetic-data
  - build-small-hackathon
task_categories:
  - image-to-text
  - text-classification
size_categories:
  - 1K<n<10K
---

# Fire Boy VLA Rollout And Evidence Artifacts

This dataset stores the public rollout, media, and proof artifacts for the Fire Boy MiniCPM-V 4.6 VLA demo.

- Space: https://build-small-hackathon-toy-room-v3.hf.space/toy-v3
- Research page: https://build-small-hackathon-toy-room-v3.hf.space/vla-research
- Policy gallery: https://build-small-hackathon-toy-room-v3.hf.space/fireboy-policy-gallery
- Model artifacts: https://huggingface.co/build-small-hackathon/fireboy-minicpm-v-4-6-vla

## Contents

- `vla-rollouts/`: image/action rollout datasets, JSONL manifests, and compressed image packs.
- `runpod_artifacts/`: RunPod/Newton-style training outputs, contact sheets, MP4/GIF policy proofs, and controller reports.
- `policy-proof-bundle/`: compact media and reports used by the in-app policy gallery.
- `showcase/`: MuJoCo learned/expert berry-eating videos.
- `demo/`: Toy Room v3 demo MP4 and thumbnail.

The dataset is intended as transparent evidence for the training process rather than as a polished benchmark. It contains successful policies, failed experiments, and intermediate variants so the demo story is inspectable.

## License

The generated rollouts, reports, cards, and media in this dataset are released under the MIT license. Upstream base models, external tools, and third-party libraries retain their original licenses.
