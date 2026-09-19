"""Validate compiled documents against the Godot runtime capability contract."""

from __future__ import annotations

import hashlib
from typing import Any

from ..resources import godot_runtime_dir


RUNTIME_CONTRACT_VERSION = 2

PropertyTier = str  # implemented | emulated | inert_only | unsupported

PARTICLE_EMISSION_SHAPES = frozenset({
    "point",
    "sphere",
    "sphere_surface",
    "box",
    "ring",
    "line",
    "cone",
    "disc",
})

MATERIAL_COMMON: dict[str, PropertyTier] = {
    "blend_mode": "implemented",
    "unshaded": "implemented",
    "billboard": "implemented",
    "depth_draw": "inert_only",
    "texture": "implemented",
    "tint": "implemented",
    "uv_scroll": "inert_only",
    "distortion": "inert_only",
    "dissolve": "inert_only",
    "fresnel": "inert_only",
    "emissive_intensity": "implemented",
}

MATERIAL_DEFAULTS: dict[str, Any] = {
    "depth_draw": "always",
    "uv_scroll": [0.0, 0.0],
    "distortion": 0.0,
    "dissolve": 0.0,
    "fresnel": 0.0,
}

LAYER_CONTRACTS: dict[str, dict[str, Any]] = {
    "particle": {
        "properties": {
            "amount": "implemented",
            "one_shot": "implemented",
            "lifetime": "implemented",
            "explosiveness": "implemented",
            "randomness": "implemented",
            "fixed_fps": "implemented",
            "local_coords": "implemented",
            "emission_shape": "implemented",
            "emission_box_extents": "implemented",
            "emission_radius": "implemented",
            "emission_height": "implemented",
            "direction": "implemented",
            "spread": "implemented",
            "initial_velocity": "implemented",
            "initial_velocity_min": "implemented",
            "initial_velocity_max": "implemented",
            "gravity": "implemented",
            "damping": "implemented",
            "radial_accel": "implemented",
            "tangential_accel": "implemented",
            "scale_min": "implemented",
            "scale_max": "implemented",
            "rotation_min": "implemented",
            "rotation_max": "implemented",
            "angular_velocity_min": "implemented",
            "angular_velocity_max": "implemented",
            "flipbook_start_frame": "implemented",
            "flipbook_frames": "implemented",
            "flipbook_fps": "implemented",
            "flipbook_loop": "implemented",
            "texture": "implemented",
            "color": "implemented",
            "size": "implemented",
            "mesh_asset": "implemented",
            "turbulence": "inert_only",
            "attractor_strength": "inert_only",
            "attractor_position": "inert_only",
        },
        "property_defaults": {
            "turbulence": 0.0,
            "attractor_strength": 0.0,
            "attractor_position": [0.0, 0.0, 0.0],
        },
        "curves": {
            "scale": "implemented",
            "alpha": "implemented",
            "velocity": "emulated",
        },
    },
    "mesh_particle": {
        "inherits": "particle",
    },
    "trail": {
        "properties": {
            "width": "implemented",
            "lifetime": "implemented",
            "segments": "implemented",
            "color": "implemented",
            "alpha": "implemented",
            "target": "implemented",
            "texture": "inert_only",
            "uv_mode": "inert_only",
        },
        "property_defaults": {
            "alpha": 1.0,
            "texture": "",
            "uv_mode": "stretch",
        },
        "curves": {
            "width": "implemented",
        },
    },
    "mesh_effect": {
        "properties": {
            "mesh": "implemented",
            "mesh_asset": "implemented",
            "size": "implemented",
            "color": "implemented",
            "rotation": "implemented",
            "rotation_speed": "implemented",
            "pulse": "implemented",
            "dissolve": "inert_only",
        },
        "property_defaults": {
            "dissolve": 0.0,
            "pulse": 0.0,
        },
        "curves": {
            "scale": "implemented",
            "alpha": "implemented",
        },
    },
    "decal": {
        "properties": {
            "size": "implemented",
            "color": "implemented",
            "texture": "implemented",
            "height": "implemented",
            "fade": "implemented",
            "rotate": "implemented",
        },
        "property_defaults": {
            "height": 0.0,
            "fade": False,
            "rotate": 0.0,
        },
        "curves": {
            "alpha": "implemented",
            "scale": "implemented",
        },
    },
    "light": {
        "properties": {
            "color": "implemented",
            "energy": "implemented",
            "range": "implemented",
            "shadow_enabled": "implemented",
            "fade": "implemented",
        },
        "property_defaults": {
            "fade": False,
        },
        "curves": {
            "energy": "implemented",
        },
    },
    "beam": {
        "properties": {
            "source": "implemented",
            "target": "implemented",
            "segments": "implemented",
            "thickness": "implemented",
            "noise": "implemented",
            "color": "implemented",
            "texture": "implemented",
            "scroll_speed": "implemented",
            "fade": "implemented",
        },
        "property_defaults": {
            "scroll_speed": 0.0,
            "fade": 0.0,
        },
        "curves": {
            "width": "implemented",
        },
    },
    "event_marker": {
        "properties": {
            "event_id": "implemented",
            "payload": "implemented",
        },
        "property_defaults": {
            "payload": {},
        },
    },
    "sprite": {
        "properties": {
            "texture": "implemented",
            "size": "implemented",
            "flipbook_columns": "implemented",
            "flipbook_rows": "implemented",
            "flipbook_frames": "implemented",
            "flipbook_fps": "implemented",
            "flipbook_loop": "implemented",
            "flipbook_start_frame": "implemented",
            "random_start": "inert_only",
            "pixel_snap": "inert_only",
            "billboard": "implemented",
            "color": "implemented",
        },
        "property_defaults": {
            "random_start": False,
            "pixel_snap": False,
        },
        "curves": {
            "scale": "implemented",
            "alpha": "implemented",
        },
    },
}


def _resolved_layer_contract(layer_type: str) -> dict[str, Any] | None:
    entry = LAYER_CONTRACTS.get(layer_type)
    if entry is None:
        return None
    if "inherits" in entry:
        base = _resolved_layer_contract(str(entry["inherits"]))
        if base is None:
            return None
        merged = {
            "properties": dict(base.get("properties", {})),
            "property_defaults": dict(base.get("property_defaults", {})),
            "curves": dict(base.get("curves", {})),
        }
        for key in ("properties", "property_defaults", "curves"):
            if key in entry:
                merged[key].update(entry[key])
        return merged
    return entry


def _curve_has_points(curve: Any) -> bool:
    if not isinstance(curve, dict):
        return False
    points = curve.get("points")
    return isinstance(points, list) and len(points) > 0


def _safe_float(value: Any, default: float = 0.0) -> float | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _values_equal(left: Any, right: Any, *, tolerance: float = 1e-6) -> bool:
    if left == right:
        return True
    if isinstance(left, (int, float)) and isinstance(right, (int, float)) and not isinstance(left, bool) and not isinstance(right, bool):
        return abs(float(left) - float(right)) <= tolerance
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(_values_equal(a, b, tolerance=tolerance) for a, b in zip(left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            return False
        return all(_values_equal(left[key], right[key], tolerance=tolerance) for key in left)
    return False


def _is_default_value(value: Any, default: Any) -> bool:
    if default is None:
        return value is None
    if isinstance(default, str) and default == "":
        return value in {None, ""}
    if isinstance(default, dict) and not default:
        return value in {None, {}, []}
    return _values_equal(value, default)


def _tier_blocks_non_default(tier: PropertyTier) -> bool:
    return tier in {"inert_only", "unsupported"}


def _append_property_error(
    errors: list[dict[str, Any]],
    *,
    code: str,
    layer_id: str,
    path: str,
    message: str,
    tier: PropertyTier | None = None,
    supported: list[str] | None = None,
) -> None:
    item: dict[str, Any] = {
        "code": code,
        "message": message,
        "layer_id": layer_id,
        "path": path,
    }
    if tier is not None:
        item["tier"] = tier
    if supported is not None:
        item["supported"] = supported
    errors.append(item)


def _validate_property_map(
    errors: list[dict[str, Any]],
    *,
    layer_id: str,
    layer_type: str,
    values: dict[str, Any],
    contract: dict[str, PropertyTier],
    defaults: dict[str, Any],
    path_prefix: str,
    unknown_code: str,
    unsupported_code: str,
) -> None:
    for key, value in values.items():
        path = f"{path_prefix}.{key}"
        tier = contract.get(key)
        if tier is None:
            _append_property_error(
                errors,
                code=unknown_code,
                layer_id=layer_id,
                path=path,
                message=(
                    f"Layer '{layer_id}' ({layer_type}) uses property '{key}' "
                    "which has no declared runtime behavior."
                ),
            )
            continue
        if tier == "unsupported":
            _append_property_error(
                errors,
                code=unsupported_code,
                layer_id=layer_id,
                path=path,
                message=f"Layer '{layer_id}' uses unsupported runtime property '{key}'.",
                tier=tier,
            )
            continue
        if tier == "inert_only" and not _is_default_value(value, defaults.get(key)):
            _append_property_error(
                errors,
                code=unsupported_code,
                layer_id=layer_id,
                path=path,
                message=(
                    f"Layer '{layer_id}' uses non-default '{key}' "
                    f"({value!r}); runtime only accepts the neutral default."
                ),
                tier=tier,
            )
            continue
        if key in {"turbulence", "attractor_strength"}:
            numeric = _safe_float(value, 0.0)
            if numeric is None:
                _append_property_error(
                    errors,
                    code=unsupported_code,
                    layer_id=layer_id,
                    path=path,
                    message=f"Layer '{layer_id}' property '{key}' must be numeric.",
                    tier=tier,
                )
            elif numeric != 0.0:
                _append_property_error(
                    errors,
                    code=unsupported_code,
                    layer_id=layer_id,
                    path=path,
                    message=f"Layer '{layer_id}' uses non-zero '{key}', which the runtime does not implement.",
                    tier=tier,
                )


def _validate_curve_map(
    errors: list[dict[str, Any]],
    *,
    layer_id: str,
    layer_type: str,
    curves: dict[str, Any],
    contract: dict[str, PropertyTier],
    path_prefix: str,
) -> None:
    for channel, curve in curves.items():
        if not _curve_has_points(curve):
            continue
        tier = contract.get(channel)
        path = f"{path_prefix}.{channel}"
        if tier is None:
            _append_property_error(
                errors,
                code="UNCONTRACTED_RUNTIME_CURVE",
                layer_id=layer_id,
                path=path,
                message=(
                    f"Layer '{layer_id}' ({layer_type}) uses curve '{channel}' "
                    "which has no declared runtime behavior."
                ),
            )
            continue
        if tier == "unsupported":
            _append_property_error(
                errors,
                code="UNSUPPORTED_RUNTIME_CURVE",
                layer_id=layer_id,
                path=path,
                message=f"Layer '{layer_id}' uses unsupported runtime curve '{channel}'.",
                tier=tier,
                supported=sorted(contract),
            )


def _contract_export(layer_type: str, contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "properties": dict(sorted(contract.get("properties", {}).items())),
        "property_defaults": dict(sorted(contract.get("property_defaults", {}).items())),
        "curves": dict(sorted(contract.get("curves", {}).items())),
        "material": dict(sorted(MATERIAL_COMMON.items())),
        "material_defaults": dict(sorted(MATERIAL_DEFAULTS.items())),
    }


def runtime_capability_contract() -> dict[str, Any]:
    runtime_hashes: dict[str, str] = {}
    try:
        runtime = godot_runtime_dir()
        for name in ("vfx_runtime.gd", "vfx_trail.gd"):
            path = runtime / name
            if path.is_file():
                runtime_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        pass
    layers: dict[str, Any] = {}
    for layer_type in sorted(LAYER_CONTRACTS):
        resolved = _resolved_layer_contract(layer_type)
        if resolved is not None and "inherits" not in LAYER_CONTRACTS[layer_type]:
            layers[layer_type] = _contract_export(layer_type, resolved)
    return {
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "layers": layers,
        "runtime_scripts": sorted(runtime_hashes.keys()),
    }


def validate_runtime_conformance(document: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    layers = document.get("layers")
    if not isinstance(layers, list):
        return errors
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        if not bool(layer.get("enabled", True)):
            continue
        layer_id = str(layer.get("id", "unknown"))
        layer_type = str(layer.get("type", ""))
        contract = _resolved_layer_contract(layer_type)
        if contract is None:
            _append_property_error(
                errors,
                code="UNCONTRACTED_RUNTIME_LAYER",
                layer_id=layer_id,
                path=f"layers.{layer_id}.type",
                message=f"Layer type '{layer_type}' has no runtime conformance contract.",
            )
            continue
        properties = layer.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        material = layer.get("material", {})
        if not isinstance(material, dict):
            material = {}
        if layer_type in {"particle", "mesh_particle"}:
            shape = str(properties.get("emission_shape", "point"))
            if shape not in PARTICLE_EMISSION_SHAPES:
                _append_property_error(
                    errors,
                    code="UNSUPPORTED_RUNTIME_EMISSION_SHAPE",
                    layer_id=layer_id,
                    path=f"layers.{layer_id}.properties.emission_shape",
                    message=(
                        f"Layer '{layer_id}' uses emission shape '{shape}' "
                        "which the Godot runtime does not implement."
                    ),
                    supported=sorted(PARTICLE_EMISSION_SHAPES),
                )
        _validate_property_map(
            errors,
            layer_id=layer_id,
            layer_type=layer_type,
            values=properties,
            contract=contract.get("properties", {}),
            defaults=contract.get("property_defaults", {}),
            path_prefix=f"layers.{layer_id}.properties",
            unknown_code="UNCONTRACTED_RUNTIME_PROPERTY",
            unsupported_code="UNSUPPORTED_RUNTIME_PROPERTY",
        )
        _validate_property_map(
            errors,
            layer_id=layer_id,
            layer_type=layer_type,
            values=material,
            contract=MATERIAL_COMMON,
            defaults=MATERIAL_DEFAULTS,
            path_prefix=f"layers.{layer_id}.material",
            unknown_code="UNCONTRACTED_RUNTIME_MATERIAL",
            unsupported_code="UNSUPPORTED_RUNTIME_MATERIAL",
        )
        curves = layer.get("curves", {})
        if isinstance(curves, dict):
            _validate_curve_map(
                errors,
                layer_id=layer_id,
                layer_type=layer_type,
                curves=curves,
                contract=contract.get("curves", {}),
                path_prefix=f"layers.{layer_id}.curves",
            )
    return errors
