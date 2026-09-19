"""Validate compiled documents against the Godot runtime capability contract."""

from __future__ import annotations

import hashlib
from typing import Any

from ..resources import godot_runtime_dir


RUNTIME_CONTRACT_VERSION = 1

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

PARTICLE_CURVE_CHANNELS = frozenset({"scale", "alpha", "velocity"})

PARTICLE_PROPERTIES = frozenset({
    "amount",
    "one_shot",
    "lifetime",
    "explosiveness",
    "randomness",
    "fixed_fps",
    "local_coords",
    "emission_shape",
    "emission_box_extents",
    "emission_radius",
    "emission_height",
    "direction",
    "spread",
    "initial_velocity",
    "initial_velocity_min",
    "initial_velocity_max",
    "gravity",
    "damping",
    "radial_accel",
    "tangential_accel",
    "scale_min",
    "scale_max",
    "rotation_min",
    "rotation_max",
    "angular_velocity_min",
    "angular_velocity_max",
    "flipbook_start_frame",
    "flipbook_frames",
    "flipbook_fps",
    "flipbook_loop",
    "texture",
    "color",
    "size",
    "mesh_asset",
    "turbulence",
    "attractor_strength",
    "attractor_position",
})

TRAIL_PROPERTIES = frozenset({
    "width",
    "lifetime",
    "segments",
    "color",
    "alpha",
    "uv_mode",
    "texture",
    "target",
})


def _curve_has_points(curve: Any) -> bool:
    if not isinstance(curve, dict):
        return False
    points = curve.get("points")
    return isinstance(points, list) and len(points) > 0


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
    return {
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "particle": {
            "emission_shapes": sorted(PARTICLE_EMISSION_SHAPES),
            "properties": sorted(PARTICLE_PROPERTIES),
            "curves": sorted(PARTICLE_CURVE_CHANNELS),
        },
        "trail": {
            "properties": sorted(TRAIL_PROPERTIES),
            "curves": ["width"],
        },
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
        layer_id = str(layer.get("id", "unknown"))
        layer_type = str(layer.get("type", ""))
        properties = layer.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        if layer_type in {"particle", "mesh_particle"}:
            shape = str(properties.get("emission_shape", "point"))
            if shape not in PARTICLE_EMISSION_SHAPES:
                errors.append({
                    "code": "UNSUPPORTED_RUNTIME_EMISSION_SHAPE",
                    "message": f"Layer '{layer_id}' uses emission shape '{shape}' which the Godot runtime does not implement.",
                    "layer_id": layer_id,
                    "path": f"layers.{layer_id}.properties.emission_shape",
                    "supported": sorted(PARTICLE_EMISSION_SHAPES),
                })
            for key, value in properties.items():
                if key not in PARTICLE_PROPERTIES:
                    errors.append({
                        "code": "UNSUPPORTED_RUNTIME_PARTICLE_PROPERTY",
                        "message": f"Layer '{layer_id}' uses particle property '{key}' which the Godot runtime does not implement.",
                        "layer_id": layer_id,
                        "path": f"layers.{layer_id}.properties.{key}",
                    })
                elif key in {"turbulence", "attractor_strength"} and float(value or 0.0) != 0.0:
                    errors.append({
                        "code": "UNSUPPORTED_RUNTIME_PARTICLE_PROPERTY",
                        "message": f"Layer '{layer_id}' uses non-zero '{key}', which the Godot runtime does not implement.",
                        "layer_id": layer_id,
                        "path": f"layers.{layer_id}.properties.{key}",
                    })
            curves = layer.get("curves", {})
            if isinstance(curves, dict):
                for channel, curve in curves.items():
                    if channel not in PARTICLE_CURVE_CHANNELS and _curve_has_points(curve):
                        errors.append({
                            "code": "UNSUPPORTED_RUNTIME_CURVE",
                            "message": f"Layer '{layer_id}' uses curve '{channel}' which the Godot runtime does not implement.",
                            "layer_id": layer_id,
                            "path": f"layers.{layer_id}.curves.{channel}",
                            "supported": sorted(PARTICLE_CURVE_CHANNELS),
                        })
        elif layer_type == "trail":
            for key in properties:
                if key not in TRAIL_PROPERTIES:
                    errors.append({
                        "code": "UNSUPPORTED_RUNTIME_TRAIL_PROPERTY",
                        "message": f"Layer '{layer_id}' uses trail property '{key}' which the Godot runtime does not implement.",
                        "layer_id": layer_id,
                        "path": f"layers.{layer_id}.properties.{key}",
                    })
    return errors
