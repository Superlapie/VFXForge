"""JSON Schema validation helpers for service contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .resources import schema_dir


class SchemaValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def _load_schema(name: str) -> dict[str, Any]:
    path = schema_dir() / name
    return json.loads(path.read_text(encoding="utf-8"))


def validate_instance(instance: Any, schema_name: str) -> None:
    schema = _load_schema(schema_name)
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("jsonschema is required for schema validation. Install the vfxforge package dependencies.") from exc
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    if errors:
        messages = [f"{list(error.path) or ['$']}: {error.message}" for error in errors]
        raise SchemaValidationError(messages)


def validate_file(path: Path, schema_name: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_instance(payload, schema_name)
