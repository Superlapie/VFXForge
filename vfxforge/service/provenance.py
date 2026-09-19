"""Provenance and reproduction metadata."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..version import SCHEMA_VERSION, TOOL_VERSION
from .policy import policy_ref
from .selector import recipe_ref


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_provenance(
    normalized_request: dict[str, Any],
    request_digest: str,
    generation_digest: str,
    recipe: dict[str, Any],
    policy: dict[str, Any],
    seed: int,
    corrections: list[dict[str, Any]],
    validation: dict[str, Any],
    previews: dict[str, Any],
    export_result: dict[str, Any] | None,
    *,
    export_mode: str = "standalone",
    resource_root: str | None = None,
    shared_runtime_path: str | None = None,
) -> dict[str, Any]:
    policy_id = str(policy.get("policy_id", "default"))
    command_parts = [
        "vfxforge forge",
        f"--request request.json --policy {policy_id}",
        f"--workspace . --export-mode {export_mode}",
    ]
    if resource_root:
        command_parts.append(f"--resource-root {resource_root}")
    if shared_runtime_path:
        command_parts.append(f"--shared-runtime-path {shared_runtime_path}")
    command_parts.append("--json")
    reproduction = {"command": " ".join(command_parts)}
    recipe_meta = recipe_ref(recipe)
    policy_meta = policy_ref(policy_id)
    hashes: dict[str, Any] = {
        "request": request_digest,
        "generation": generation_digest,
        "recipe": recipe_meta.get("sha256"),
        "policy": policy_meta.get("sha256"),
    }
    if export_result:
        manifest_path = Path(str(export_result.get("manifest", "")))
        if manifest_path.exists():
            hashes["export_manifest"] = file_sha256(manifest_path)
    preview_files = previews.get("files", []) if isinstance(previews, dict) else []
    if preview_files:
        hashes["previews"] = {str(item.get("path", index)): item.get("sha256") for index, item in enumerate(preview_files) if isinstance(item, dict)}
    contact_sheet = previews.get("contact_sheet") if isinstance(previews, dict) else None
    if contact_sheet:
        contact_path = Path(str(contact_sheet))
        if contact_path.exists():
            hashes["contact_sheet"] = file_sha256(contact_path)
    return {
        "normalized_request": normalized_request,
        "request_hash": request_digest,
        "generation_digest": generation_digest,
        "recipe": recipe_meta,
        "policy": policy_meta,
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "corrections": corrections,
        "validation_summary": {
            "valid": validation.get("valid"),
            "error_count": len(validation.get("errors", [])),
            "warning_count": len(validation.get("warnings", [])),
            "metrics": validation.get("metrics", {}),
        },
        "previews": previews,
        "export": export_result or {},
        "runtime_validation": (export_result or {}).get("smoke_test") or (export_result or {}).get("host_smoke_test") or {},
        "reproduction": reproduction,
        "hashes": hashes,
    }


def write_manifest(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)
