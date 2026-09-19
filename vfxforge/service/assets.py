"""Deterministic asset identity for generation digests and host catalogs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable


def collect_asset_references(document: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        if isinstance(value, str) and value and value not in seen:
            seen.add(value)
            refs.append(value)

    dependencies = document.get("dependencies", {})
    if isinstance(dependencies, dict):
        for key in ("textures", "meshes", "effects"):
            for reference in dependencies.get(key, []):
                add(reference)
    for layer in document.get("layers", []):
        if not isinstance(layer, dict):
            continue
        for container in (layer.get("properties", {}), layer.get("material", {})):
            if not isinstance(container, dict):
                continue
            add(container.get("texture"))
            add(container.get("mesh_asset"))
            add(container.get("effect_id"))
    return refs


def resolve_asset_path(
    reference: str,
    *,
    asset_root: str | Path | None = None,
    catalog: dict[str, str] | None = None,
) -> Path | None:
    if not reference:
        return None
    if catalog and reference in catalog:
        mapped = Path(catalog[reference])
        if mapped.is_file():
            return mapped.resolve()
        if asset_root is not None:
            nested = (Path(asset_root) / mapped).resolve()
            if nested.is_file():
                return nested
        return None
    if asset_root is None:
        return None
    root = Path(asset_root).resolve()
    relative = reference.removeprefix("res://")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None


def hash_assets(
    document: dict[str, Any],
    *,
    asset_root: str | Path | None = None,
    catalog: dict[str, str] | None = None,
    extra_documents: Iterable[dict[str, Any]] = (),
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    documents = [document, *extra_documents]
    for item in documents:
        if not isinstance(item, dict):
            continue
        for reference in collect_asset_references(item):
            path = resolve_asset_path(reference, asset_root=asset_root, catalog=catalog)
            if path is None or not path.is_file():
                continue
            hashes[reference.replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(hashes.items()))
