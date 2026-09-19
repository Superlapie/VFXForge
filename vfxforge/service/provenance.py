"""Provenance and reproduction metadata."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..version import SCHEMA_VERSION, TOOL_VERSION


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_provenance(
    normalized_request: dict[str, Any],
    request_digest: str,
    recipe: dict[str, Any],
    policy: dict[str, Any],
    seed: int,
    corrections: list[dict[str, Any]],
    validation: dict[str, Any],
    previews: dict[str, Any],
    export_result: dict[str, Any] | None,
) -> dict[str, Any]:
    reproduction = {
        "command": (
            "vfxforge forge --request request.json --policy "
            f"{policy.get('policy_id', 'default')} --workspace . --json"
        ),
    }
    hashes: dict[str, Any] = {"request": request_digest}
    if export_result:
        manifest_path = Path(export_result.get("manifest", ""))
        if manifest_path.exists():
            hashes["export_manifest"] = file_sha256(manifest_path)
    return {
        "normalized_request": normalized_request,
        "request_hash": request_digest,
        "recipe_id": recipe.get("recipe_id"),
        "recipe_version": recipe.get("recipe_version", 1),
        "policy_id": policy.get("policy_id"),
        "policy_version": policy.get("policy_version", 1),
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "corrections": corrections,
        "validation_summary": {
            "valid": validation.get("valid"),
            "error_count": len(validation.get("errors", [])),
            "warning_count": len(validation.get("warnings", [])),
        },
        "previews": previews,
        "export": export_result or {},
        "reproduction": reproduction,
        "hashes": hashes,
    }


def write_manifest(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)
