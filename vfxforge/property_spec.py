"""Authoritative typed property specifications for strict validation."""

from __future__ import annotations

from typing import Any

from .schema import COMMON_LAYER, LAYER_DEFAULTS, LAYER_TYPES, default_document


ROOT_KEYS = frozenset(default_document("_placeholder").keys())
DOCUMENT_OPTIONAL_KEYS = ROOT_KEYS - frozenset({"schema_version", "id", "name", "duration", "loop", "seed", "layers"})
LAYER_STRUCT_KEYS = frozenset({"id", "type", "name", "enabled", "start", "duration", "properties", "material", "curves", "gradient"})


OPTIONAL_VISUAL_PROPERTIES = frozenset({"color"})
VISUAL_LAYER_TYPES_WITH_COLOR = frozenset({
    "particle", "mesh_particle", "sprite", "trail", "beam", "light", "decal", "mesh_effect",
})


def layer_property_keys(layer_type: str) -> frozenset[str]:
    defaults = LAYER_DEFAULTS.get(layer_type, {})
    keys = frozenset(defaults.get("properties", {}).keys())
    if layer_type in VISUAL_LAYER_TYPES_WITH_COLOR:
        keys = keys | OPTIONAL_VISUAL_PROPERTIES
    return keys


def layer_material_keys() -> frozenset[str]:
    return frozenset(COMMON_LAYER["material"].keys())


def layer_curve_keys(layer_type: str) -> frozenset[str]:
    defaults = LAYER_DEFAULTS.get(layer_type, {})
    return frozenset(defaults.get("curves", {}).keys())


def all_layer_types() -> tuple[str, ...]:
    return LAYER_TYPES


def describe_property_registry() -> dict[str, Any]:
    layers = {}
    for layer_type in LAYER_TYPES:
        layers[layer_type] = {
            "properties": sorted(layer_property_keys(layer_type)),
            "material": sorted(layer_material_keys()),
            "curves": sorted(layer_curve_keys(layer_type)),
        }
    return {"root_keys": sorted(ROOT_KEYS), "layers": layers}
