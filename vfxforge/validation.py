"""First-class validation for documents, dependencies, and performance budgets."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Iterable

from .model import finite_number, is_stable_id, read_document
from .property_spec import LAYER_STRUCT_KEYS, ROOT_KEYS, layer_curve_keys, layer_material_keys, layer_property_keys
from .schema import BLEND_MODES, BUDGET_PROFILES, EMISSION_SHAPES, LAYER_TYPES, MESH_ASSET_EXTENSIONS


HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
VISUAL_LAYER_TYPES = {"particle", "mesh_particle", "sprite", "light", "trail", "beam", "decal", "mesh_effect"}


def issue(
    severity: str,
    code: str,
    path: str,
    message: str,
    suggestion: str | None = None,
    value: Any = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "path": path,
        "message": message,
    }
    if suggestion:
        result["suggestion"] = suggestion
    if value is not None:
        result["value"] = value
    return result


def _number(
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    value: Any,
    path: str,
    minimum: float | None = None,
    maximum: float | None = None,
    required: bool = False,
) -> bool:
    if not finite_number(value):
        (errors if required else warnings).append(
            issue(
                "error" if required else "warning",
                "INVALID_NUMBER",
                path,
                "Expected a finite number.",
                "Use a JSON number such as 0.5.",
                value,
            )
        )
        return False
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        errors.append(issue("error", "NUMBER_TOO_SMALL", path, f"Value must be at least {minimum}.", value=value))
        return False
    if maximum is not None and numeric > maximum:
        errors.append(issue("error", "NUMBER_TOO_LARGE", path, f"Value must be at most {maximum}.", value=value))
        return False
    return True


def _vector(value: Any, path: str, size: int, errors: list[dict[str, Any]]) -> None:
    if not isinstance(value, list) or len(value) != size or not all(finite_number(item) for item in value):
        errors.append(
            issue(
                "error",
                "INVALID_VECTOR",
                path,
                f"Expected an array of {size} finite numbers.",
                value=value,
            )
        )


def _validate_curve(value: Any, path: str, errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("points"), list):
        errors.append(issue("error", "INVALID_CURVE", path, "A curve must contain a points array."))
        return
    previous_x = -math.inf
    for index, point in enumerate(value["points"]):
        point_path = f"{path}.points[{index}]"
        if not isinstance(point, dict):
            errors.append(issue("error", "INVALID_CURVE_POINT", point_path, "Curve points must be objects."))
            continue
        if not _number(errors, warnings, point.get("x"), f"{point_path}.x", 0.0, 1.0, True):
            continue
        _number(errors, warnings, point.get("y"), f"{point_path}.y", None, None, True)
        x = float(point["x"])
        if x < previous_x:
            errors.append(
                issue(
                    "error",
                    "CURVE_NOT_SORTED",
                    point_path,
                    "Curve points must be sorted by x.",
                    "Sort points from 0 to 1.",
                )
            )
        previous_x = x
    if len(value["points"]) == 0:
        warnings.append(issue("warning", "EMPTY_CURVE", path, "The curve has no points and will evaluate to zero."))


def _validate_gradient(value: Any, path: str, errors: list[dict[str, Any]]) -> None:
    if not isinstance(value, list):
        errors.append(issue("error", "INVALID_GRADIENT", path, "A gradient must be an array of stops."))
        return
    previous = -math.inf
    for index, stop in enumerate(value):
        stop_path = f"{path}[{index}]"
        if not isinstance(stop, dict):
            errors.append(issue("error", "INVALID_GRADIENT_STOP", stop_path, "Gradient stops must be objects."))
            continue
        position = stop.get("position")
        if not finite_number(position) or not 0.0 <= float(position) <= 1.0:
            errors.append(issue("error", "INVALID_GRADIENT_POSITION", f"{stop_path}.position", "Stop position must be between 0 and 1.", value=position))
        elif float(position) < previous:
            errors.append(issue("error", "GRADIENT_NOT_SORTED", stop_path, "Gradient stops must be sorted by position."))
        previous = float(position) if finite_number(position) else previous
        color = stop.get("color")
        if not isinstance(color, str) or not HEX_COLOR.fullmatch(color):
            errors.append(
                issue(
                    "error",
                    "INVALID_COLOR",
                    f"{stop_path}.color",
                    "Colors must use #RRGGBB or #RRGGBBAA.",
                    value=color,
                )
            )


def _check_texture_ref(
    reference: Any,
    path: str,
    project_dir: Path | None,
    errors: list[dict[str, Any]],
    *,
    max_dimension: int | None = None,
    require_inspectable: bool = False,
) -> None:
    if not reference:
        return
    if not isinstance(reference, str):
        errors.append(issue("error", "INVALID_TEXTURE_REFERENCE", path, "Texture references must be relative path strings.", value=reference))
        return
    if project_dir is None:
        return
    relative_reference = reference.removeprefix("res://")
    resolved = (project_dir / relative_reference).resolve()
    try:
        resolved.relative_to(project_dir.resolve())
    except ValueError:
        errors.append(issue("error", "TEXTURE_OUTSIDE_PROJECT", path, "Texture reference escapes the project directory.", value=reference))
        return
    if not resolved.exists():
        errors.append(
            issue(
                "error",
                "MISSING_TEXTURE",
                path,
                f"Referenced texture does not exist: {reference}",
                "Import the texture with vfxforge add-texture or correct the relative path.",
                reference,
            )
        )
        return
    if max_dimension is None:
        return
    try:
        from PIL import Image

        with Image.open(resolved) as image:
            width, height = image.size
    except Exception:
        if require_inspectable:
            errors.append(
                issue(
                    "error",
                    "TEXTURE_DIMENSION_UNVERIFIED",
                    path,
                    "Texture dimensions could not be inspected for policy enforcement.",
                    value=reference,
                )
            )
        return
    if max(width, height) > max_dimension:
        errors.append(
            issue(
                "error",
                "TEXTURE_DIMENSION_EXCEEDED",
                path,
                f"Texture dimensions {width}x{height} exceed policy maximum {max_dimension}.",
                value=reference,
            )
        )


def _check_mesh_ref(
    reference: Any,
    path: str,
    project_dir: Path | None,
    errors: list[dict[str, Any]],
) -> None:
    """Validate a project-relative Godot-importable 3D mesh asset reference."""
    if not isinstance(reference, str) or not reference:
        errors.append(
            issue(
                "error",
                "INVALID_MESH_REFERENCE",
                path,
                "Mesh references must be non-empty relative path strings.",
                "Use a project-relative .obj, .glb, or .gltf path.",
                reference,
            )
        )
        return
    relative_reference = reference.removeprefix("res://")
    suffix = Path(relative_reference).suffix.lower()
    if suffix not in MESH_ASSET_EXTENSIONS:
        errors.append(
            issue(
                "error",
                "UNSUPPORTED_MESH_FORMAT",
                path,
                f"Unsupported mesh format '{suffix or '<none>'}'.",
                "Use an .obj, .glb, or .gltf model that Godot 4 can import.",
                reference,
            )
        )
        return
    if project_dir is None:
        return
    resolved = (project_dir / relative_reference).resolve()
    try:
        resolved.relative_to(project_dir.resolve())
    except ValueError:
        errors.append(issue("error", "MESH_OUTSIDE_PROJECT", path, "Mesh reference escapes the project directory.", value=reference))
        return
    if not resolved.exists() or not resolved.is_file():
        errors.append(
            issue(
                "error",
                "MISSING_MESH",
                path,
                f"Referenced mesh does not exist: {reference}",
                "Add the model to the project asset library or correct the relative path.",
                reference,
            )
        )


def _effect_reference(layer: dict[str, Any]) -> str | None:
    if layer.get("type") != "child_effect":
        return None
    properties = layer.get("properties", {})
    if not isinstance(properties, dict):
        return None
    value = properties.get("effect_id", "")
    return value if isinstance(value, str) and value else None


def _resolve_effect(reference: str, project_dir: Path) -> Path | None:
    candidate = (project_dir / reference).resolve()
    if candidate.exists() and candidate.is_file():
        return candidate
    if candidate.suffix == "":
        candidate = candidate.with_suffix(".vfx.json")
    if candidate.exists() and candidate.is_file():
        return candidate
    by_id = sorted(project_dir.rglob("*.vfx.json"))
    for path in by_id:
        try:
            document = read_document(path)
        except Exception:
            continue
        if document.get("id") == reference:
            return path
    return None


def detect_dependency_cycles(document: dict[str, Any], project_dir: Path | None) -> list[dict[str, Any]]:
    if project_dir is None:
        return []
    root_id = str(document.get("id", "<missing>"))
    seen: set[Path] = set()
    stack: list[str] = [root_id]
    cycles: list[dict[str, Any]] = []

    def visit(current: dict[str, Any], current_path: Path | None) -> None:
        current_dir = current_path.parent if current_path else project_dir
        for layer in current.get("layers", []):
            if not isinstance(layer, dict):
                continue
            reference = _effect_reference(layer)
            if not reference:
                continue
            child_path = _resolve_effect(reference, current_dir)
            if child_path is None:
                continue
            if child_path in seen:
                continue
            try:
                child = read_document(child_path)
            except Exception:
                continue
            child_id = str(child.get("id", reference))
            if child_id in stack:
                cycles.append(
                    issue(
                        "error",
                        "CHILD_EFFECT_CYCLE",
                        f"layers.{layer.get('id', '<missing>')}.properties.effect_id",
                        f"Child-effect dependency cycle detected: {' -> '.join(stack + [child_id])}.",
                        "Break the cycle or use an event marker instead.",
                        reference,
                    )
                )
                continue
            seen.add(child_path)
            stack.append(child_id)
            visit(child, child_path)
            stack.pop()

    visit(document, None)
    return cycles


def _max_child_effect_depth(document: dict[str, Any], project_dir: Path | None, current_depth: int = 0, stack: list[str] | None = None) -> int:
    if project_dir is None:
        return current_depth
    stack = list(stack or [str(document.get("id", "<missing>"))])
    maximum = current_depth
    current_dir = project_dir
    for layer in document.get("layers", []):
        if not isinstance(layer, dict):
            continue
        reference = _effect_reference(layer)
        if not reference:
            continue
        child_path = _resolve_effect(reference, current_dir)
        if child_path is None:
            continue
        try:
            child = read_document(child_path)
        except Exception:
            continue
        child_id = str(child.get("id", reference))
        if child_id in stack:
            continue
        maximum = max(maximum, _max_child_effect_depth(child, child_path.parent, current_depth + 1, stack + [child_id]))
    return maximum


def estimate_metrics(document: dict[str, Any], project_dir: Path | None = None) -> dict[str, Any]:
    particles = 0
    lights = 0
    draw_calls = 0
    overdraw_layers = 0
    triangles = 0
    texture_references: set[str] = set()
    for layer in document.get("layers", []):
        if not isinstance(layer, dict) or not layer.get("enabled", True):
            continue
        layer_type = layer.get("type")
        properties = layer.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        material = layer.get("material", {})
        if not isinstance(material, dict):
            material = {}
        if layer_type in {"particle", "mesh_particle"}:
            particles += int(properties.get("amount", 0)) if isinstance(properties.get("amount", 0), int) else 0
            draw_calls += 1
            triangles += int(properties.get("amount", 0)) * (2 if layer_type == "particle" else 12)
        elif layer_type == "light":
            lights += 1
            draw_calls += 1
        elif layer_type in VISUAL_LAYER_TYPES:
            draw_calls += 1
            triangles += 2 if layer_type in {"sprite", "decal", "beam", "trail"} else 24
        if layer_type in {"particle", "mesh_particle", "sprite", "trail", "beam", "decal"}:
            blend = material.get("blend_mode", "additive")
            if blend in {"additive", "alpha", "premultiplied"}:
                overdraw_layers += 1
        for container in (properties, material):
            if isinstance(container, dict) and isinstance(container.get("texture"), str) and container.get("texture"):
                texture_references.add(container["texture"])
    dependencies = document.get("dependencies", {})
    if isinstance(dependencies, dict):
        texture_references.update(reference for reference in dependencies.get("textures", []) if isinstance(reference, str))
    texture_bytes = 0
    if project_dir is not None:
        for reference in texture_references:
            candidate = (project_dir / reference.removeprefix("res://")).resolve()
            if candidate.exists() and candidate.is_file():
                texture_bytes += candidate.stat().st_size
    return {
        "active_particles_estimate": particles,
        "peak_particles_estimate": particles,
        "lights": lights,
        "draw_calls_estimate": draw_calls,
        "triangles_estimate": triangles,
        "texture_memory_estimate_bytes": texture_bytes,
        "overdraw_layers": overdraw_layers,
        "layer_count": len(document.get("layers", [])) if isinstance(document.get("layers"), list) else 0,
        "duration": document.get("duration"),
    }


def validate_document(
    document: dict[str, Any],
    project_dir: str | Path | None = None,
    selected_budget: str | None = None,
    strict: bool = False,
    policy_ceilings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return stable structured validation data; this function never raises for bad fields."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    root = document if isinstance(document, dict) else {}
    project = Path(project_dir).resolve() if project_dir is not None else None

    if strict and isinstance(root, dict):
        for key in root:
            if key not in ROOT_KEYS:
                errors.append(issue("error", "UNKNOWN_ROOT_FIELD", key, f"Unknown root field '{key}' is not allowed in strict mode.", value=key))

    if root.get("schema_version") != 1 or isinstance(root.get("schema_version"), bool):
        errors.append(issue("error", "INVALID_SCHEMA_VERSION", "schema_version", "schema_version must be 1.", value=root.get("schema_version")))
    if not is_stable_id(root.get("id")):
        errors.append(
            issue(
                "error",
                "MISSING_OR_INVALID_ID",
                "id",
                "The effect needs a stable ID matching [A-Za-z][A-Za-z0-9_-]{1,63}.",
                "Choose an ID such as arcane_impact.",
                root.get("id"),
            )
        )
    if not isinstance(root.get("name"), str) or not root.get("name", "").strip():
        errors.append(issue("error", "MISSING_NAME", "name", "The effect needs a non-empty display name."))
    _number(errors, warnings, root.get("duration"), "duration", 0.001, 3600.0, True)
    if not isinstance(root.get("loop"), bool):
        errors.append(issue("error", "INVALID_LOOP", "loop", "loop must be boolean.", value=root.get("loop")))
    if not isinstance(root.get("seed"), int) or isinstance(root.get("seed"), bool):
        errors.append(issue("error", "INVALID_SEED", "seed", "seed must be an integer.", value=root.get("seed")))
    if not isinstance(root.get("layers"), list):
        errors.append(issue("error", "INVALID_LAYERS", "layers", "layers must be an array."))
        layers: list[Any] = []
    else:
        layers = root["layers"]

    layer_ids: set[str] = set()
    duration = float(root.get("duration", 0.0)) if finite_number(root.get("duration")) else 0.0
    for index, layer in enumerate(layers):
        path = f"layers[{index}]"
        if not isinstance(layer, dict):
            errors.append(issue("error", "INVALID_LAYER", path, "Each layer must be an object."))
            continue
        layer_id = layer.get("id")
        if not is_stable_id(layer_id):
            errors.append(issue("error", "INVALID_LAYER_ID", f"{path}.id", "Layer IDs must be stable identifiers.", value=layer_id))
        elif layer_id in layer_ids:
            errors.append(issue("error", "DUPLICATE_LAYER_ID", f"{path}.id", f"Layer ID '{layer_id}' is duplicated."))
        else:
            layer_ids.add(layer_id)
        layer_type = layer.get("type")
        if layer_type not in LAYER_TYPES:
            errors.append(issue("error", "UNKNOWN_LAYER_TYPE", f"{path}.type", f"Unsupported layer type '{layer_type}'.", f"Use one of: {', '.join(LAYER_TYPES)}.", layer_type))
            continue
        properties = layer.get("properties", {})
        if not isinstance(properties, dict):
            errors.append(issue("error", "INVALID_PROPERTIES", f"{path}.properties", "Layer properties must be an object."))
            properties = {}
        material = layer.get("material", {})
        if not isinstance(material, dict):
            errors.append(issue("error", "INVALID_MATERIAL", f"{path}.material", "Material settings must be an object."))
            material = {}
        curves = layer.get("curves", {})
        if not isinstance(curves, dict):
            errors.append(issue("error", "INVALID_CURVES", f"{path}.curves", "curves must be an object."))
            curves = {}
        if strict:
            for key in layer:
                if key not in LAYER_STRUCT_KEYS:
                    errors.append(issue("error", "UNKNOWN_LAYER_FIELD", f"{path}.{key}", f"Unknown layer field '{key}' is not allowed in strict mode.", value=key))
            allowed_properties = layer_property_keys(layer_type)
            allowed_material = layer_material_keys()
            allowed_curves = layer_curve_keys(layer_type)
            for key in properties:
                if key not in allowed_properties:
                    errors.append(issue("error", "UNKNOWN_LAYER_PROPERTY", f"{path}.properties.{key}", f"Unknown property '{key}' for layer type '{layer_type}'.", value=key))
            for key in material:
                if key not in allowed_material:
                    errors.append(issue("error", "UNKNOWN_MATERIAL_FIELD", f"{path}.material.{key}", f"Unknown material field '{key}'.", value=key))
            for curve_name in curves:
                if curve_name not in allowed_curves:
                    errors.append(issue("error", "UNKNOWN_CURVE", f"{path}.curves.{curve_name}", f"Unsupported curve '{curve_name}' for layer type '{layer_type}'.", value=curve_name))
        if not isinstance(layer.get("name"), str) or not layer.get("name", "").strip():
            warnings.append(issue("warning", "EMPTY_LAYER_NAME", f"{path}.name", "The layer has no display name."))
        if not isinstance(layer.get("enabled"), bool):
            errors.append(issue("error", "INVALID_ENABLED", f"{path}.enabled", "enabled must be boolean.", value=layer.get("enabled")))
        _number(errors, warnings, layer.get("start"), f"{path}.start", 0.0, 3600.0, True)
        layer_duration_ok = _number(errors, warnings, layer.get("duration"), f"{path}.duration", 0.001, 3600.0, True)
        if layer_duration_ok and finite_number(layer.get("start")) and float(layer["start"]) + float(layer["duration"]) > duration + 1e-6:
            outside = issue("warning", "LAYER_OUTSIDE_DURATION", path, "The layer ends after the effect duration.", "Increase effect duration or shorten the layer.")
            (errors if strict else warnings).append(outside)
        blend = material.get("blend_mode", "additive")
        if blend not in BLEND_MODES:
            errors.append(issue("error", "INVALID_BLEND_MODE", f"{path}.material.blend_mode", f"Use one of: {', '.join(BLEND_MODES)}.", value=blend))
        if material.get("texture"):
            _check_texture_ref(material.get("texture"), f"{path}.material.texture", project, errors)
        texture = properties.get("texture")
        if texture:
            _check_texture_ref(texture, f"{path}.properties.texture", project, errors)
        mesh_asset = properties.get("mesh_asset")
        if mesh_asset:
            _check_mesh_ref(mesh_asset, f"{path}.properties.mesh_asset", project, errors)
        if layer_type in {"particle", "mesh_particle"}:
            _number(errors, warnings, properties.get("amount"), f"{path}.properties.amount", 0, 200000, True)
            _number(errors, warnings, properties.get("lifetime"), f"{path}.properties.lifetime", 0.001, 3600.0, True)
            if properties.get("amount") == 0:
                zero_issue = issue("warning", "ZERO_PARTICLES", f"{path}.properties.amount", "The emitter is configured to produce zero particles.", "Set amount above zero or disable the layer.")
                (errors if strict else warnings).append(zero_issue)
            if properties.get("emission_shape") not in EMISSION_SHAPES:
                errors.append(issue("error", "INVALID_EMISSION_SHAPE", f"{path}.properties.emission_shape", f"Use one of: {', '.join(EMISSION_SHAPES)}.", value=properties.get("emission_shape")))
        vector_keys = ["direction", "gravity", "attractor_position"]
        if layer_type == "beam":
            vector_keys.extend(["source", "target"])
        for key in vector_keys:
            if key in properties:
                _vector(properties[key], f"{path}.properties.{key}", 3, errors)
        if layer_type in {"sprite", "decal"} and "size" in properties:
            _vector(properties["size"], f"{path}.properties.size", 2, errors)
        if layer_type == "mesh_effect":
            _vector(properties.get("size"), f"{path}.properties.size", 3, errors)
        for curve_name, curve_value in curves.items():
            _validate_curve(curve_value, f"{path}.curves.{curve_name}", errors, warnings)
        _validate_gradient(layer.get("gradient", []), f"{path}.gradient", errors)

    timeline = root.get("timeline", {})
    if not isinstance(timeline, dict):
        errors.append(issue("error", "INVALID_TIMELINE", "timeline", "timeline must be an object."))
    else:
        events = timeline.get("events", [])
        if not isinstance(events, list):
            errors.append(issue("error", "INVALID_TIMELINE_EVENTS", "timeline.events", "Timeline events must be an array."))
        else:
            event_ids: set[str] = set()
            for index, event in enumerate(events):
                event_path = f"timeline.events[{index}]"
                if not isinstance(event, dict):
                    errors.append(issue("error", "INVALID_EVENT", event_path, "Timeline events must be objects."))
                    continue
                event_id = event.get("id", event.get("event_id"))
                if not isinstance(event_id, str) or not event_id:
                    errors.append(issue("error", "MISSING_EVENT_ID", f"{event_path}.id", "Timeline events need a stable id."))
                elif event_id in event_ids:
                    errors.append(issue("error", "DUPLICATE_EVENT_ID", f"{event_path}.id", f"Event ID '{event_id}' is duplicated."))
                else:
                    event_ids.add(event_id)
                if _number(errors, warnings, event.get("time"), f"{event_path}.time", 0.0, 3600.0, True) and finite_number(event.get("time")) and float(event["time"]) > duration:
                    outside_event = issue("warning", "EVENT_OUTSIDE_DURATION", event_path, "The event occurs after the effect duration.")
                    (errors if strict else warnings).append(outside_event)

    dependencies = root.get("dependencies", {})
    if not isinstance(dependencies, dict):
        errors.append(issue("error", "INVALID_DEPENDENCIES", "dependencies", "dependencies must be an object."))
    else:
        texture_refs = dependencies.get("textures", [])
        if not isinstance(texture_refs, list):
            errors.append(issue("error", "INVALID_TEXTURE_DEPENDENCIES", "dependencies.textures", "Texture dependencies must be an array."))
        else:
            for index, reference in enumerate(texture_refs):
                _check_texture_ref(reference, f"dependencies.textures[{index}]", project, errors)
        effect_refs = dependencies.get("effects", [])
        if not isinstance(effect_refs, list):
            errors.append(issue("error", "INVALID_EFFECT_DEPENDENCIES", "dependencies.effects", "Effect dependencies must be an array."))
        else:
            for index, reference in enumerate(effect_refs):
                if not isinstance(reference, str) or not reference:
                    errors.append(issue("error", "INVALID_EFFECT_REFERENCE", f"dependencies.effects[{index}]", "Effect dependencies must be non-empty strings.", value=reference))
                elif project is not None and _resolve_effect(reference, project) is None:
                    errors.append(issue("error", "MISSING_EFFECT", f"dependencies.effects[{index}]", f"Referenced child effect does not exist: {reference}", "Create the effect file or correct the stable ID.", reference))
        mesh_refs = dependencies.get("meshes", [])
        if not isinstance(mesh_refs, list):
            errors.append(issue("error", "INVALID_MESH_DEPENDENCIES", "dependencies.meshes", "Mesh dependencies must be an array."))
        else:
            for index, reference in enumerate(mesh_refs):
                _check_mesh_ref(reference, f"dependencies.meshes[{index}]", project, errors)
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            continue
        reference = _effect_reference(layer)
        if reference and project is not None and _resolve_effect(reference, project) is None:
            errors.append(issue("error", "MISSING_CHILD_EFFECT", f"layers[{index}].properties.effect_id", f"Child effect does not exist: {reference}", "Create the referenced .vfx.json or correct the stable ID.", reference))
    errors.extend(detect_dependency_cycles(root, project))

    metrics = estimate_metrics(root, project)
    budgets = root.get("budgets", {})
    if not isinstance(budgets, dict):
        budgets = {}
    profile_name = selected_budget or budgets.get("profile", "Medium")
    if profile_name not in BUDGET_PROFILES:
        unknown_profile = issue("warning", "UNKNOWN_BUDGET_PROFILE", "budgets.profile", f"Unknown budget profile '{profile_name}', using Medium.", value=profile_name)
        if strict:
            errors.append(issue("error", "UNKNOWN_BUDGET_PROFILE", "budgets.profile", f"Unknown budget profile '{profile_name}'.", value=profile_name))
        else:
            warnings.append(unknown_profile)
            profile_name = "Medium"
    profile = BUDGET_PROFILES.get(profile_name, BUDGET_PROFILES["Medium"])
    if policy_ceilings:
        profile = {
            "max_particles": policy_ceilings.get("max_particles", profile["max_particles"]),
            "max_lights": policy_ceilings.get("max_lights", profile["max_lights"]),
            "max_draw_calls": policy_ceilings.get("max_draw_calls", profile["max_draw_calls"]),
            "max_layers": policy_ceilings.get("max_layers", profile["max_layers"]),
            "max_transparent_layers": policy_ceilings.get("max_transparent_layers", 6),
            "max_trail_segments": policy_ceilings.get("max_trail_segments", 24),
            "max_beam_segments": policy_ceilings.get("max_beam_segments", 24),
            "max_duration_sec": policy_ceilings.get("max_duration_sec", 30.0),
            "max_texture_dimension": policy_ceilings.get("max_texture_dimension", 1024),
            "max_child_effect_depth": policy_ceilings.get("max_child_effect_depth", 4),
            "allowed_layer_types": policy_ceilings.get("allowed_layer_types", []),
        }
    budget_target = errors if strict else warnings
    if metrics["peak_particles_estimate"] > profile["max_particles"]:
        budget_target.append(issue("warning" if not strict else "error", "PARTICLE_BUDGET_EXCEEDED", "layers", f"Estimated peak particles ({metrics['peak_particles_estimate']}) exceed {profile_name} budget ({int(profile['max_particles'])}).", "Lower emitter amounts or choose an intentional higher budget."))
    if metrics["lights"] > profile["max_lights"]:
        budget_target.append(issue("warning" if not strict else "error", "LIGHT_BUDGET_EXCEEDED", "layers", f"Estimated dynamic lights ({metrics['lights']}) exceed {profile_name} budget ({int(profile['max_lights'])}).", "Reduce dynamic lights or use baked/mesh glow."))
    if metrics["draw_calls_estimate"] > profile["max_draw_calls"]:
        budget_target.append(issue("warning" if not strict else "error", "DRAW_CALL_BUDGET_EXCEEDED", "layers", f"Estimated draw calls ({metrics['draw_calls_estimate']}) exceed {profile_name} budget ({int(profile['max_draw_calls'])})."))
    if metrics["layer_count"] > profile["max_layers"]:
        budget_target.append(issue("warning" if not strict else "error", "LAYER_BUDGET_EXCEEDED", "layers", f"Layer count ({metrics['layer_count']}) exceeds {profile_name} budget ({int(profile['max_layers'])})."))
    if policy_ceilings and profile.get("max_transparent_layers") and metrics.get("overdraw_layers", 0) > profile["max_transparent_layers"]:
        budget_target.append(issue("warning" if not strict else "error", "TRANSPARENT_LAYER_BUDGET_EXCEEDED", "layers", f"Transparent layers ({metrics['overdraw_layers']}) exceed policy limit ({profile['max_transparent_layers']})."))
    if policy_ceilings and duration > float(profile.get("max_duration_sec", 30.0)):
        budget_target.append(issue("warning" if not strict else "error", "DURATION_POLICY_EXCEEDED", "duration", f"Effect duration ({duration}) exceeds policy maximum ({profile['max_duration_sec']})."))
    allowed_layer_types = profile.get("allowed_layer_types") if policy_ceilings else None
    if strict and allowed_layer_types:
        allowed = set(allowed_layer_types)
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                continue
            layer_type = layer.get("type")
            if layer_type not in allowed:
                errors.append(issue("error", "LAYER_TYPE_NOT_ALLOWED", f"layers[{index}].type", f"Layer type '{layer_type}' is not allowed by policy.", value=layer_type))
    if strict and policy_ceilings:
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                continue
            properties = layer.get("properties", {})
            if layer.get("type") == "trail" and isinstance(properties, dict):
                segments = properties.get("segments", properties.get("segment_count"))
                if finite_number(segments) and float(segments) > profile["max_trail_segments"]:
                    errors.append(issue("error", "TRAIL_SEGMENT_LIMIT", f"layers[{index}].properties.segments", f"Trail segments exceed policy limit ({profile['max_trail_segments']}).", value=segments))
            if layer.get("type") == "beam" and isinstance(properties, dict):
                segments = properties.get("segments", properties.get("segment_count"))
                if finite_number(segments) and float(segments) > profile["max_beam_segments"]:
                    errors.append(issue("error", "BEAM_SEGMENT_LIMIT", f"layers[{index}].properties.segments", f"Beam segments exceed policy limit ({profile['max_beam_segments']}).", value=segments))
        max_texture_dimension = int(profile.get("max_texture_dimension", 0) or 0)
        if max_texture_dimension > 0:
            texture_paths: set[str] = set()
            for index, layer in enumerate(layers):
                if not isinstance(layer, dict):
                    continue
                path = f"layers[{index}]"
                material = layer.get("material", {})
                properties = layer.get("properties", {})
                if isinstance(material, dict) and material.get("texture"):
                    texture_paths.add(f"{path}.material.texture")
                    _check_texture_ref(
                        material.get("texture"),
                        f"{path}.material.texture",
                        project,
                        errors,
                        max_dimension=max_texture_dimension,
                        require_inspectable=True,
                    )
                if isinstance(properties, dict) and properties.get("texture"):
                    _check_texture_ref(
                        properties.get("texture"),
                        f"{path}.properties.texture",
                        project,
                        errors,
                        max_dimension=max_texture_dimension,
                        require_inspectable=True,
                    )
            if isinstance(dependencies, dict):
                for index, reference in enumerate(dependencies.get("textures", [])):
                    _check_texture_ref(
                        reference,
                        f"dependencies.textures[{index}]",
                        project,
                        errors,
                        max_dimension=max_texture_dimension,
                        require_inspectable=bool(reference),
                    )
        max_child_depth = int(profile.get("max_child_effect_depth", 0) or 0)
        if max_child_depth > 0 and project is not None:
            depth = _max_child_effect_depth(root, project)
            if depth > max_child_depth:
                errors.append(
                    issue(
                        "error",
                        "CHILD_EFFECT_DEPTH_EXCEEDED",
                        "dependencies.effects",
                        f"Child-effect dependency depth ({depth}) exceeds policy maximum ({max_child_depth}).",
                        value=depth,
                    )
                )
    if metrics["overdraw_layers"] >= 6:
        warnings.append(issue("warning", "OVERDRAW_RISK", "layers", f"{metrics['overdraw_layers']} transparent/additive layers may create heavy overdraw.", "Preview on target hardware and consolidate cards where possible."))
    if duration > 30.0:
        warnings.append(issue("warning", "LONG_DURATION", "duration", "The effect lasts longer than 30 seconds.", "Confirm this is an intentional environmental or looping effect."))

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
        "budget": {"profile": profile_name, "limits": profile},
    }


def validation_summary(validation: dict[str, Any]) -> str:
    state = "PASS" if validation.get("valid") else "FAIL"
    return f"{state}: {len(validation.get('errors', []))} error(s), {len(validation.get('warnings', []))} warning(s)"


def iter_vfx_files(directory: str | Path) -> Iterable[Path]:
    root = Path(directory)
    if root.is_file():
        yield root
    else:
        yield from sorted(root.rglob("*.vfx.json"))
