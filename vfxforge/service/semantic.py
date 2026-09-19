"""Recipe/request semantic contract validation."""

from __future__ import annotations

from typing import Any

from .request import request_lookup_path


SEMANTIC_ROLES = frozenset({
    "warning_geometry",
    "warning_visual",
    "warning_duration",
    "resolve_event",
    "resolve_visual",
    "gameplay_footprint",
})


def _review(code: str, message: str, **extra: Any) -> dict[str, Any]:
    item = {"code": code, "message": message}
    item.update(extra)
    return item


def layer_semantic_roles(recipe: dict[str, Any]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for entry in recipe.get("layer_roles", []):
        if not isinstance(entry, dict) or not entry.get("id"):
            continue
        role = entry.get("semantic_role")
        if isinstance(role, str) and role in SEMANTIC_ROLES:
            roles[str(entry["id"])] = role
    timing = recipe.get("timing", {})
    for layer_id in timing.get("resolve_layer_ids", []):
        if isinstance(layer_id, str):
            roles.setdefault(layer_id, "resolve_visual")
    for layer_id in timing.get("warning_layer_ids", []):
        if isinstance(layer_id, str):
            roles.setdefault(layer_id, "warning_visual")
    return roles


def protected_document_paths(recipe: dict[str, Any] | None, document: dict[str, Any] | None = None) -> set[str]:
    protected: set[str] = {"duration"}
    if document is not None:
        protected.add("timeline.events")
        for event in document.get("timeline", {}).get("events", []):
            if isinstance(event, dict) and event.get("event_id"):
                protected.add(f"timeline.events.{event.get('event_id')}.time")
    if not recipe:
        return protected
    roles = layer_semantic_roles(recipe)
    for layer_id, role in roles.items():
        prefix = f"layers.{layer_id}"
        protected.add(f"{prefix}.enabled")
        protected.add(f"{prefix}.start")
        protected.add(f"{prefix}.duration")
        if role in {"warning_geometry", "gameplay_footprint"}:
            protected.update({f"{prefix}.properties.size", f"{prefix}.properties.emission_radius", f"{prefix}.properties.target"})
        if role == "resolve_event":
            protected.add(f"{prefix}.properties.event_id")
    return protected


def is_document_path_protected(path: str, protected: set[str]) -> bool:
    if path in protected:
        return True
    for candidate in protected:
        if path.startswith(candidate + "."):
            return True
    return False


def validate_recipe_semantics(request: dict[str, Any], recipe: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    required = recipe.get("required_gameplay", [])
    if isinstance(required, list):
        for dotted in required:
            if request_lookup_path(request, dotted) is None:
                reasons.append(_review("MISSING_REQUIRED_SEMANTIC", f"Recipe requires {dotted}.", path=dotted))
    supported = set(recipe.get("supported_gameplay", recipe.get("consumed_gameplay", [])) or [])
    consumed = set(recipe.get("consumed_gameplay", supported) or [])
    for key, value in request.get("gameplay", {}).items():
        if value is None:
            continue
        path = f"gameplay.{key}"
        if supported and path not in supported and path not in consumed:
            reasons.append(_review("UNSUPPORTED_SEMANTIC_PARAMETER", f"Recipe does not consume {path}.", path=path))
    bounds = policy.get("semantic_bounds", {})
    gameplay = request.get("gameplay", {})
    for key in ("radius_tiles", "width_tiles", "length_tiles"):
        if key not in gameplay:
            continue
        limit = bounds.get(key)
        if isinstance(limit, dict):
            value = float(gameplay[key])
            maximum = float(limit.get("max", 64))
            minimum = float(limit.get("min", 0.25))
            if value > maximum or value < minimum:
                reasons.append(_review("SEMANTIC_OUT_OF_BOUNDS", f"{key}={value} is outside policy bounds.", path=f"gameplay.{key}", value=value))
    tell_ms = gameplay.get("tell_ms")
    if tell_ms is not None:
        tell_bounds = bounds.get("tell_ms", {"min": 100, "max": 10000})
        if float(tell_ms) > float(tell_bounds.get("max", 10000)) or float(tell_ms) < float(tell_bounds.get("min", 100)):
            reasons.append(_review("SEMANTIC_OUT_OF_BOUNDS", f"tell_ms={tell_ms} is outside policy bounds.", path="gameplay.tell_ms", value=tell_ms))
    return reasons


def document_semantic_metrics(document: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {"duration_sec": float(document.get("duration", 0.0))}
    resolve_time = None
    for event in document.get("timeline", {}).get("events", []):
        if isinstance(event, dict) and event.get("event_id") in {"damage_frame", "resolve", "impact"}:
            resolve_time = float(event.get("time", 0.0))
            break
    metrics["resolve_time_sec"] = resolve_time
    layer_timings: dict[str, dict[str, float]] = {}
    for layer in document.get("layers", []):
        if not isinstance(layer, dict):
            continue
        layer_id = str(layer.get("id", ""))
        if layer_id:
            layer_timings[layer_id] = {
                "start": float(layer.get("start", 0.0)),
                "duration": float(layer.get("duration", 0.0)),
                "end": float(layer.get("start", 0.0)) + float(layer.get("duration", 0.0)),
            }
        if layer.get("type") != "decal":
            continue
        size = layer.get("properties", {}).get("size")
        if isinstance(size, list) and len(size) >= 2:
            metrics.setdefault("decal_sizes", []).append([float(size[0]), float(size[1])])
        if layer.get("id") in {"warning_line", "warning_rect", "warning_circle"}:
            metrics["primary_decal_size"] = [float(size[0]), float(size[1])] if isinstance(size, list) else None
    metrics["layer_timings"] = layer_timings
    for layer in document.get("layers", []):
        if isinstance(layer, dict) and layer.get("type") == "beam":
            target = layer.get("properties", {}).get("target")
            if isinstance(target, list) and len(target) >= 3:
                metrics["beam_length"] = abs(float(target[2]))
    return metrics
