"""Multi-time deterministic preview suite."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

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
    ordered = sorted(samples)
    return [min(max(0.0, value), duration) for value in ordered]


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
    contact_lines = [f"{item['camera']}@{item['time']:.3f}" for item in files]
    manifest = {
        "sample_count": len(files),
        "cameras": cameras,
        "files": files,
        "contact_sheet_note": " | ".join(contact_lines),
    }
    manifest_path = output_dir / "preview_manifest.json"
    import json
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"manifest": str(manifest_path), "files": files, "contact_sheet_note": manifest["contact_sheet_note"]}
