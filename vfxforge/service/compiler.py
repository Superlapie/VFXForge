"""Compile a selected recipe and normalized request into a canonical document."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..schema import default_document
from .policy import allowed_budget_profile
from .request import TILE_SIZE, request_lookup_path


def _set_path(document: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    current: Any = document
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _scale_particle_amounts(document: dict[str, Any], factor: float) -> None:
    for layer in document.get("layers", []):
        if not isinstance(layer, dict):
            continue
        if layer.get("type") not in {"particle", "mesh_particle"}:
            continue
        properties = layer.setdefault("properties", {})
        amount = properties.get("amount")
        if isinstance(amount, int):
            properties["amount"] = max(1, int(round(amount * factor)))


def _apply_gameplay_scaling(document: dict[str, Any], request: dict[str, Any], recipe: dict[str, Any]) -> None:
    gameplay = request.get("gameplay", {})
    scaling = recipe.get("gameplay_scaling", {})
    shape = gameplay.get("shape")
    if shape == "circle" and "radius_tiles" in gameplay:
        radius = float(gameplay["radius_tiles"]) * TILE_SIZE
        size_factor = radius * 2.0
        target_layers = scaling.get("circle_size_layers", ["warning_circle", "circle"])
        for layer in document.get("layers", []):
            if not isinstance(layer, dict) or layer.get("id") not in target_layers:
                continue
            properties = layer.setdefault("properties", {})
            if "size" in properties and isinstance(properties["size"], list):
                properties["size"] = [size_factor, size_factor]
            if "emission_radius" in properties:
                properties["emission_radius"] = radius
    if shape == "rectangle" and "width_tiles" in gameplay and "length_tiles" in gameplay:
        width = float(gameplay["width_tiles"]) * TILE_SIZE
        length = float(gameplay["length_tiles"]) * TILE_SIZE
        for layer in document.get("layers", []):
            if not isinstance(layer, dict):
                continue
            properties = layer.setdefault("properties", {})
            if layer.get("type") == "decal" and "size" in properties:
                properties["size"] = [width, length]
    if shape == "line" and "length_tiles" in gameplay:
        length = float(gameplay["length_tiles"]) * TILE_SIZE
        width = float(gameplay.get("width_tiles", 1)) * TILE_SIZE
        for layer in document.get("layers", []):
            if not isinstance(layer, dict):
                continue
            properties = layer.setdefault("properties", {})
            if layer.get("type") == "decal" and "size" in properties:
                properties["size"] = [width, length]
            if layer.get("type") == "beam":
                properties["target"] = [0.0, 0.0, -length]
    tell_ms = gameplay.get("tell_ms")
    if tell_ms is not None:
        document["duration"] = max(float(tell_ms) / 1000.0, document.get("duration", 1.0))
    active_ms = gameplay.get("active_ms")
    if active_ms is not None and active_ms > 0:
        document["duration"] = max(float(active_ms) / 1000.0, document.get("duration", 1.0))
    duration_ms = gameplay.get("duration_ms")
    if duration_ms is not None and duration_ms > 0:
        document["duration"] = float(duration_ms) / 1000.0
    if "loop" in gameplay:
        document["loop"] = bool(gameplay["loop"])


def compile_recipe(
    request: dict[str, Any],
    recipe: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    blueprint = recipe.get("document")
    if not isinstance(blueprint, dict):
        raise ValueError(f"Recipe '{recipe.get('recipe_id')}' is missing a document blueprint.")
    document = deepcopy(blueprint)
    effect_id = request["effect_id"]
    document["schema_version"] = 1
    document["id"] = effect_id
    document["name"] = recipe.get("display_name") or effect_id.replace("_", " ").title()
    document["seed"] = int(request.get("seed", recipe.get("seed", 12345)))
    document.setdefault("export", {})
    document["export"]["folder_name"] = effect_id
    usage = request.get("context", {}).get("usage", "normal_combat")
    profile = allowed_budget_profile(policy, usage)
    document.setdefault("budgets", {})
    document["budgets"]["profile"] = profile
    intensity = request.get("intent", {}).get("intensity", "standard")
    scale_table = recipe.get("intensity_scale", {"subtle": 0.7, "standard": 1.0, "strong": 1.25, "boss": 1.5})
    factor = float(scale_table.get(intensity, 1.0))
    _scale_particle_amounts(document, factor)
    _apply_gameplay_scaling(document, request, recipe)
    for binding in recipe.get("bindings", []):
        if not isinstance(binding, dict):
            continue
        source = binding.get("from")
        target = binding.get("to")
        if source and target:
            value = request_lookup_path(request, source)
            if value is not None:
                _set_path(document, target, value)
    return document
