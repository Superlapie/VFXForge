"""Authoritative typed property specifications for strict validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from .model import coerce_float
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

MESH_PARTICLE_PRIMITIVE_VALUES = ("quad", "sphere", "box", "torus")
MESH_EFFECT_PRIMITIVE_VALUES = ("sphere", "box", "torus", "quad")
CHILD_EFFECT_TRIGGERS = ("on_start", "on_stop", "manual")
TRAIL_UV_MODES = ("stretch", "repeat")


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: str
    values: tuple[str, ...] = ()
    dimensions: int = 0
    minimum: float | None = None
    maximum: float | None = None


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
    ("mesh_particle", "mesh"): MESH_PARTICLE_PRIMITIVE_VALUES,
    ("mesh_effect", "mesh"): MESH_EFFECT_PRIMITIVE_VALUES,
    ("sprite", "billboard"): BILLBOARD_MODES,
    ("child_effect", "trigger"): CHILD_EFFECT_TRIGGERS,
    ("trail", "uv_mode"): TRAIL_UV_MODES,
}

PROPERTY_RANGES: dict[tuple[str, str], tuple[float | None, float | None]] = {
    ("particle", "explosiveness"): (0.0, 1.0),
    ("particle", "randomness"): (0.0, 1.0),
    ("particle", "lifetime"): (0.02, None),
    ("particle", "amount"): (0.0, None),
    ("particle", "fixed_fps"): (0.0, None),
    ("mesh_particle", "lifetime"): (0.02, None),
    ("mesh_particle", "amount"): (0.0, None),
    ("sprite", "flipbook_columns"): (1.0, None),
    ("sprite", "flipbook_rows"): (1.0, None),
    ("sprite", "flipbook_frames"): (1.0, None),
    ("sprite", "flipbook_start_frame"): (0.0, None),
    ("sprite", "flipbook_fps"): (0.0, None),
    ("trail", "width"): (0.01, None),
    ("trail", "lifetime"): (0.02, None),
    ("trail", "alpha"): (0.0, 1.0),
    ("trail", "segments"): (2.0, 64.0),
    ("beam", "segments"): (2.0, 64.0),
    ("beam", "thickness"): (0.01, None),
    ("beam", "fade"): (0.0, 1.0),
    ("light", "range"): (0.1, None),
    ("light", "energy"): (0.0, None),
    ("mesh_effect", "pulse"): (0.0, None),
    ("mesh_effect", "dissolve"): (0.0, None),
}

MATERIAL_RANGES: dict[str, tuple[float | None, float | None]] = {
    "emissive_intensity": (0.0, None),
    "distortion": (0.0, None),
    "dissolve": (0.0, None),
    "fresnel": (0.0, None),
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
    minimum, maximum = PROPERTY_RANGES.get((layer_type, key), (None, None))
    if enum_values is not None:
        return FieldSpec(name=key, kind="enum", values=enum_values, minimum=minimum, maximum=maximum)
    if (layer_type, key) in PROPERTY_BOOLEANS:
        return FieldSpec(name=key, kind="boolean", minimum=minimum, maximum=maximum)
    if (layer_type, key) in PROPERTY_INTEGERS:
        return FieldSpec(name=key, kind="integer", minimum=minimum, maximum=maximum)
    if (layer_type, key) in PROPERTY_COLORS:
        return FieldSpec(name=key, kind="color", minimum=minimum, maximum=maximum)
    if (layer_type, key) in PROPERTY_STRINGS:
        return FieldSpec(name=key, kind="string", minimum=minimum, maximum=maximum)
    vector_dims = PROPERTY_VECTORS.get((layer_type, key))
    if vector_dims == 2:
        return FieldSpec(name=key, kind="vector2", dimensions=2, minimum=minimum, maximum=maximum)
    if vector_dims == 3:
        return FieldSpec(name=key, kind="vector3", dimensions=3, minimum=minimum, maximum=maximum)
    if key in {"texture", "mesh_asset"}:
        return FieldSpec(name=key, kind="string", minimum=minimum, maximum=maximum)
    if key == "payload":
        return FieldSpec(name=key, kind="object", minimum=minimum, maximum=maximum)
    kind = _infer_kind(default)
    if kind == "vector2":
        return FieldSpec(name=key, kind="vector2", dimensions=2, minimum=minimum, maximum=maximum)
    if kind == "vector3":
        return FieldSpec(name=key, kind="vector3", dimensions=3, minimum=minimum, maximum=maximum)
    return FieldSpec(name=key, kind=kind, minimum=minimum, maximum=maximum)


def _material_spec(key: str, default: Any) -> FieldSpec:
    enum_values = MATERIAL_ENUMS.get(key)
    minimum, maximum = MATERIAL_RANGES.get(key, (None, None))
    if enum_values is not None:
        return FieldSpec(name=key, kind="enum", values=enum_values, minimum=minimum, maximum=maximum)
    if key in MATERIAL_BOOLEANS:
        return FieldSpec(name=key, kind="boolean", minimum=minimum, maximum=maximum)
    if key == "tint":
        return FieldSpec(name=key, kind="color", minimum=minimum, maximum=maximum)
    if key == "texture":
        return FieldSpec(name=key, kind="string", minimum=minimum, maximum=maximum)
    if key == "uv_scroll":
        return FieldSpec(name=key, kind="vector2", dimensions=2, minimum=minimum, maximum=maximum)
    kind = _infer_kind(default)
    if kind == "number":
        return FieldSpec(name=key, kind="number", minimum=minimum, maximum=maximum)
    return FieldSpec(name=key, kind=kind, minimum=minimum, maximum=maximum)


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


def _is_finite_scalar(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _scalar_range_error(spec: FieldSpec, value: int | float) -> str | None:
    if spec.minimum is not None:
        if isinstance(value, int) and isinstance(spec.minimum, float) and spec.minimum.is_integer():
            if value < int(spec.minimum):
                return f"expected value >= {spec.minimum}"
        elif value < spec.minimum:
            return f"expected value >= {spec.minimum}"
    if spec.maximum is not None:
        if isinstance(value, int) and isinstance(spec.maximum, float) and spec.maximum.is_integer():
            if value > int(spec.maximum):
                return f"expected value <= {spec.maximum}"
        elif value > spec.maximum:
            return f"expected value <= {spec.maximum}"
    return None


def _validate_vector_value(spec: FieldSpec, value: Any, dimensions: int) -> tuple[str, str] | None:
    if not isinstance(value, list) or len(value) != dimensions:
        return ("INVALID_PROPERTY_TYPE", f"expected finite numeric array of length {dimensions}")
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return (
                "INVALID_PROPERTY_TYPE",
                f"expected numeric component at index {index}, got {type(item).__name__}",
            )
        if isinstance(item, float) and not math.isfinite(item):
            return ("NON_FINITE_PROPERTY", f"expected finite numeric component at index {index}, got {item!r}")
        range_message = _scalar_range_error(spec, item)
        if range_message is not None:
            return ("PROPERTY_OUT_OF_RANGE", f"component {index}: {range_message}")
    return None


PROPERTY_RELATIONS: dict[str, tuple[dict[str, Any], ...]] = {
    "sprite": (
        {
            "id": "flipbook_frames_capacity",
            "constraint": "flipbook_frames <= flipbook_columns * flipbook_rows",
            "fields": ["flipbook_columns", "flipbook_rows", "flipbook_frames"],
        },
        {
            "id": "flipbook_start_frame_bounds",
            "constraint": "0 <= flipbook_start_frame < flipbook_frames",
            "fields": ["flipbook_start_frame", "flipbook_frames"],
        },
        {
            "id": "flipbook_fps_when_animated",
            "constraint": "flipbook_fps > 0 when flipbook_frames > 1",
            "fields": ["flipbook_fps", "flipbook_frames"],
        },
        {
            "id": "flipbook_requires_sprite_texture",
            "when": "flipbook_frames > 1",
            "constraint": "properties.texture != ''",
            "fields": ["texture", "flipbook_frames"],
            "runtime_note": "Flipbook playback requires a Sprite3D created from properties.texture.",
        },
    ),
    "mesh_effect": (
        {
            "id": "custom_mesh_disables_primitive_selector",
            "when": "mesh_asset != ''",
            "constraint": "mesh must remain the default primitive selector value",
            "fields": ["mesh_asset", "mesh"],
            "runtime_note": "Imported mesh_asset replaces the primitive mesh; mesh is ignored.",
        },
    ),
    "mesh_particle": (
        {
            "id": "custom_mesh_disables_primitive_selector",
            "when": "mesh_asset != ''",
            "constraint": "mesh must remain the default primitive selector value",
            "fields": ["mesh_asset", "mesh"],
            "runtime_note": "Imported mesh_asset replaces draw_pass_1; mesh is ignored.",
        },
        {
            "id": "custom_mesh_disables_size_scaling",
            "when": "mesh_asset != ''",
            "constraint": "size must remain the default vector",
            "fields": ["mesh_asset", "size"],
            "runtime_note": "Imported mesh_asset is not scaled by size at runtime.",
        },
        {
            "id": "sphere_uniform_size",
            "when": "mesh == 'sphere' and mesh_asset == ''",
            "constraint": "size.x == size.y == size.z",
            "fields": ["mesh", "size"],
            "runtime_note": "Sphere primitive radius derives from min(size.x, size.y, size.z).",
        },
        {
            "id": "torus_primary_axis_size",
            "when": "mesh == 'torus' and mesh_asset == ''",
            "constraint": "size.x == size.y == size.z",
            "fields": ["mesh", "size"],
            "runtime_note": "Torus primitive radii derive from size.x only; keep size uniform.",
        },
        {
            "id": "quad_ignores_size_z",
            "when": "mesh == 'quad' and mesh_asset == ''",
            "constraint": "size.z must remain the default value",
            "fields": ["mesh", "size"],
            "runtime_note": "Quad primitive draw pass uses size.x and size.y only.",
        },
    ),
}

RUNTIME_ENFORCED_RELATION_IDS = frozenset({
    "flipbook_requires_sprite_texture",
    "custom_mesh_disables_primitive_selector",
    "custom_mesh_disables_size_scaling",
    "sphere_uniform_size",
    "torus_primary_axis_size",
    "quad_ignores_size_z",
})


@dataclass(frozen=True)
class PropertyRelationViolation:
    relation_id: str
    field: str
    message: str
    suggestion: str = ""
    value: Any = None


def collect_layer_property_relation_violations(
    layer_type: str,
    properties: dict[str, Any],
) -> list[PropertyRelationViolation]:
    violations: list[PropertyRelationViolation] = []
    if layer_type == "sprite":
        defaults = LAYER_DEFAULTS["sprite"]["properties"]
        columns = properties.get("flipbook_columns", defaults["flipbook_columns"])
        rows = properties.get("flipbook_rows", defaults["flipbook_rows"])
        frames = properties.get("flipbook_frames", defaults["flipbook_frames"])
        start_frame = properties.get("flipbook_start_frame", defaults["flipbook_start_frame"])
        fps = properties.get("flipbook_fps", defaults["flipbook_fps"])
        if not all(isinstance(item, int) and not isinstance(item, bool) for item in (columns, rows, frames, start_frame)):
            return violations
        atlas_capacity = columns * rows
        if frames > atlas_capacity:
            violations.append(
                PropertyRelationViolation(
                    "flipbook_frames_capacity",
                    "flipbook_frames",
                    (
                        f"flipbook_frames ({frames}) exceeds atlas capacity "
                        f"({columns} columns x {rows} rows = {atlas_capacity})."
                    ),
                    "Reduce flipbook_frames or expand the atlas grid.",
                    frames,
                )
            )
        if start_frame < 0 or start_frame >= frames:
            violations.append(
                PropertyRelationViolation(
                    "flipbook_start_frame_bounds",
                    "flipbook_start_frame",
                    f"flipbook_start_frame ({start_frame}) must satisfy 0 <= start_frame < flipbook_frames ({frames}).",
                    "Choose a start frame inside the authored atlas.",
                    start_frame,
                )
            )
        if frames > 1:
            coerced_fps = coerce_float(fps) if isinstance(fps, (int, float)) and not isinstance(fps, bool) else None
            if coerced_fps is None or coerced_fps <= 0.0:
                violations.append(
                    PropertyRelationViolation(
                        "flipbook_fps_when_animated",
                        "flipbook_fps",
                        "flipbook_fps must be greater than zero when flipbook_frames is greater than one.",
                        "Set flipbook_fps above zero or disable the flipbook.",
                        fps,
                    )
                )
        texture = str(properties.get("texture", defaults["texture"]))
        if frames > 1 and not texture:
            violations.append(
                PropertyRelationViolation(
                    "flipbook_requires_sprite_texture",
                    "texture",
                    "Animated flipbooks require properties.texture so the runtime can create a Sprite3D atlas card.",
                    "Set properties.texture or keep flipbook_frames at 1.",
                    texture,
                )
            )
        return violations

    if layer_type == "mesh_effect":
        defaults = LAYER_DEFAULTS["mesh_effect"]["properties"]
        mesh_asset = str(properties.get("mesh_asset", defaults["mesh_asset"]))
        mesh_name = str(properties.get("mesh", defaults["mesh"]))
        if mesh_asset and mesh_name != str(defaults["mesh"]):
            violations.append(
                PropertyRelationViolation(
                    "custom_mesh_disables_primitive_selector",
                    "mesh",
                    "mesh is ignored when mesh_asset is set; keep the default primitive selector.",
                    "Clear mesh_asset or reset mesh to the default value.",
                    properties.get("mesh", defaults["mesh"]),
                )
            )
        return violations

    if layer_type != "mesh_particle":
        return violations

    defaults = LAYER_DEFAULTS["mesh_particle"]["properties"]
    mesh_asset = str(properties.get("mesh_asset", defaults["mesh_asset"]))
    mesh_name = str(properties.get("mesh", defaults["mesh"]))
    size = properties.get("size", defaults["size"])
    default_mesh = str(defaults["mesh"])
    default_size = defaults["size"]

    if mesh_asset:
        if mesh_name != default_mesh:
            violations.append(
                PropertyRelationViolation(
                    "custom_mesh_disables_primitive_selector",
                    "mesh",
                    "mesh is ignored when mesh_asset is set; keep the default primitive selector.",
                    "Clear mesh_asset or reset mesh to the default value.",
                    mesh_name,
                )
            )
        if size != default_size:
            violations.append(
                PropertyRelationViolation(
                    "custom_mesh_disables_size_scaling",
                    "size",
                    "size is not applied to imported mesh_asset draw passes at runtime.",
                    "Clear mesh_asset or reset size to the default vector.",
                    size,
                )
            )
        return violations

    if mesh_name == "quad":
        if isinstance(size, list) and len(size) == 3 and size[2] != default_size[2]:
            violations.append(
                PropertyRelationViolation(
                    "quad_ignores_size_z",
                    "size",
                    "mesh 'quad' ignores size.z; keep the default Z component.",
                    "Use size.x and size.y only or choose box/sphere/torus.",
                    size,
                )
            )
        return violations

    if mesh_name not in {"sphere", "torus"}:
        return violations
    if not isinstance(size, list) or len(size) != 3:
        return violations
    if not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in size):
        return violations
    if size[0] == size[1] == size[2]:
        return violations
    relation_id = "sphere_uniform_size" if mesh_name == "sphere" else "torus_primary_axis_size"
    violations.append(
        PropertyRelationViolation(
            relation_id,
            "size",
            f"mesh '{mesh_name}' requires uniform size.x == size.y == size.z for predictable primitive scaling.",
            "Use equal size components or choose box/quad.",
            size,
        )
    )
    return violations


def describe_property_relations() -> dict[str, list[dict[str, Any]]]:
    return {layer_type: [dict(rule) for rule in rules] for layer_type, rules in PROPERTY_RELATIONS.items()}


def validate_field_value(spec: FieldSpec, value: Any) -> tuple[str, str] | None:
    if spec.kind == "boolean":
        if isinstance(value, bool):
            return None
        return ("INVALID_PROPERTY_TYPE", f"expected boolean, got {type(value).__name__}")
    if spec.kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return ("INVALID_PROPERTY_TYPE", f"expected integer, got {type(value).__name__}")
        range_message = _scalar_range_error(spec, value)
        if range_message is not None:
            return ("PROPERTY_OUT_OF_RANGE", range_message)
        return None
    if spec.kind == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return ("INVALID_PROPERTY_TYPE", f"expected number, got {type(value).__name__}")
        if isinstance(value, float) and not math.isfinite(value):
            return ("NON_FINITE_PROPERTY", f"expected finite number, got {value!r}")
        range_message = _scalar_range_error(spec, value)
        if range_message is not None:
            return ("PROPERTY_OUT_OF_RANGE", range_message)
        return None
    if spec.kind == "string":
        if isinstance(value, str):
            return None
        return ("INVALID_PROPERTY_TYPE", f"expected string, got {type(value).__name__}")
    if spec.kind == "enum":
        if isinstance(value, str) and value in spec.values:
            return None
        return ("INVALID_PROPERTY_ENUM", f"expected one of: {', '.join(spec.values)}")
    if spec.kind == "color":
        if _is_color(value):
            return None
        return ("INVALID_PROPERTY_TYPE", "expected #RRGGBB or #RRGGBBAA color string")
    if spec.kind == "vector2":
        return _validate_vector_value(spec, value, 2)
    if spec.kind == "vector3":
        return _validate_vector_value(spec, value, 3)
    if spec.kind == "object":
        if not isinstance(value, dict):
            return ("INVALID_PROPERTY_TYPE", f"expected object, got {type(value).__name__}")
        from .model import validate_json_safe

        for bad_path, bad_value in validate_json_safe(value, path=""):
            return ("NON_FINITE_PROPERTY", f"expected finite JSON values in object, got {bad_value!r} at {bad_path}")
        return None
    return None


def _material_error_code(code: str) -> str:
    if code == "INVALID_PROPERTY_TYPE":
        return "INVALID_MATERIAL_TYPE"
    if code == "INVALID_PROPERTY_ENUM":
        return "INVALID_MATERIAL_ENUM"
    if code == "PROPERTY_OUT_OF_RANGE":
        return "MATERIAL_OUT_OF_RANGE"
    if code == "NON_FINITE_PROPERTY":
        return "NON_FINITE_MATERIAL"
    return code


def validate_layer_property_relations(
    layer_type: str,
    properties: dict[str, Any],
    *,
    path_prefix: str,
    append_error: Callable[[str, str, str, str, Any], None],
) -> None:
    for violation in collect_layer_property_relation_violations(layer_type, properties):
        append_error(
            "INVALID_PROPERTY_RELATION",
            f"{path_prefix}.properties.{violation.field}",
            violation.message,
            violation.suggestion,
            violation.value,
        )


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
        result = validate_field_value(spec, value)
        if result is not None:
            code, message = result
            append_error(
                code,
                f"{path_prefix}.properties.{key}",
                f"Property '{key}' on layer type '{layer_type}' has invalid value: {message}.",
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
        result = validate_field_value(spec, value)
        if result is not None:
            code, message = result
            append_error(
                _material_error_code(code),
                f"{path_prefix}.material.{key}",
                f"Material field '{key}' has invalid value: {message}.",
                "Use the canonical typed value for this field.",
                value,
            )


def _serialize_field_spec(spec: FieldSpec) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": spec.kind}
    if spec.values:
        payload["values"] = list(spec.values)
    if spec.dimensions:
        payload["dimensions"] = spec.dimensions
    if spec.minimum is not None:
        payload["minimum"] = spec.minimum
    if spec.maximum is not None:
        payload["maximum"] = spec.maximum
    return payload


def describe_property_registry() -> dict[str, Any]:
    layers = {}
    for layer_type in LAYER_TYPES:
        layers[layer_type] = {
            "properties": {
                key: _serialize_field_spec(spec)
                for key, spec in sorted(LAYER_PROPERTY_SPECS.get(layer_type, {}).items())
            },
            "material": {
                key: _serialize_field_spec(spec)
                for key, spec in sorted(LAYER_MATERIAL_SPECS.items())
            },
            "curves": sorted(layer_curve_keys(layer_type)),
        }
    return {"root_keys": sorted(ROOT_KEYS), "layers": layers, "relations": describe_property_relations()}
