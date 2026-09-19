"""Compile a selected recipe and normalized request into a canonical document."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..errors import RecipeBindingError
from .policy import allowed_budget_profile, world_units_per_tile
from .request import request_lookup_path
from .semantic import layer_semantic_roles


def _mark_consumed(ledger: dict[str, Any], path: str, handler: str, applied: bool) -> None:
    entry = ledger.setdefault(path, {"declared_consumed": False, "handlers": [], "verified": False})
    entry["handlers"].append({"target": handler, "applied": applied})
    if applied:
        entry["verified"] = True


def _set_path(document: dict[str, Any], dotted: str, value: Any) -> bool:
    parts = dotted.split(".")
    if parts and parts[0] == "layers" and len(parts) >= 3:
        layer_id = parts[1]
        for layer in document.get("layers", []):
            if isinstance(layer, dict) and str(layer.get("id")) == layer_id:
                current: Any = layer
                for part in parts[2:-1]:
                    if not isinstance(current, dict):
                        raise RecipeBindingError(
                            f"Recipe binding target is not an object: {dotted}",
                            "RECIPE_BINDING_TARGET_MISSING",
                            dotted,
                        )
                    if part not in current or not isinstance(current[part], dict):
                        current[part] = {}
                    current = current[part]
                if not isinstance(current, dict):
                    raise RecipeBindingError(
                        f"Recipe binding target is not an object: {dotted}",
                        "RECIPE_BINDING_TARGET_MISSING",
                        dotted,
                    )
                current[parts[-1]] = value
                return True
        raise RecipeBindingError(
            f"Recipe binding target layer does not exist: {dotted}",
            "RECIPE_BINDING_TARGET_MISSING",
            dotted,
        )
    current: Any = document
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value
    return True


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


def _layer_ids(document: dict[str, Any]) -> set[str]:
    return {str(layer.get("id")) for layer in document.get("layers", []) if isinstance(layer, dict) and layer.get("id")}


def _remove_layers(document: dict[str, Any], layer_ids: set[str]) -> None:
    if not layer_ids:
        return
    document["layers"] = [layer for layer in document.get("layers", []) if not isinstance(layer, dict) or str(layer.get("id")) not in layer_ids]


def _apply_shape_scaling(
    document: dict[str, Any],
    request: dict[str, Any],
    recipe: dict[str, Any],
    tile_meters: float,
    ledger: dict[str, Any] | None = None,
) -> None:
    gameplay = request.get("gameplay", {})
    scaling = recipe.get("gameplay_scaling", {})
    shape = gameplay.get("shape")
    remove_for_shape = scaling.get("remove_layers_for_shape", {})
    if isinstance(remove_for_shape, dict) and shape in remove_for_shape:
        _remove_layers(document, set(remove_for_shape.get(shape, [])))
        if ledger is not None:
            _mark_consumed(ledger, "gameplay.shape", "gameplay_scaling.remove_layers_for_shape", True)
    if shape == "circle" and "radius_tiles" in gameplay:
        radius = float(gameplay["radius_tiles"]) * tile_meters
        size_factor = radius * 2.0
        target_layers = scaling.get("circle_size_layers", ["warning_circle", "circle"])
        applied = False
        for layer in document.get("layers", []):
            if not isinstance(layer, dict) or layer.get("id") not in target_layers:
                continue
            properties = layer.setdefault("properties", {})
            if "size" in properties and isinstance(properties["size"], list):
                properties["size"] = [size_factor, size_factor]
                applied = True
            if "emission_radius" in properties:
                properties["emission_radius"] = radius
                applied = True
        if ledger is not None:
            _mark_consumed(ledger, "gameplay.shape", "gameplay_scaling.circle", applied)
            _mark_consumed(ledger, "gameplay.radius_tiles", "gameplay_scaling.circle", applied)
    if shape == "rectangle" and "width_tiles" in gameplay and "length_tiles" in gameplay:
        width = float(gameplay["width_tiles"]) * tile_meters
        length = float(gameplay["length_tiles"]) * tile_meters
        target_layers = scaling.get("rectangle_size_layers", ["warning_rect", "warning_circle"])
        applied = False
        for layer in document.get("layers", []):
            if not isinstance(layer, dict) or layer.get("id") not in target_layers:
                continue
            properties = layer.setdefault("properties", {})
            if layer.get("type") == "decal" and "size" in properties:
                properties["size"] = [width, length]
                applied = True
        if ledger is not None:
            _mark_consumed(ledger, "gameplay.shape", "gameplay_scaling.rectangle", applied)
            _mark_consumed(ledger, "gameplay.width_tiles", "gameplay_scaling.rectangle", applied)
            _mark_consumed(ledger, "gameplay.length_tiles", "gameplay_scaling.rectangle", applied)
    if shape == "line" and "length_tiles" in gameplay:
        length = float(gameplay["length_tiles"]) * tile_meters
        width = float(gameplay.get("width_tiles", 1)) * tile_meters
        target_layers = scaling.get("line_size_layers", ["warning_line"])
        applied = False
        for layer in document.get("layers", []):
            if not isinstance(layer, dict):
                continue
            properties = layer.setdefault("properties", {})
            if layer.get("id") in target_layers and layer.get("type") == "decal" and "size" in properties:
                properties["size"] = [width, length]
                applied = True
            if layer.get("type") == "beam":
                properties["target"] = [0.0, 0.0, -length]
                properties["thickness"] = max(width * 0.35, properties.get("thickness", 0.12))
                applied = True
        if ledger is not None:
            _mark_consumed(ledger, "gameplay.shape", "gameplay_scaling.line", applied)
            _mark_consumed(ledger, "gameplay.length_tiles", "gameplay_scaling.line", applied)
            if "width_tiles" in gameplay:
                _mark_consumed(ledger, "gameplay.width_tiles", "gameplay_scaling.line", applied)


def _apply_tell_timing(
    document: dict[str, Any],
    request: dict[str, Any],
    recipe: dict[str, Any],
    ledger: dict[str, Any] | None = None,
) -> None:
    gameplay = request.get("gameplay", {})
    tell_ms = gameplay.get("tell_ms")
    if tell_ms is None:
        active_ms = gameplay.get("active_ms")
        duration_ms = gameplay.get("duration_ms")
        if active_ms is not None:
            document["duration"] = float(active_ms) / 1000.0
            if ledger is not None:
                _mark_consumed(ledger, "gameplay.active_ms", "timing.active_ms", True)
        elif duration_ms is not None:
            document["duration"] = float(duration_ms) / 1000.0
            if ledger is not None:
                _mark_consumed(ledger, "gameplay.duration_ms", "timing.duration_ms", True)
        if "loop" in gameplay:
            document["loop"] = bool(gameplay["loop"])
            if ledger is not None:
                _mark_consumed(ledger, "gameplay.loop", "timing.loop", True)
        return
    tell_sec = float(tell_ms) / 1000.0
    timing = recipe.get("timing", {})
    post_resolve = float(timing.get("post_resolve_sec", 0.0))
    document["duration"] = tell_sec + post_resolve
    if ledger is not None:
        _mark_consumed(ledger, "gameplay.tell_ms", "timing.tell_ms", True)
    resolve_event_id = str(timing.get("resolve_event_id", "damage_frame"))
    warning_end = tell_sec
    roles = layer_semantic_roles(recipe)
    resolve_visual_ids = {layer_id for layer_id, role in roles.items() if role == "resolve_visual"}
    resolve_visual_ids.update(str(item) for item in timing.get("resolve_layer_ids", []) if isinstance(item, str))
    resolve_event_ids = {layer_id for layer_id, role in roles.items() if role == "resolve_event"}
    for layer in document.get("layers", []):
        if not isinstance(layer, dict):
            continue
        layer_id = str(layer.get("id", ""))
        if layer_id in resolve_visual_ids:
            layer["enabled"] = True
            layer["start"] = tell_sec
            layer["duration"] = max(0.001, post_resolve if post_resolve > 0 else document["duration"] - tell_sec)
            continue
        if layer.get("type") == "event_marker" or layer_id in resolve_event_ids:
            continue
        start = float(layer.get("start", 0.0))
        if start >= warning_end:
            layer["enabled"] = False
            continue
        layer["duration"] = max(0.001, warning_end - start)
    events = document.setdefault("timeline", {}).setdefault("events", [])
    matched = False
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("event_id") in {resolve_event_id, "damage_frame", "resolve"}:
            event["time"] = tell_sec
            matched = True
    if not matched:
        events.append({"id": resolve_event_id, "event_id": resolve_event_id, "time": tell_sec, "data": {"presentation": True}})
    events.sort(key=lambda item: float(item.get("time", 0.0)))
    for layer in document.get("layers", []):
        if not isinstance(layer, dict) or layer.get("type") != "event_marker":
            continue
        properties = layer.setdefault("properties", {})
        marker_id = str(properties.get("event_id", layer.get("id", "resolve")))
        if marker_id in {resolve_event_id, "damage_frame", "resolve", "impact"} or str(layer.get("id", "")) in resolve_event_ids:
            layer["start"] = tell_sec
            layer["duration"] = 0.001
    if "loop" in gameplay:
        document["loop"] = bool(gameplay["loop"])
        if ledger is not None:
            _mark_consumed(ledger, "gameplay.loop", "timing.loop", True)


def _apply_loop_coverage(document: dict[str, Any], recipe: dict[str, Any], ledger: dict[str, Any] | None = None) -> None:
    if not document.get("loop"):
        return
    duration = float(document.get("duration", 1.0))
    applied = False
    for layer in document.get("layers", []):
        if not isinstance(layer, dict) or not layer.get("enabled", True):
            continue
        if layer.get("type") in {"particle", "mesh_particle"}:
            properties = layer.setdefault("properties", {})
            properties["one_shot"] = False
            properties["lifetime"] = max(float(properties.get("lifetime", 1.0)), duration * 0.85)
            layer["duration"] = duration
            applied = True
        elif layer.get("type") in {"decal", "mesh_effect", "sprite", "trail", "beam"}:
            layer["duration"] = duration
            applied = True
    if ledger is not None and applied:
        _mark_consumed(ledger, "gameplay.loop", "loop_coverage", True)


def compile_recipe_with_ledger(
    request: dict[str, Any],
    recipe: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
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
    tile_meters = world_units_per_tile(policy, usage)
    ledger: dict[str, Any] = {}
    for path in recipe.get("consumed_gameplay") or []:
        if isinstance(path, str):
            ledger[path] = {"declared_consumed": True, "handlers": [], "verified": False}
    _apply_shape_scaling(document, request, recipe, tile_meters, ledger)
    _apply_tell_timing(document, request, recipe, ledger)
    _apply_loop_coverage(document, recipe, ledger)
    for binding in recipe.get("bindings", []):
        if not isinstance(binding, dict):
            continue
        source = binding.get("from")
        target = binding.get("to")
        if source and target:
            value = request_lookup_path(request, source)
            if value is not None:
                applied = _set_path(document, target, value)
                _mark_consumed(ledger, str(source), str(target), applied)
    return document, ledger


def unconsumed_semantics(request: dict[str, Any], recipe: dict[str, Any], ledger: dict[str, Any]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    consumed = {str(item) for item in (recipe.get("consumed_gameplay") or []) if isinstance(item, str)}
    for key, value in request.get("gameplay", {}).items():
        if value is None:
            continue
        path = f"gameplay.{key}"
        if path not in consumed:
            continue
        entry = ledger.get(path) or {}
        if not entry.get("verified"):
            reasons.append({
                "code": "SEMANTIC_NOT_CONSUMED",
                "message": f"Recipe declared {path} as consumed but compilation did not apply it.",
                "path": path,
                "consumption": entry,
            })
    return reasons


def compile_recipe(
    request: dict[str, Any],
    recipe: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    document, _ledger = compile_recipe_with_ledger(request, recipe, policy)
    return document
