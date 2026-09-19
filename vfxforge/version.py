"""Build and schema version information."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

TOOL_NAME = "VFX Forge"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = 1
COMPILER_CONTRACT_VERSION = 2
GODOT_TARGET = "4.x"


def tool_revision() -> str:
    configured = os.environ.get("VFXFORGE_REVISION", "").strip()
    if configured:
        return configured
    marker = Path(__file__).with_name("_revision.txt")
    if marker.is_file():
        value = marker.read_text(encoding="utf-8").strip()
        if value:
            return value
    try:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def runtime_file_hashes() -> dict[str, str]:
    from .resources import godot_runtime_dir

    hashes: dict[str, str] = {}
    try:
        runtime = godot_runtime_dir()
    except FileNotFoundError:
        return hashes
    for name in ("vfx_runtime.gd", "vfx_trail.gd"):
        path = runtime / name
        if path.is_file():
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def generator_identity(
    *,
    tool_version: str | None = None,
    revision: str | None = None,
    compiler_contract_version: int | None = None,
    runtime_contract_version: int | None = None,
) -> dict[str, object]:
    if runtime_contract_version is None:
        from .service.runtime_conformance import RUNTIME_CONTRACT_VERSION

        runtime_contract_version = RUNTIME_CONTRACT_VERSION
    return {
        "tool_version": tool_version or TOOL_VERSION,
        "tool_revision": revision if revision is not None else tool_revision(),
        "compiler_contract_version": compiler_contract_version if compiler_contract_version is not None else COMPILER_CONTRACT_VERSION,
        "runtime_contract_version": runtime_contract_version,
        "runtime_sha256": runtime_file_hashes(),
    }
