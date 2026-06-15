from __future__ import annotations

import argparse
import json
import shutil
import tarfile
from pathlib import Path
from typing import Any

from policy_registry import DEFAULT_REGISTRY_PATH, REPO_ROOT, load_policy_registry, resolve_repo_path
from validate_policy_registry import validate_policy_registry


BUNDLE_KEYS = (
    "proof_mp4",
    "proof_gif",
    "local_demo_mp4",
    "eval_path",
    "train_path",
    "report_path",
    "manifest_summary_path",
    "local_manifest_summary_path",
)
CHECKPOINT_KEYS = (
    "policy_path",
    "checkpoint_path",
    "local_checkpoint_path",
    "seed_checkpoint_path",
    "adapter_path",
    "local_fallback_policy_path",
    "manifest_path",
    "local_manifest_path",
    "artifact_archive",
)


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)


def iter_entries(registry: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    entries: list[tuple[str, str, dict[str, Any]]] = []
    for section_name in ("body_proofs", "skills", "vla_models", "failed_experiments"):
        section = registry.get(section_name, {})
        if not isinstance(section, dict):
            continue
        for entry_name, entry in section.items():
            if not isinstance(entry, dict) or entry.get("alias_of"):
                continue
            entries.append((section_name, entry_name, entry))
    return entries


def copy_artifact(source: Path, destination_dir: Path, prefix: str) -> str:
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / f"{safe_name(prefix)}__{safe_name(source.name)}"
    shutil.copy2(source, target)
    return target.relative_to(destination_dir.parent).as_posix()


def build_policy_proof_bundle(
    out_dir: Path,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    *,
    make_archive: bool = True,
) -> dict[str, Any]:
    validation = validate_policy_registry(registry_path)
    if not validation["ok"]:
        raise RuntimeError(f"Policy registry is not valid: {validation}")

    registry = load_policy_registry(registry_path)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    copied: list[dict[str, Any]] = []
    checkpoint_refs: list[dict[str, str]] = []

    for section_name, entry_name, entry in iter_entries(registry):
        prefix = f"{section_name}_{entry_name}"
        for key in BUNDLE_KEYS:
            path = resolve_repo_path(entry.get(key))
            if path is None or not path.exists() or not path.is_file():
                continue
            subdir = "media" if path.suffix.lower() in {".mp4", ".gif", ".jpg", ".jpeg", ".png"} else "json"
            bundle_path = copy_artifact(path, out_dir / subdir, f"{prefix}_{key}")
            copied.append({
                "section": section_name,
                "entry": entry_name,
                "key": key,
                "source": path.relative_to(REPO_ROOT).as_posix(),
                "bundle_path": bundle_path,
            })
        for key in CHECKPOINT_KEYS:
            path = resolve_repo_path(entry.get(key))
            if path is None or not path.exists():
                continue
            checkpoint_refs.append({
                "section": section_name,
                "entry": entry_name,
                "key": key,
                "source": path.relative_to(REPO_ROOT).as_posix(),
            })

    screenshot_dir = REPO_ROOT / "fireboy-vla-physics" / "build" / "proof-gallery-screenshots"
    if screenshot_dir.exists():
        for screenshot in sorted(screenshot_dir.glob("*.png")):
            bundle_path = copy_artifact(screenshot, out_dir / "screenshots", f"screenshot_{screenshot.stem}")
            copied.append({
                "section": "screenshots",
                "entry": screenshot.stem,
                "key": "screenshot",
                "source": screenshot.relative_to(REPO_ROOT).as_posix(),
                "bundle_path": bundle_path,
            })

    final_proof_dir = REPO_ROOT / "Fireboy-training-policy-vla" / "proofs"
    if final_proof_dir.exists():
        for proof in sorted(final_proof_dir.glob("*")):
            if proof.suffix.lower() not in {".json", ".png"} or not proof.is_file():
                continue
            bundle_path = copy_artifact(proof, out_dir / "proofs", f"final_{proof.stem}")
            copied.append({
                "section": "final_proofs",
                "entry": proof.stem,
                "key": "proof",
                "source": proof.relative_to(REPO_ROOT).as_posix(),
                "bundle_path": bundle_path,
            })

    skill_param_dir = REPO_ROOT / "Fireboy-training-policy-vla" / "vla-rollouts" / "vla_skill_params"
    if skill_param_dir.exists():
        for manifest_artifact in sorted(skill_param_dir.glob("fireboy_vla_skill_params_*")):
            if manifest_artifact.suffix not in {".jsonl", ".json"}:
                continue
            bundle_path = copy_artifact(manifest_artifact, out_dir / "training", f"skill_param_{manifest_artifact.stem}")
            copied.append({
                "section": "training_manifests",
                "entry": manifest_artifact.stem,
                "key": "skill_param_manifest",
                "source": manifest_artifact.relative_to(REPO_ROOT).as_posix(),
                "bundle_path": bundle_path,
            })

    summary = {
        "registry": registry_path.relative_to(REPO_ROOT).as_posix(),
        "fireboy_glb": registry.get("fireboy_glb"),
        "validation": validation,
        "copied_count": len(copied),
        "checkpoint_reference_count": len(checkpoint_refs),
        "copied": copied,
        "checkpoint_refs": checkpoint_refs,
        "active_skills": {
            name: {
                "task": entry.get("task"),
                "lane": entry.get("lane"),
                "status": entry.get("status"),
                "successes": entry.get("successes"),
                "episodes": entry.get("episodes"),
                "success_rate": entry.get("success_rate"),
            }
            for name, entry in registry.get("skills", {}).items()
            if isinstance(entry, dict) and not entry.get("alias_of")
        },
        "vla_models": {
            name: {
                "task": entry.get("task"),
                "lane": entry.get("lane"),
                "runtime": entry.get("runtime"),
                "status": entry.get("status"),
                "successes": entry.get("successes"),
                "episodes": entry.get("episodes"),
                "success_rate": entry.get("success_rate"),
            }
            for name, entry in registry.get("vla_models", {}).items()
            if isinstance(entry, dict)
        },
        "failed_experiments": {
            name: {
                "successes": entry.get("successes"),
                "episodes": entry.get("episodes"),
                "reason": entry.get("reason"),
            }
            for name, entry in registry.get("failed_experiments", {}).items()
            if isinstance(entry, dict)
        },
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "README.md").write_text(bundle_readme(summary), encoding="utf-8")

    archive_path = None
    if make_archive:
        archive_path = out_dir.with_suffix(".tgz")
        if archive_path.exists():
            archive_path.unlink()
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(out_dir, arcname=out_dir.name)

    return {
        "out_dir": str(out_dir),
        "archive": str(archive_path) if archive_path else None,
        "copied_count": len(copied),
        "checkpoint_reference_count": len(checkpoint_refs),
        "validation": validation,
    }


def bundle_readme(summary: dict[str, Any]) -> str:
    lines = [
        "# Fire Boy Policy Proof Bundle",
        "",
        f"Registry: `{summary['registry']}`",
        f"Fire Boy GLB: `{summary.get('fireboy_glb')}`",
        "",
        "## Active Skills",
        "",
    ]
    for name, entry in summary["active_skills"].items():
        lines.append(
            f"- `{name}`: {entry.get('lane')} / {entry.get('task')} / "
            f"{entry.get('successes')}/{entry.get('episodes')} ({entry.get('success_rate')})"
        )
    lines.extend(["", "## VLA Router Models", ""])
    for name, entry in summary["vla_models"].items():
        lines.append(
            f"- `{name}`: {entry.get('lane')} / {entry.get('runtime')} / "
            f"{entry.get('successes')}/{entry.get('episodes')} ({entry.get('success_rate')})"
        )
    lines.extend(["", "## Failed Direct VLA Experiments", ""])
    for name, entry in summary["failed_experiments"].items():
        lines.append(f"- `{name}`: {entry.get('successes')}/{entry.get('episodes')} - {entry.get('reason')}")
    lines.extend([
        "",
        "## Notes",
        "",
        "This bundle copies proof media, eval JSON, reports, and screenshots.",
        "Large checkpoints and LoRA adapter folders are referenced in `summary.json` rather than duplicated here.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "fireboy-vla-physics" / "build" / "fireboy-policy-proof-bundle")
    parser.add_argument("--no-archive", action="store_true")
    args = parser.parse_args()
    result = build_policy_proof_bundle(args.out_dir, make_archive=not args.no_archive)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
