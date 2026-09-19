"""Resolve packaged service data paths for editable and wheel installs."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path


PKG_ROOT = Path(__file__).resolve().parent


def _has_service_data(root: Path) -> bool:
    return (root / "recipes").is_dir() and (root / "policies").is_dir()


def _share_candidates() -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        key = str(path)
        if key in seen:
            return
        seen.add(key)
        candidates.append(path)

    for prefix in (Path(sys.prefix), Path(sys.base_prefix)):
        add(prefix / "share" / "vfxforge")
    add(PKG_ROOT.parent / "share" / "vfxforge")
    for entry in sys.path:
        if not entry:
            continue
        add(Path(entry) / "share" / "vfxforge")
    return candidates


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
        if _has_service_data(root):
            return root
    raise FileNotFoundError("VFX Forge service data was not found in the installed package or source checkout.")


def _share_root() -> Path | None:
    for candidate in _share_candidates():
        if _has_service_data(candidate):
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


def host_smoke_dir() -> Path | None:
    candidates = [
        install_root() / "godot" / "host_smoke",
        PKG_ROOT.parent / "godot" / "host_smoke",
        PKG_ROOT.parent / "tests" / "fixtures" / "host_library",
    ]
    share = _share_root()
    if share is not None:
        candidates.insert(0, share / "godot" / "host_smoke")
    for candidate in candidates:
        if (candidate / "host_smoke.gd").is_file() and (candidate / "project.godot").is_file():
            return candidate
    return None
