"""Resolve packaged service data paths for editable and wheel installs."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path


PKG_ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def install_root() -> Path:
    candidates = [
        PKG_ROOT / "_install",
        PKG_ROOT.parent,
    ]
    share = _share_root()
    if share is not None:
        candidates.insert(0, share)
    for root in candidates:
        if (root / "recipes").is_dir() and (root / "policies").is_dir():
            return root
    raise FileNotFoundError("VFX Forge service data was not found in the installed package or source checkout.")


def _share_root() -> Path | None:
    for prefix in (Path(sys.prefix), Path(sys.base_prefix)):
        candidate = prefix / "share" / "vfxforge"
        if (candidate / "recipes").is_dir():
            return candidate
    return None


def recipes_dir() -> Path:
    return install_root() / "recipes"


def policies_dir() -> Path:
    return install_root() / "policies"


def schema_dir() -> Path:
    return install_root() / "schema"


def godot_runtime_dir() -> Path:
    runtime = install_root() / "godot" / "runtime"
    if runtime.is_dir():
        return runtime
    fallback = PKG_ROOT.parent / "godot" / "runtime"
    if fallback.is_dir():
        return fallback
    raise FileNotFoundError("Godot runtime data was not found.")
