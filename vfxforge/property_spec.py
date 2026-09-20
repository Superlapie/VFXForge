"""Authoritative typed property specifications for strict validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .schema import (
    BILLBOARD_MODES,
    BLEND_MODES,
    COMMON_LAYER,
    EMISSION_SHAPES,
    LAYER_DEFAULTS,
    LAYER_TYPES,
    default_document,
)


ROOT_KEYS = frozenset(default_document("_placeholder").keys())
DOCUMENT_OPTIONAL_KEYS = ROOT_KEYS - frozenset({"schema_version", "id", "name", "duration", "loop", "seed", "layers"})
LAYER_STRUCT_KEYS = frozenset({"id", "type", "name", "enabled", "start", "duration", "properties", "material", "curves", "gradient"})


OPTIONAL_VISUAL_PROPERTIES = frozenset({"color"})
VISUAL_LAYER_TYPES_WITH_COLOR = frozenset({
    "particle", "mesh_particle", "sprite", "trail", "beam", "light", "decal", "mesh_effect",
})

MESH_PRIMITIVE_VALUES = ("quad", "sphere", "box", "torus")
CHILD_EFFECT_TRIGGERS = ("on_start", "on_stop", "manual")
TRAIL_UV_MODES = ("stretch", "repeat")


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: str
    values: tuple[str, ...] = ()
    dimensions: int = 0


def _infer_kind(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        if len(value) == 2:
            return "vector2"
        if len(value) == 3:
            return "vector3"
    if isinstance(value, dict):
        return "object"
    return "unknown"


PROPERTY_ENUMS: dict[tuple[str, str], tuple[str, ...]] = {
    ("particle", "emission_shape"): EMISSION_SHAPES,
    ("mesh_particle", "emission_shape"): EMISSION_SHAPES,
    ("mesh_particle", "mesh"): MESH_PRIMITIVE_VALUES,
    ("mesh_effect", "mesh"): MESH_PRIMITIVE_VALUES,
    ("sprite", "billboard"): BILLBOARD_MODES,
    ("child_effect", "trigger"): CHILD_EFFECT_TRIGGERS,
    ("trail", "uv_mode"): TRAIL_UV_MODES,
}

PROPERTY_INTEGERS: frozenset[tuple[str, str]] = frozenset({
    ("particle", "amount"),
    ("particle", "fixed_fps"),
    ("mesh_particle", "amount"),
    ("sprite", "flipbook_columns"),
    ("sprite", "flipbook_rows"),
    ("sprite", "flipbook_frames"),
    ("sprite", "flipbook_start_frame"),
    ("trail", "segments"),
    ("beam", "segments"),
    ("child_effect", "max_instances"),
})

PROPERTY_BOOLEANS: frozenset[tuple[str, str]] = frozenset({
    ("particle", "one_shot"),
    ("particle", "local_coords"),
    ("mesh_particle", "one_shot"),
    ("sprite", "flipbook_loop"),
    ("sprite", "random_start"),
    ("sprite", "pixel_snap"),
    ("light", "shadow_enabled"),
    ("light", "fade"),
    ("decal", "fade"),
    ("child_effect", "inherit_transform"),
})

PROPERTY_COLORS: frozenset[tuple[str, str]] = frozenset({
    ("light", "color"),
    ("trail", "color"),
    ("beam", "color"),
    ("decal", "color"),
    ("mesh_effect", "color"),
    ("particle", "color"),
    ("mesh_particle", "color"),
    ("sprite", "color"),
})

MATERIAL_ENUMS: dict[str, tuple[str, ...]] = {
    "blend_mode": BLEND_MODES,
    "billboard": BILLBOARD_MODES,
}

MATERIAL_BOOLEANS = frozenset({"unshaded"})


PROPERTY_STRINGS: frozenset[tuple[str, str]] = frozenset({
    ("trail", "target"),
    ("child_effect", "effect_id"),
    ("audio_marker", "event_id"),
    ("event_marker", "event_id"),
})

PROPERTY_VECTORS: dict[tuple[str, str], int] = {
    ("particle", "direction"): 3,
    ("particle", "gravity"): 3,
    ("particle", "attractor_position"): 3,
    ("mesh_particle", "size"): 3,
    ("mesh_particle", "gravity"): 3,
    ("sprite", "size"): 2,
    ("beam", "source"): 3,
    ("beam", "target"): 3,
    ("decal", "size"): 2,
    ("mesh_effect", "size"): 3,
    ("mesh_effect", "rotation"): 3,
    ("mesh_effect", "rotation_speed"): 3,
    ("child_effect", "offset"): 3,
}


def _property_spec(layer_type: str, key: str, default: Any) -> FieldSpec:
    enum_values = PROPERTY_ENUMS.get((layer_type, key))
    if enum_values is not None:
        return FieldSpec(name=key, kind="enum", values=enum_values)
    if (layer_type, key) in PROPERTY_BOOLEANS:
        return FieldSpec(name=key, kind="boolean")
    if (layer_type, key) in PROPERTY_INTEGERS:
        return FieldSpec(name=key, kind="integer")
    if (layer_type, key) in PROPERTY_COLORS:
        return FieldSpec(name=key, kind="color")
    if (layer_type, key) in PROPERTY_STRINGS:
        return FieldSpec(name=key, kind="string")
    vector_dims = PROPERTY_VECTORS.get((layer_type, key))
    if vector_dims == 2:
        return FieldSpec(name=key, kind="vector2", dimensions=2)
    if vector_dims == 3:
        return FieldSpec(name=key, kind="vector3", dimensions=3)
    if key in {"texture", "mesh_asset"}:
        return FieldSpec(name=key, kind="string")
    if key == "payload":
        return FieldSpec(name=key, kind="object")
    kind = _infer_kind(default)
    if kind == "vector2":
        return FieldSpec(name=key, kind="vector2", dimensions=2)
    if kind == "vector3":
        return FieldSpec(name=key, kind="vector3", dimensions=3)
    return FieldSpec(name=key, kind=kind)


def _material_spec(key: str, default: Any) -> FieldSpec:
    enum_values = MATERIAL_ENUMS.get(key)
    if enum_values is not None:
        return FieldSpec(name=key, kind="enum", values=enum_values)
    if key in MATERIAL_BOOLEANS:
        return FieldSpec(name=key, kind="boolean")
    if key == "tint":
        return FieldSpec(name=key, kind="color")
    if key == "texture":
        return FieldSpec(name=key, kind="string")
    if key == "uv_scroll":
        return FieldSpec(name=key, kind="vector2", dimensions=2)
    kind = _infer_kind(default)
    if kind == "number":
        return FieldSpec(name=key, kind="number")
    return FieldSpec(name=key, kind=kind)


LAYER_PROPERTY_SPECS: dict[str, dict[str, FieldSpec]] = {}
LAYER_MATERIAL_SPECS: dict[str, FieldSpec] = {}

for layer_type, defaults in LAYER_DEFAULTS.items():
    specs: dict[str, FieldSpec] = {}
    for key, value in defaults.get("properties", {}).items():
        specs[key] = _property_spec(layer_type, key, value)
    if layer_type in VISUAL_LAYER_TYPES_WITH_COLOR:
        specs.setdefault("color", FieldSpec(name="color", kind="color"))
    LAYER_PROPERTY_SPECS[layer_type] = specs

for key, value in COMMON_LAYER["material"].items():
    LAYER_MATERIAL_SPECS[key] = _material_spec(key, value)


def layer_property_keys(layer_type: str) -> frozenset[str]:
    return frozenset(LAYER_PROPERTY_SPECS.get(layer_type, {}).keys())


def layer_material_keys() -> frozenset[str]:
    return frozenset(LAYER_MATERIAL_SPECS.keys())


def layer_curve_keys(layer_type: str) -> frozenset[str]:
    defaults = LAYER_DEFAULTS.get(layer_type, {})
    return frozenset(defaults.get("curves", {}).keys())


def all_layer_types() -> tuple[str, ...]:
    return LAYER_TYPES


def property_spec(layer_type: str, key: str) -> FieldSpec | None:
    return LAYER_PROPERTY_SPECS.get(layer_type, {}).get(key)


def material_spec(key: str) -> FieldSpec | None:
    return LAYER_MATERIAL_SPECS.get(key)


def _is_color(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text.startswith("#"):
        return False
    hex_part = text[1:]
    return len(hex_part) in {6, 8} and all(item in "0123456789abcdefABCDEF" for item in hex_part)


def _validate_vector(value: Any, dimensions: int) -> bool:
    if not isinstance(value, list) or len(value) != dimensions:
        return False
    return all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)


def validate_field_value(spec: FieldSpec, value: Any) -> str | None:
    if spec.kind == "boolean":
        return None if isinstance(value, bool) else f"expected boolean, got {type(value).__name__}"
    if spec.kind == "integer":
        return None if isinstance(value, int) and not isinstance(value, bool) else f"expected integer, got {type(value).__name__}"
    if spec.kind == "number":
        return None if isinstance(value, (int, float)) and not isinstance(value, bool) else f"expected number, got {type(value).__name__}"
    if spec.kind == "string":
        return None if isinstance(value, str) else f"expected string, got {type(value).__name__}"
    if spec.kind == "enum":
        return None if isinstance(value, str) and value in spec.values else f"expected one of: {', '.join(spec.values)}"
    if spec.kind == "color":
        return None if _is_color(value) else "expected #RRGGBB or #RRGGBBAA color string"
    if spec.kind == "vector2":
        return None if _validate_vector(value, 2) else "expected [x, y] numeric array"
    if spec.kind == "vector3":
        return None if _validate_vector(value, 3) else "expected [x, y, z] numeric array"
    if spec.kind == "object":
        return None if isinstance(value, dict) else f"expected object, got {type(value).__name__}"
    return None


def validate_layer_property_types(
    layer_type: str,
    properties: dict[str, Any],
    *,
    path_prefix: str,
    append_error: Callable[[str, str, str, str, Any], None],
) -> None:
    specs = LAYER_PROPERTY_SPECS.get(layer_type, {})
    for key, value in properties.items():
        spec = specs.get(key)
        if spec is None:
            continue
        message = validate_field_value(spec, value)
        if message is not None:
            append_error(
                "INVALID_PROPERTY_TYPE",
                f"{path_prefix}.properties.{key}",
                f"Property '{key}' on layer type '{layer_type}' has invalid type: {message}.",
                "Use the canonical typed value for this field.",
                value,
            )


def validate_layer_material_types(
    material: dict[str, Any],
    *,
    path_prefix: str,
    append_error: Callable[[str, str, str, str, Any], None],
) -> None:
    for key, value in material.items():
        spec = LAYER_MATERIAL_SPECS.get(key)
        if spec is None:
            continue
        message = validate_field_value(spec, value)
        if message is not None:
            append_error(
                "INVALID_MATERIAL_TYPE",
                f"{path_prefix}.material.{key}",
                f"Material field '{key}' has invalid type: {message}.",
                "Use the canonical typed value for this field.",
                value,
            )


def describe_property_registry() -> dict[str, Any]:
    layers = {}
    for layer_type in LAYER_TYPES:
        layers[layer_type] = {
            "properties": {
                key: {"kind": spec.kind, "values": list(spec.values) if spec.values else None, "dimensions": spec.dimensions or None}
                for key, spec in sorted(LAYER_PROPERTY_SPECS.get(layer_type, {}).items())
            },
            "material": {
                key: {"kind": spec.kind, "values": list(spec.values) if spec.values else None}
                for key, spec in sorted(LAYER_MATERIAL_SPECS.items())
            },
            "curves": sorted(layer_curve_keys(layer_type)),
        }
    return {"root_keys": sorted(ROOT_KEYS), "layers": layers}
