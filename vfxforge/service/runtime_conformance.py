"""Validate compiled documents against the Godot runtime capability contract."""

from __future__ import annotations

import hashlib
from typing import Any

from ..property_spec import layer_curve_keys, layer_material_keys, layer_property_keys
from ..resources import godot_runtime_dir
from ..schema import BILLBOARD_MODES, BLEND_MODES, COMMON_LAYER, LAYER_DEFAULTS, LAYER_TYPES


RUNTIME_CONTRACT_VERSION = 6

PropertyTier = str  # implemented | emulated | inert_only | unsupported | host_bound

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

STANDARD_MATERIAL_DEFAULTS: dict[str, Any] = dict(COMMON_LAYER["material"])

MATERIAL_UNUSED: dict[str, PropertyTier] = {
    key: "inert_only" for key in STANDARD_MATERIAL_DEFAULTS
}

MATERIAL_DRAW_STANDARD: dict[str, PropertyTier] = {
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

MATERIAL_PARTICLE_DRAW: dict[str, PropertyTier] = {
    **MATERIAL_DRAW_STANDARD,
    "billboard": "emulated",
}

PROPERTY_TIER_OVERRIDES: dict[str, dict[str, PropertyTier]] = {
    "particle": {
        "turbulence": "inert_only",
        "attractor_strength": "inert_only",
        "attractor_position": "inert_only",
    },
    "mesh_particle": {
        "rotation_speed": "inert_only",
        "turbulence": "inert_only",
        "attractor_strength": "inert_only",
        "attractor_position": "inert_only",
    },
    "trail": {
        "target": "host_bound",
        "texture": "inert_only",
        "uv_mode": "inert_only",
    },
    "mesh_effect": {
        "dissolve": "inert_only",
    },
    "event_marker": {
        "payload": "emulated",
    },
    "sprite": {
        "random_start": "inert_only",
        "pixel_snap": "inert_only",
        "billboard": "inert_only",
    },
}

CURVE_TIER_OVERRIDES: dict[str, dict[str, PropertyTier]] = {
    "particle": {"velocity": "emulated"},
    "mesh_particle": {"velocity": "emulated"},
}

MATERIAL_TIER_OVERRIDES: dict[str, dict[str, PropertyTier]] = {
    "particle": MATERIAL_PARTICLE_DRAW,
    "mesh_particle": MATERIAL_PARTICLE_DRAW,
    "trail": MATERIAL_UNUSED,
    "light": MATERIAL_UNUSED,
    "event_marker": MATERIAL_UNUSED,
    "sprite": MATERIAL_DRAW_STANDARD,
    "mesh_effect": MATERIAL_DRAW_STANDARD,
    "decal": MATERIAL_DRAW_STANDARD,
    "beam": MATERIAL_DRAW_STANDARD,
}

RUNTIME_PRODUCTION_LAYER_TYPES = frozenset(MATERIAL_TIER_OVERRIDES)
SCHEMA_ONLY_LAYER_TYPES = frozenset(LAYER_TYPES) - RUNTIME_PRODUCTION_LAYER_TYPES


def _property_default(layer_type: str, key: str) -> Any:
    properties = LAYER_DEFAULTS[layer_type]["properties"]
    if key in properties:
        return properties[key]
    if key == "color":
        return ""
    return None


def _build_property_contract(layer_type: str) -> tuple[dict[str, PropertyTier], dict[str, Any]]:
    tiers: dict[str, PropertyTier] = {}
    defaults: dict[str, Any] = {}
    overrides = PROPERTY_TIER_OVERRIDES.get(layer_type, {})
    for key in sorted(layer_property_keys(layer_type)):
        tier = overrides.get(key, "implemented")
        tiers[key] = tier
        if tier in {"inert_only", "host_bound"} or key in LAYER_DEFAULTS[layer_type]["properties"]:
            defaults[key] = _property_default(layer_type, key)
    return tiers, defaults


def _build_curve_contract(layer_type: str) -> tuple[dict[str, PropertyTier], dict[str, Any]]:
    tiers: dict[str, PropertyTier] = {}
    defaults: dict[str, Any] = {}
    overrides = CURVE_TIER_OVERRIDES.get(layer_type, {})
    for key in sorted(layer_curve_keys(layer_type)):
        tier = overrides.get(key, "implemented")
        tiers[key] = tier
        if key in LAYER_DEFAULTS[layer_type]["curves"]:
            defaults[key] = LAYER_DEFAULTS[layer_type]["curves"][key]
    return tiers, defaults


def _build_material_contract(layer_type: str) -> tuple[dict[str, PropertyTier], dict[str, Any]]:
    tiers = dict(MATERIAL_TIER_OVERRIDES[layer_type])
    defaults = dict(STANDARD_MATERIAL_DEFAULTS)
    return tiers, defaults


def _build_layer_contracts() -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for layer_type in sorted(RUNTIME_PRODUCTION_LAYER_TYPES):
        properties, property_defaults = _build_property_contract(layer_type)
        curves, curve_defaults = _build_curve_contract(layer_type)
        material, material_defaults = _build_material_contract(layer_type)
        contracts[layer_type] = {
            "properties": properties,
            "property_defaults": property_defaults,
            "curves": curves,
            "curve_defaults": curve_defaults,
            "material": material,
            "material_defaults": material_defaults,
        }
    return contracts


LAYER_CONTRACTS = _build_layer_contracts()


def _resolved_layer_contract(layer_type: str) -> dict[str, Any] | None:
    return LAYER_CONTRACTS.get(layer_type)


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


def _validate_enum_field(
    errors: list[dict[str, Any]],
    *,
    layer_id: str,
    path: str,
    key: str,
    value: Any,
    allowed: tuple[str, ...],
    tier: PropertyTier,
    unsupported_code: str,
) -> None:
    if key == "billboard" and str(value) not in allowed:
        _append_property_error(
            errors,
            code=unsupported_code,
            layer_id=layer_id,
            path=path,
            message=f"Layer '{layer_id}' uses unsupported billboard mode '{value}'.",
            tier=tier,
            supported=list(allowed),
        )
    if key == "blend_mode" and str(value) not in allowed:
        _append_property_error(
            errors,
            code=unsupported_code,
            layer_id=layer_id,
            path=path,
            message=f"Layer '{layer_id}' uses unsupported blend mode '{value}'.",
            tier=tier,
            supported=list(allowed),
        )


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
        if key == "billboard":
            _validate_enum_field(
                errors,
                layer_id=layer_id,
                path=path,
                key=key,
                value=value,
                allowed=BILLBOARD_MODES,
                tier=tier,
                unsupported_code=unsupported_code,
            )
        if key == "blend_mode":
            _validate_enum_field(
                errors,
                layer_id=layer_id,
                path=path,
                key=key,
                value=value,
                allowed=BLEND_MODES,
                tier=tier,
                unsupported_code=unsupported_code,
            )
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
    authorable = sorted(layer_property_keys(layer_type))
    return {
        "schema_authorable_properties": authorable,
        "properties": dict(sorted(contract.get("properties", {}).items())),
        "property_defaults": dict(sorted(contract.get("property_defaults", {}).items())),
        "curves": dict(sorted(contract.get("curves", {}).items())),
        "material": dict(sorted(contract.get("material", {}).items())),
        "material_defaults": dict(sorted(contract.get("material_defaults", {}).items())),
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
        if resolved is not None:
            layers[layer_type] = _contract_export(layer_type, resolved)
    return {
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "property_tiers": [
            "implemented",
            "emulated",
            "inert_only",
            "host_bound",
            "unsupported",
        ],
        "schema_layer_types": list(LAYER_TYPES),
        "runtime_production_layer_types": sorted(RUNTIME_PRODUCTION_LAYER_TYPES),
        "schema_only_layer_types": sorted(SCHEMA_ONLY_LAYER_TYPES),
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
        if layer_type == "mesh_particle":
            defaults = contract.get("property_defaults", {})
            mesh_asset = str(properties.get("mesh_asset", defaults.get("mesh_asset", "")))
            if mesh_asset:
                for key in ("mesh", "size"):
                    if key in properties and not _is_default_value(properties.get(key), defaults.get(key)):
                        _append_property_error(
                            errors,
                            code="UNSUPPORTED_RUNTIME_PROPERTY",
                            layer_id=layer_id,
                            path=f"layers.{layer_id}.properties.{key}",
                            message=(
                                f"Layer '{layer_id}' property '{key}' is inactive when mesh_asset is set; "
                                "runtime uses the imported mesh without primitive selector or size scaling."
                            ),
                            tier="conditional",
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
            contract=contract.get("material", {}),
            defaults=contract.get("material_defaults", {}),
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
