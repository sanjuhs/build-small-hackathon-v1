from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from train_minicpm_vla_action_head import (
    MODEL_ID,
    MiniCPMStateActionHead,
    apply_minicpm_chat_template,
    build_minicpm_action_head,
    load_manifest_samples,
    make_vla_prompt,
)


def train_minicpm_vla_lora_action_head(
    manifest: Path,
    seed_checkpoint: Path,
    out_dir: Path,
    model_id: str = MODEL_ID,
    limit_rows: int = 512,
    max_steps: int = 500,
    task_filter: list[str] | None = None,
    lora_rank: int = 8,
    lora_alpha: int = 16,
    lora_dropout: float = 0.05,
    lr_lora: float = 1.0e-5,
    lr_head: float = 5.0e-5,
    freeze_state_head: bool = True,
    downsample_mode: str = "16x",
    max_slice_nums: int = 4,
    val_fraction: float = 0.10,
    seed: int = 11,
) -> dict[str, Any]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install torch before training MiniCPM-V LoRA action head") from exc

    payload = torch.load(seed_checkpoint, map_location="cpu")
    samples = load_manifest_samples(
        [manifest],
        limit_rows=limit_rows,
        task_filter=task_filter,
        state_mode=str(payload.get("state_mode", "clock")),
        include_stage_flags=bool(payload.get("include_stage_flags", True)),
    )
    if not samples:
        raise RuntimeError(f"No usable samples found in {manifest}")

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(samples))
    val_count = max(1, int(round(len(samples) * val_fraction))) if len(samples) > 8 else 1
    val_indices = set(int(i) for i in order[:val_count])
    train_indices = [i for i in range(len(samples)) if i not in val_indices]
    val_list = [i for i in range(len(samples)) if i in val_indices]
    if not train_indices:
        train_indices = list(range(len(samples)))
        val_list = train_indices[:1]

    import torch

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    processor, minicpm = load_minicpm_for_lora(model_id, lora_rank, lora_alpha, lora_dropout, device)

    head = build_minicpm_action_head(payload)
    head.load_state_dict(payload["head"])
    head.to(device)
    if freeze_state_head:
        freeze_named_prefix(head.model, "state_head")

    states = np.asarray([sample.state for sample in samples], dtype=np.float32)
    actions = np.asarray([sample.action_chunk for sample in samples], dtype=np.float32)
    state_mean = np.asarray(payload["state_mean"], dtype=np.float32)
    state_std = np.asarray(payload["state_std"], dtype=np.float32)
    vl_mean = np.asarray(payload["vl_mean"], dtype=np.float32)
    vl_std = np.asarray(payload["vl_std"], dtype=np.float32)
    action_mean = np.asarray(payload["action_mean"], dtype=np.float32)
    action_std = np.asarray(payload["action_std"], dtype=np.float32)
    targets = (actions - action_mean) / action_std
    states_norm = (states - state_mean) / state_std

    action_dim = int(payload["action_dim"])
    chunk_steps = int(payload["chunk_steps"])
    chunk_weights = np.linspace(1.45, 0.75, chunk_steps, dtype=np.float32)
    chunk_weights = np.repeat(chunk_weights, action_dim)
    weight = torch.tensor(chunk_weights, dtype=torch.float32, device=device).unsqueeze(0)

    lora_params = [param for param in minicpm.parameters() if param.requires_grad]
    head_params = [param for param in head.parameters() if param.requires_grad]
    opt = torch.optim.AdamW(
        [
            {"params": lora_params, "lr": lr_lora},
            {"params": head_params, "lr": lr_head},
        ],
        weight_decay=1.0e-4,
    )

    losses: list[float] = []
    val_losses: list[float] = []
    py_rng = np.random.default_rng(seed + 1)
    for step in range(max_steps):
        sample_index = int(py_rng.choice(train_indices))
        loss = compute_sample_loss(
            processor,
            minicpm,
            head,
            samples[sample_index],
            states_norm[sample_index],
            targets[sample_index],
            vl_mean,
            vl_std,
            weight,
            device,
            downsample_mode,
            max_slice_nums,
        )
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()

        if step % 25 == 0 or step == max_steps - 1:
            with torch.no_grad():
                val_loss = eval_small_validation(
                    processor,
                    minicpm,
                    head,
                    samples,
                    states_norm,
                    targets,
                    sorted(val_list)[: min(12, len(val_list))],
                    vl_mean,
                    vl_std,
                    weight,
                    device,
                    downsample_mode,
                    max_slice_nums,
                )
            losses.append(float(loss.detach().cpu()))
            val_losses.append(float(val_loss))
            print(
                json.dumps(
                    {
                        "step": step,
                        "loss": losses[-1],
                        "val_loss": val_losses[-1],
                        "train_rows": len(train_indices),
                        "val_rows": len(val_list),
                    }
                ),
                flush=True,
            )

    out_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir = out_dir / "lora_adapter"
    minicpm.save_pretrained(adapter_dir)
    checkpoint = out_dir / "minicpm_vla_lora_action_head.pt"
    save_payload = dict(payload)
    save_payload.update(
        {
            "head": {key: value.detach().cpu() for key, value in head.state_dict().items()},
            "model_id": model_id,
            "policy_kind": "minicpm_vla_lora_residual_action_head_v1",
            "lora_rank": int(lora_rank),
            "lora_alpha": int(lora_alpha),
            "lora_dropout": float(lora_dropout),
            "lora_adapter_dir": "lora_adapter",
            "seed_checkpoint": str(seed_checkpoint),
            "train_rows": len(train_indices),
            "val_rows": len(val_list),
            "rows": len(samples),
            "freeze_state_head": bool(freeze_state_head),
            "downsample_mode": downsample_mode,
            "max_slice_nums": int(max_slice_nums),
            "note": (
                "MiniCPM-V LoRA adapters trained from the proven residual-fusion "
                "frozen-encoder action head. The state controller branch was kept "
                "frozen by default to preserve closed-loop manipulation behavior."
            ),
        }
    )
    torch.save(save_payload, checkpoint)
    return {
        "checkpoint": str(checkpoint),
        "adapter_dir": str(adapter_dir),
        "seed_checkpoint": str(seed_checkpoint),
        "model_id": model_id,
        "rows": len(samples),
        "train_rows": len(train_indices),
        "val_rows": len(val_list),
        "device": str(device),
        "lora_rank": int(lora_rank),
        "lora_alpha": int(lora_alpha),
        "freeze_state_head": bool(freeze_state_head),
        "losses": losses[-10:],
        "val_losses": val_losses[-10:],
    }


def load_minicpm_for_lora(
    model_id: str,
    lora_rank: int,
    lora_alpha: int,
    lora_dropout: float,
    device: Any,
) -> tuple[Any, Any]:
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForImageTextToText, AutoProcessor

    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )
    model.to(device)
    if hasattr(model, "config"):
        model.config.use_cache = False
    if hasattr(model, "gradient_checkpointing_enable"):
        try:
            model.gradient_checkpointing_enable()
        except Exception:
            pass
    targets = find_lora_targets(model)
    config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
        target_modules=targets,
    )
    model = get_peft_model(model, config)
    model.train()
    return processor, model


def find_lora_targets(model: Any) -> list[str]:
    import torch

    preferred = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
    found: set[str] = set()
    for name, module in model.named_modules():
        if isinstance(module, torch.nn.Linear):
            leaf = name.rsplit(".", 1)[-1]
            if leaf in preferred:
                found.add(leaf)
    if found:
        return sorted(found)
    fallback: set[str] = set()
    for name, module in model.named_modules():
        if isinstance(module, torch.nn.Linear):
            fallback.add(name.rsplit(".", 1)[-1])
    return sorted(fallback)


def freeze_named_prefix(model: Any, prefix: str) -> None:
    for name, param in model.named_parameters():
        if name.startswith(prefix):
            param.requires_grad_(False)


def encode_minicpm_prompt_tensor(
    processor: Any,
    model: Any,
    image_path: Path,
    instruction: str,
    device: Any,
    downsample_mode: str,
    max_slice_nums: int,
) -> Any:
    import torch

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "url": str(image_path)},
                {"type": "text", "text": make_vla_prompt(instruction)},
            ],
        }
    ]
    try:
        inputs = apply_minicpm_chat_template(processor, messages, downsample_mode, max_slice_nums)
    except Exception:
        image = Image.open(image_path).convert("RGB")
        messages[0]["content"][0] = {"type": "image", "image": image}
        inputs = apply_minicpm_chat_template(processor, messages, downsample_mode, max_slice_nums)

    inputs = inputs.to(device)
    outputs = model(**inputs, output_hidden_states=True, return_dict=True)
    hidden_states = getattr(outputs, "hidden_states", None)
    if not hidden_states:
        raise RuntimeError("MiniCPM forward did not return hidden states.")
    last_hidden = hidden_states[-1].float()
    attention = inputs.get("attention_mask")
    if attention is not None:
        mask = attention.to(last_hidden.device).unsqueeze(-1).float()
        return (last_hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
    return last_hidden.mean(dim=1)


def compute_sample_loss(
    processor: Any,
    minicpm: Any,
    head: MiniCPMStateActionHead,
    sample: Any,
    state_norm: np.ndarray,
    target_norm: np.ndarray,
    vl_mean: np.ndarray,
    vl_std: np.ndarray,
    weight: Any,
    device: Any,
    downsample_mode: str,
    max_slice_nums: int,
) -> Any:
    import torch

    vl = encode_minicpm_prompt_tensor(
        processor,
        minicpm,
        sample.image_path,
        sample.instruction,
        device,
        downsample_mode,
        max_slice_nums,
    )
    vl = (vl - torch.tensor(vl_mean, dtype=torch.float32, device=device).unsqueeze(0)) / torch.tensor(
        vl_std, dtype=torch.float32, device=device
    ).unsqueeze(0)
    state = torch.tensor(state_norm, dtype=torch.float32, device=device).unsqueeze(0)
    target = torch.tensor(target_norm, dtype=torch.float32, device=device).unsqueeze(0)
    pred = head(torch.cat([vl, state], dim=-1))
    return ((pred - target) ** 2 * weight).mean()


def eval_small_validation(
    processor: Any,
    minicpm: Any,
    head: MiniCPMStateActionHead,
    samples: list[Any],
    states_norm: np.ndarray,
    targets: np.ndarray,
    indices: list[int],
    vl_mean: np.ndarray,
    vl_std: np.ndarray,
    weight: Any,
    device: Any,
    downsample_mode: str,
    max_slice_nums: int,
) -> float:
    if not indices:
        return 0.0
    losses = []
    for sample_index in indices:
        loss = compute_sample_loss(
            processor,
            minicpm,
            head,
            samples[sample_index],
            states_norm[sample_index],
            targets[sample_index],
            vl_mean,
            vl_std,
            weight,
            device,
            downsample_mode,
            max_slice_nums,
        )
        losses.append(float(loss.detach().cpu()))
    return float(np.mean(losses))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed-checkpoint", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--limit-rows", type=int, default=512)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--task-filter", action="append", default=[])
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--lr-lora", type=float, default=1.0e-5)
    parser.add_argument("--lr-head", type=float, default=5.0e-5)
    parser.add_argument("--freeze-state-head", action="store_true", default=True)
    parser.add_argument("--train-state-head", action="store_false", dest="freeze_state_head")
    parser.add_argument("--downsample-mode", default="16x")
    parser.add_argument("--max-slice-nums", type=int, default=4)
    parser.add_argument("--val-fraction", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    result = train_minicpm_vla_lora_action_head(
        manifest=args.manifest,
        seed_checkpoint=args.seed_checkpoint,
        out_dir=args.out_dir,
        model_id=args.model_id,
        limit_rows=args.limit_rows,
        max_steps=args.max_steps,
        task_filter=args.task_filter or None,
        lora_rank=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        lr_lora=args.lr_lora,
        lr_head=args.lr_head,
        freeze_state_head=args.freeze_state_head,
        downsample_mode=args.downsample_mode,
        max_slice_nums=args.max_slice_nums,
        val_fraction=args.val_fraction,
        seed=args.seed,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
