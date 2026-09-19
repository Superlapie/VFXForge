"""Multi-time deterministic preview suite."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from ..renderer import render_preview


def sample_times(document: dict[str, Any]) -> list[float]:
    duration = float(document.get("duration", 1.0))
    if duration <= 0:
        duration = 1.0
    samples = {0.0, min(0.05, duration * 0.05), duration * 0.25, duration * 0.5, duration * 0.75, max(0.0, duration - 0.05)}
    timeline = document.get("timeline", {})
    if isinstance(timeline, dict):
        for event in timeline.get("events", []):
            if isinstance(event, dict) and isinstance(event.get("time"), (int, float)):
                samples.add(float(event["time"]))
    for layer in document.get("layers", []):
        if isinstance(layer, dict) and layer.get("type") == "event_marker" and isinstance(layer.get("start"), (int, float)):
            samples.add(float(layer["start"]))
    ordered = sorted(samples)
    return [min(max(0.0, value), duration) for value in ordered]


def _build_contact_sheet(files: list[dict[str, Any]], output_dir: Path) -> str | None:
    images: list[Image.Image] = []
    for item in files:
        path = Path(str(item.get("path", "")))
        if path.exists():
            images.append(Image.open(path).convert("RGBA"))
    if not images:
        return None
    cell_width = max(image.width for image in images)
    cell_height = max(image.height for image in images)
    columns = min(4, len(images))
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGBA", (cell_width * columns, cell_height * rows), (16, 16, 20, 255))
    for index, image in enumerate(images):
        row = index // columns
        column = index % columns
        sheet.paste(image, (column * cell_width, row * cell_height))
    contact_path = output_dir / "contact_sheet.png"
    sheet.save(contact_path)
    return str(contact_path)


def render_preview_suite(
    document: dict[str, Any],
    output_dir: Path,
    cameras: list[str] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cameras = cameras or ["mmo"]
    files: list[dict[str, Any]] = []
    for camera in cameras:
        for index, time in enumerate(sample_times(document)):
            output = output_dir / f"{camera}_{index:02d}_{time:.3f}.png"
            preview = render_preview(document, output, time, camera, 768, 512, "dark", True)
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            files.append({"camera": camera, "time": time, "path": str(output), "sha256": digest, "preview": preview})
    contact_sheet = _build_contact_sheet(files, output_dir)
    manifest = {
        "sample_count": len(files),
        "cameras": cameras,
        "files": files,
        "contact_sheet": contact_sheet,
    }
    manifest_path = output_dir / "preview_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"manifest": str(manifest_path), "files": files, "contact_sheet": contact_sheet}
