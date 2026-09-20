"""Document loading, migration, path mutation, and atomic persistence."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .errors import DocumentError
from .schema import COMMON_LAYER, LAYER_DEFAULTS, SCHEMA_VERSION, make_layer


ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,63}$")


def is_stable_id(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_PATTERN.fullmatch(value))


def _merge_defaults(value: Any, defaults: Any) -> Any:
    if isinstance(defaults, dict):
        result = deepcopy(value) if isinstance(value, dict) else {}
        for key, default in defaults.items():
            if key not in result:
                result[key] = deepcopy(default)
            elif isinstance(default, dict):
                result[key] = _merge_defaults(result[key], default)
        return result
    return deepcopy(value) if value is not None else deepcopy(defaults)


def migrate_document(raw: Any) -> dict[str, Any]:
    """Migrate known historical forms and normalize missing optional fields.

    Migration never invents a missing required identity. Validation reports that
    condition to the caller, which keeps malformed files inspectable instead of
    turning a typo into a new project.
    """
    if not isinstance(raw, dict):
        raise DocumentError("The root value must be a JSON object.", "INVALID_ROOT")
    version = raw.get("schema_version", 0)
    if not isinstance(version, int) or isinstance(version, bool):
        raise DocumentError("schema_version must be an integer.", "INVALID_SCHEMA_VERSION", "schema_version")
    if version > SCHEMA_VERSION:
        raise DocumentError(
            f"Document schema {version} is newer than this tool supports ({SCHEMA_VERSION}).",
            "FUTURE_SCHEMA",
            "schema_version",
        )
    document = deepcopy(raw)
    if version == 0:
        # Early/internal prototypes used 'effects' for the layer list and had no
        # explicit loop or seed fields. Keeping this migration tiny makes old
        # fixtures useful without accepting ambiguous shapes indefinitely.
        if "layers" not in document and isinstance(document.get("effects"), list):
            document["layers"] = document.pop("effects")
        document.setdefault("loop", False)
        document.setdefault("seed", 12345)
        document["schema_version"] = 1
    document.setdefault("metadata", {})
    document.setdefault("tags", [])
    document.setdefault("layers", [])
    document.setdefault("dependencies", {})
    document["dependencies"] = _merge_defaults(document["dependencies"], {"textures": [], "meshes": [], "effects": []})
    document.setdefault("timeline", {"events": [], "snap": 0.05})
    document["timeline"] = _merge_defaults(document["timeline"], {"events": [], "snap": 0.05})
    document.setdefault("camera_presets", {})
    document.setdefault("budgets", {"profile": "Medium", "custom": {}})
    document["budgets"] = _merge_defaults(document["budgets"], {"profile": "Medium", "custom": {}})
    document.setdefault("export", {})
    document["export"] = _merge_defaults(
        document["export"],
        {
            "godot_version": "4.x",
            "folder_name": document.get("id", "effect"),
            "include_metadata": True,
            "embed_document": True,
            "copy_textures": True,
            "copy_meshes": True,
        },
    )
    normalized_layers: list[Any] = []
    for layer in document.get("layers", []):
        if not isinstance(layer, dict):
            normalized_layers.append(layer)
            continue
        layer_type = layer.get("type")
        if layer_type in LAYER_DEFAULTS:
            base = make_layer(layer_type, str(layer.get("id", "missing_layer")))
            base.update({key: deepcopy(value) for key, value in layer.items() if key not in ("properties", "material", "curves", "gradient")})
            base["properties"] = _merge_defaults(layer.get("properties", {}), LAYER_DEFAULTS[layer_type]["properties"])
            base["material"] = _merge_defaults(layer.get("material", {}), COMMON_LAYER["material"])
            base["curves"] = _merge_defaults(layer.get("curves", {}), LAYER_DEFAULTS[layer_type].get("curves", {}))
            base["gradient"] = deepcopy(layer.get("gradient", LAYER_DEFAULTS[layer_type].get("gradient", COMMON_LAYER["gradient"])))
            normalized_layers.append(base)
        else:
            normalized_layers.append(layer)
    document["layers"] = normalized_layers
    document["schema_version"] = SCHEMA_VERSION
    return document


def read_document(path: str | Path) -> dict[str, Any]:
    document_path = Path(path)
    try:
        text = document_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DocumentError(f"Could not read {document_path}: {exc}", "FILE_READ", str(document_path)) from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DocumentError(
            f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            "INVALID_JSON",
            str(document_path),
        ) from exc
    try:
        return migrate_document(raw)
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError(f"Could not migrate {document_path}: {exc}", "MIGRATION_FAILED") from exc


def _fsync_directory(directory: Path) -> None:
    try:
        descriptor = os.open(directory, os.O_DIRECTORY)
    except (OSError, AttributeError):
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_document(path: str | Path, document: dict[str, Any], make_backup: bool = True) -> None:
    """Write a document atomically, retaining a last-known-good .bak copy."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False, allow_nan=False) + "\n"
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        if make_backup and destination.exists():
            backup = destination.with_name(destination.name + ".bak")
            shutil.copy2(destination, backup)
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise DocumentError(f"Could not atomically write {destination}: {exc}", "FILE_WRITE", str(destination)) from exc


def parse_value(text: str) -> Any:
    """Parse CLI values as JSON first, then preserve a normal string."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _find_layer(document: dict[str, Any], layer_id: str) -> dict[str, Any]:
    for layer in document.get("layers", []):
        if isinstance(layer, dict) and layer.get("id") == layer_id:
            return layer
    raise KeyError(f"Layer '{layer_id}' does not exist.")


def get_path(document: dict[str, Any], path: str) -> Any:
    tokens = [token for token in path.split(".") if token]
    if not tokens:
        raise KeyError("A non-empty path is required.")
    current: Any = document
    if tokens[0] == "layers" and len(tokens) >= 2:
        current = _find_layer(document, tokens[1])
        tokens = tokens[2:]
        if tokens and tokens[0] not in current:
            properties = current.get("properties", {})
            if tokens[0] in properties:
                current = properties
    for token in tokens:
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, dict) and token in current:
            current = current[token]
        else:
            raise KeyError(f"Path '{path}' does not exist at '{token}'.")
    return current


def set_path(document: dict[str, Any], path: str, value: Any) -> None:
    tokens = [token for token in path.split(".") if token]
    if not tokens:
        raise KeyError("A non-empty path is required.")
    current: Any = document
    if tokens[0] == "layers" and len(tokens) >= 3:
        current = _find_layer(document, tokens[1])
        tokens = tokens[2:]
        if tokens[0] not in current and tokens[0] in current.get("properties", {}):
            current = current["properties"]
    for token in tokens[:-1]:
        if isinstance(current, dict):
            if token not in current:
                current[token] = {}
            current = current[token]
        elif isinstance(current, list):
            current = current[int(token)]
        else:
            raise KeyError(f"Cannot traverse '{token}' in '{path}'.")
    final = tokens[-1]
    if isinstance(current, dict):
        current[final] = value
    elif isinstance(current, list):
        current[int(final)] = value
    else:
        raise KeyError(f"Cannot assign '{path}'.")


def add_layer(document: dict[str, Any], layer_type: str, layer_id: str, name: str | None = None) -> dict[str, Any]:
    if any(isinstance(item, dict) and item.get("id") == layer_id for item in document.get("layers", [])):
        raise KeyError(f"Layer '{layer_id}' already exists.")
    layer = make_layer(layer_type, layer_id, name)
    document.setdefault("layers", []).append(layer)
    return layer


def remove_layer(document: dict[str, Any], layer_id: str) -> dict[str, Any]:
    layers = document.get("layers", [])
    for index, layer in enumerate(layers):
        if isinstance(layer, dict) and layer.get("id") == layer_id:
            return layers.pop(index)
    raise KeyError(f"Layer '{layer_id}' does not exist.")


def clone_document(document: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(document)


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
