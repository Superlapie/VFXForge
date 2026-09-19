"""Safe identifier resolution and res:// path validation."""

from __future__ import annotations

import re
from pathlib import Path

from ..model import is_stable_id


RES_PATH = re.compile(r"^res://[A-Za-z0-9_./-]+$")


def assert_safe_id(identifier: str, label: str) -> None:
    if not is_stable_id(identifier):
        raise ValueError(f"Invalid {label} '{identifier}'. Use a stable identifier such as impact_fire.")


def resolve_contained_file(root: Path, identifier: str, suffix: str = ".json") -> Path:
    assert_safe_id(identifier, "identifier")
    candidate = (root / f"{identifier}{suffix}").resolve()
    root_resolved = root.resolve()
    if candidate.parent != root_resolved and not str(candidate).startswith(str(root_resolved) + "/"):
        raise ValueError(f"Identifier '{identifier}' resolves outside managed root.")
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"Missing file for identifier '{identifier}' under {root_resolved}")
    return candidate


def validate_resource_path(path: str, field: str) -> None:
    if not isinstance(path, str) or not path:
        raise ValueError(f"{field} must be a non-empty res:// path.")
    if ".." in path or "\n" in path or "\r" in path or '"' in path:
        raise ValueError(f"{field} contains invalid path characters.")
    if not path.startswith("res://"):
        raise ValueError(f"{field} must start with res://.")
    if not RES_PATH.fullmatch(path):
        raise ValueError(f"{field} has invalid res:// path format.")
