from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from train_minicpm_vla_skill_param_head import (
    MiniCPMSkillParamHead,
    encode_minicpm_skill_param_prompt,
    evaluate_head_arrays,
    load_skill_param_samples,
    make_skill_param_cache_key,
)
from train_minicpm_vla_action_head import load_embedding_cache, load_minicpm, save_embedding_cache


DEFAULT_CHECKPOINT = Path("fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt")


def eval_minicpm_vla_skill_param_head(
    checkpoint: Path,
    manifests: list[Path],
    *,
    limit_rows: int = 512,
    embedding_cache: Path | None = None,
) -> dict[str, Any]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install torch before evaluating the MiniCPM-V skill-param head") from exc

    payload = torch.load(checkpoint, map_location="cpu")
    samples = load_skill_param_samples(
        manifests,
        limit_rows=limit_rows,
        state_mode=str(payload.get("state_mode", "nav_clock")),
        include_stage_flags=bool(payload.get("include_stage_flags", True)),
    )
    if not samples:
        raise RuntimeError(f"No usable skill-param samples in manifests: {manifests}")

    processor, minicpm = load_minicpm_for_checkpoint(payload, checkpoint)
    minicpm.eval()
    for param in minicpm.parameters():
        param.requires_grad_(False)

    cache = load_embedding_cache(embedding_cache)
    embeddings: list[np.ndarray] = []
    cache_hits = 0
    for index, sample in enumerate(samples):
        cache_key = make_eval_cache_key(sample, payload, checkpoint)
        if cache_key in cache:
            embedding = cache[cache_key]
            cache_hits += 1
        else:
            embedding = encode_minicpm_skill_param_prompt(
                processor,
                minicpm,
                sample.image_path,
                sample.instruction,
                downsample_mode=str(payload.get("downsample_mode", "16x")),
                max_slice_nums=int(payload.get("max_slice_nums", 9)),
            )
            cache[cache_key] = embedding
        embeddings.append(embedding)
        if (index + 1) % 50 == 0:
            print(json.dumps({"encoded": index + 1, "total": len(samples), "cache_hits": cache_hits}), file=sys.stderr, flush=True)
    save_embedding_cache(embedding_cache, cache)

    vl = np.asarray(embeddings, dtype=np.float32)
    states = np.asarray([sample.state for sample in samples], dtype=np.float32)
    params = np.asarray([sample.target_params for sample in samples], dtype=np.float32)
    skill_ids = np.asarray([sample.skill_id for sample in samples], dtype=np.int64)
    features = np.concatenate(
        [
            (vl - np.asarray(payload["vl_mean"], dtype=np.float32)) / np.asarray(payload["vl_std"], dtype=np.float32),
            (states - np.asarray(payload["state_mean"], dtype=np.float32)) / np.asarray(payload["state_std"], dtype=np.float32),
        ],
        axis=1,
    )
    param_targets = (params - np.asarray(payload["param_mean"], dtype=np.float32)) / np.asarray(payload["param_std"], dtype=np.float32)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    head = MiniCPMSkillParamHead(
        input_dim=int(payload["input_dim"]),
        skill_count=int(payload["skill_count"]),
        param_dim=int(payload["param_dim"]),
    ).to(device)
    head.load_state_dict(payload["head"])
    head.eval()

    metrics = evaluate_head_arrays(
        head,
        torch.tensor(features, dtype=torch.float32, device=device),
        torch.tensor(skill_ids, dtype=torch.long, device=device),
        torch.tensor(param_targets, dtype=torch.float32, device=device),
        np.asarray(payload["param_mean"], dtype=np.float32),
        np.asarray(payload["param_std"], dtype=np.float32),
        device=device,
    )
    return {
        "checkpoint": str(checkpoint),
        "manifests": [str(path) for path in manifests],
        "rows": len(samples),
        "cache_hits": cache_hits,
        "device": str(device),
        "policy_kind": payload.get("policy_kind"),
        "skill_names": payload.get("skill_names"),
        "param_names": payload.get("param_names"),
        "metrics": metrics,
    }


def load_minicpm_for_checkpoint(payload: dict[str, Any], checkpoint: Path) -> tuple[Any, Any]:
    if int(payload.get("lora_rank") or 0) <= 0:
        return load_minicpm(str(payload["model_id"]))

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForImageTextToText, AutoProcessor
    except ImportError as exc:
        raise RuntimeError("Install transformers and peft before evaluating a LoRA skill-param router") from exc

    model_id = str(payload["model_id"])
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    base = AutoModelForImageTextToText.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    base.to(device)
    adapter_dir = checkpoint.parent / str(payload.get("lora_adapter_dir") or "lora_adapter")
    model = PeftModel.from_pretrained(base, adapter_dir)
    model.to(device)
    model.eval()
    return processor, model


def make_eval_cache_key(sample: Any, payload: dict[str, Any], checkpoint: Path) -> str:
    base_key = make_skill_param_cache_key(
        sample,
        str(payload["model_id"]),
        str(payload.get("downsample_mode", "16x")),
        int(payload.get("max_slice_nums", 9)),
    )
    if int(payload.get("lora_rank") or 0) <= 0:
        return base_key
    return "|".join(
        [
            base_key,
            str(payload.get("policy_kind") or "lora"),
            str(payload.get("lora_rank") or ""),
            str((checkpoint.parent / str(payload.get("lora_adapter_dir") or "lora_adapter")).resolve()),
        ]
    )


def parse_path_list(values: list[Path] | None) -> list[Path]:
    return [Path(value) for value in values or []]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--limit-rows", type=int, default=512)
    parser.add_argument("--embedding-cache", type=Path)
    args = parser.parse_args()
    result = eval_minicpm_vla_skill_param_head(
        args.checkpoint,
        parse_path_list(args.manifest),
        limit_rows=args.limit_rows,
        embedding_cache=args.embedding_cache,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
