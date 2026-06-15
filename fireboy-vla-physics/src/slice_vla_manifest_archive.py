from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path
from typing import Any

from PIL import Image


def slice_vla_manifest_archive(
    manifest: Path,
    out_dir: Path,
    limit_rows: int = 512,
    task_filter: list[str] | None = None,
    image_size: int = 320,
    archive_name: str = "fireboy-vla-slice.tgz",
    sample_mode: str = "prefix",
) -> dict[str, Any]:
    allowed = set(task_filter or [])
    available: list[tuple[int, dict[str, Any]]] = []
    with manifest.open("r", encoding="utf-8") as handle:
        for row_index, line in enumerate(handle):
            if not line.strip():
                continue
            row = json.loads(line)
            task = str(row.get("task", "unknown"))
            if allowed and task not in allowed:
                continue
            image_path = Path(str(row.get("image_path", "")))
            if not image_path.exists():
                continue
            available.append((row_index, row))
    if not available:
        raise RuntimeError(f"No usable rows found in {manifest}")
    rows = select_rows(available, limit_rows=limit_rows, sample_mode=sample_mode)
    counts: dict[str, int] = {}
    for row in rows:
        task = str(row.get("task", "unknown"))
        counts[task] = counts.get(task, 0) + 1

    out_dir.mkdir(parents=True, exist_ok=True)
    dataset_dir = out_dir / "datasets" / "fireboy_vla_slice"
    image_root = dataset_dir / "images"
    manifest_dir = out_dir / "vla_manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    image_root.mkdir(parents=True, exist_ok=True)
    out_manifest = manifest_dir / "fireboy_vla_slice.jsonl"

    rewritten_rows = []
    for index, row in enumerate(rows):
        src = Path(str(row["image_path"]))
        dst = image_root / f"{index:06d}.jpg"
        resize_image(src, dst, image_size=image_size)
        row = dict(row)
        row["source_image_path"] = str(src)
        row["image_path"] = str(dst.resolve())
        rewritten_rows.append(row)

    with out_manifest.open("w", encoding="utf-8") as handle:
        for row in rewritten_rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    summary = {
        "source_manifest": str(manifest),
        "manifest": str(out_manifest.resolve()),
        "dataset": str(dataset_dir.resolve()),
        "rows": len(rewritten_rows),
        "counts": counts,
        "image_size": image_size,
        "sample_mode": sample_mode,
    }
    summary_path = manifest_dir / "fireboy_vla_slice.summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    archive_path = out_dir / archive_name
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(dataset_dir, arcname="datasets/fireboy_vla_slice")
        tar.add(out_manifest, arcname="vla_manifests/fireboy_vla_slice.jsonl")
        tar.add(summary_path, arcname="vla_manifests/fireboy_vla_slice.summary.json")

    summary["archive"] = str(archive_path.resolve())
    return summary


def select_rows(available: list[tuple[int, dict[str, Any]]], limit_rows: int, sample_mode: str) -> list[dict[str, Any]]:
    if sample_mode == "prefix":
        return [dict(row) for _, row in available[:limit_rows]]
    if sample_mode != "uniform":
        raise ValueError(f"Unknown sample mode: {sample_mode}")

    by_task: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for item in available:
        by_task.setdefault(str(item[1].get("task", "unknown")), []).append(item)
    tasks = sorted(by_task)
    base_quota = max(1, limit_rows // max(1, len(tasks)))
    quotas = {task: base_quota for task in tasks}
    for task in tasks[: max(0, limit_rows - base_quota * len(tasks))]:
        quotas[task] += 1

    selected: list[tuple[int, dict[str, Any]]] = []
    for task in tasks:
        selected.extend(evenly_sample(by_task[task], min(quotas[task], len(by_task[task]))))

    if len(selected) < limit_rows:
        seen = {index for index, _ in selected}
        for item in available:
            if item[0] not in seen:
                selected.append(item)
                seen.add(item[0])
                if len(selected) >= limit_rows:
                    break
    selected = sorted(selected[:limit_rows], key=lambda item: item[0])
    return [dict(row) for _, row in selected]


def evenly_sample(items: list[tuple[int, dict[str, Any]]], quota: int) -> list[tuple[int, dict[str, Any]]]:
    if quota <= 0:
        return []
    if quota >= len(items):
        return list(items)
    if quota == 1:
        return [items[len(items) // 2]]
    picked: list[tuple[int, dict[str, Any]]] = []
    seen: set[int] = set()
    span = len(items) - 1
    for pick_index in range(quota):
        item_index = round(pick_index * span / (quota - 1))
        while item_index in seen and item_index + 1 < len(items):
            item_index += 1
        while item_index in seen and item_index > 0:
            item_index -= 1
        if item_index not in seen:
            picked.append(items[item_index])
            seen.add(item_index)
    if len(picked) < quota:
        for item_index, item in enumerate(items):
            if item_index not in seen:
                picked.append(item)
                seen.add(item_index)
                if len(picked) >= quota:
                    break
    return picked[:quota]


def resize_image(src: Path, dst: Path, image_size: int) -> None:
    with Image.open(src) as image:
        image = image.convert("RGB")
        image.thumbnail((image_size, image_size))
        canvas = Image.new("RGB", (image_size, image_size), (246, 244, 236))
        left = (image_size - image.width) // 2
        top = (image_size - image.height) // 2
        canvas.paste(image, (left, top))
        dst.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(dst, quality=84)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--limit-rows", type=int, default=512)
    parser.add_argument("--task-filter", action="append", default=[])
    parser.add_argument("--image-size", type=int, default=320)
    parser.add_argument("--archive-name", default="fireboy-vla-slice.tgz")
    parser.add_argument("--sample-mode", choices=["prefix", "uniform"], default="prefix")
    args = parser.parse_args()
    result = slice_vla_manifest_archive(
        args.manifest,
        args.out_dir,
        limit_rows=args.limit_rows,
        task_filter=args.task_filter or None,
        image_size=args.image_size,
        archive_name=args.archive_name,
        sample_mode=args.sample_mode,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
