"""Shared child-effect reference resolution for validation and export."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .model import is_generated_effect_document, read_document


EXPORT_EFFECT_NAME = re.compile(r"^.+_[0-9a-f]{8}(?:_\d+)?\.vfx\.json$")


@dataclass(frozen=True)
class EffectResolveResult:
    path: Path | None = None
    error_code: str | None = None
    error_message: str | None = None
    matches: tuple[Path, ...] = ()


def _contained_resolved(project_root: Path, candidate: Path) -> Path | None:
    resolved = candidate.resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError:
        return None
    return resolved


def is_source_effect_document(
    path: Path,
    project_root: Path,
    *,
    document: dict | None = None,
) -> bool:
    """Return whether a document may participate in stable-ID source discovery."""
    contained = _contained_resolved(project_root, path)
    if contained is None:
        return False
    relative = contained.relative_to(project_root.resolve())
    for part in relative.parts[:-1]:
        if part.startswith(".") and "export-staging" in part:
            return False
    if EXPORT_EFFECT_NAME.match(relative.name):
        return False
    payload = document
    if payload is None:
        try:
            payload = read_document(contained)
        except Exception:
            return True
    if is_generated_effect_document(payload):
        return False
    return True


def is_path_like_effect_reference(reference: str) -> bool:
    if reference.startswith("res://"):
        return True
    if "/" in reference:
        return True
    if reference.endswith(".json") or reference.endswith(".vfx.json"):
        return True
    return False


def reference_escapes_project(reference: str, *, document_dir: Path, project_root: Path) -> bool:
    if not is_path_like_effect_reference(reference):
        return False
    if reference.startswith("res://"):
        raw = project_root / reference.removeprefix("res://")
    else:
        raw = document_dir / reference
    return _contained_resolved(project_root, raw) is None


def _resolve_path_candidate(reference: str, *, document_dir: Path, project_root: Path) -> EffectResolveResult:
    if reference.startswith("res://"):
        raw = project_root / reference.removeprefix("res://")
    else:
        raw = document_dir / reference
    contained = _contained_resolved(project_root, raw)
    if contained is None:
        return EffectResolveResult(
            error_code="EFFECT_OUTSIDE_PROJECT",
            error_message=f"Child effect reference escapes the project: {reference}",
        )
    if contained.is_file():
        return EffectResolveResult(path=contained)
    if contained.suffix == "":
        with_suffix = contained.with_suffix(".vfx.json")
        contained_suffix = _contained_resolved(project_root, with_suffix)
        if contained_suffix is not None and contained_suffix.is_file():
            return EffectResolveResult(path=contained_suffix)
    return EffectResolveResult()


def _resolve_stable_id(reference: str, project_root: Path) -> EffectResolveResult:
    matches: list[Path] = []
    for path in sorted(project_root.rglob("*.vfx.json")):
        contained = _contained_resolved(project_root, path)
        if contained is None:
            continue
        try:
            document = read_document(contained)
        except Exception:
            continue
        if is_generated_effect_document(document):
            continue
        if not is_source_effect_document(path, project_root, document=document):
            continue
        if document.get("id") == reference:
            matches.append(contained)
    if len(matches) > 1:
        rendered = ", ".join(str(item.relative_to(project_root)) for item in matches)
        return EffectResolveResult(
            error_code="AMBIGUOUS_EFFECT_ID",
            error_message=f"Stable effect ID '{reference}' matches multiple documents: {rendered}",
            matches=tuple(matches),
        )
    if len(matches) == 1:
        return EffectResolveResult(path=matches[0])
    return EffectResolveResult()


def resolve_effect(
    reference: str,
    *,
    document_dir: Path,
    project_root: Path,
) -> EffectResolveResult:
    project = project_root.resolve()
    if is_path_like_effect_reference(reference):
        return _resolve_path_candidate(reference, document_dir=document_dir.resolve(), project_root=project)
    return _resolve_stable_id(reference, project)


def resolve_effect_path(
    reference: str,
    *,
    document_dir: Path,
    project_root: Path,
) -> Path | None:
    return resolve_effect(reference, document_dir=document_dir, project_root=project_root).path
