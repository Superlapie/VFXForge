"""Canonical VFX Forge schema defaults and self-description.

The schema intentionally stays data-oriented. GUI, CLI, renderer, and exporter
consume these defaults rather than maintaining parallel representations.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .version import GODOT_TARGET, SCHEMA_VERSION, TOOL_NAME, TOOL_VERSION


LAYER_TYPES: tuple[str, ...] = (
    "particle",
    "mesh_particle",
    "sprite",
    "light",
    "trail",
    "beam",
    "decal",
    "mesh_effect",
    "audio_marker",
    "event_marker",
    "child_effect",
)

BLEND_MODES: tuple[str, ...] = ("additive", "alpha", "premultiplied", "multiply")
BILLBOARD_MODES: tuple[str, ...] = ("disabled", "enabled", "y_billboard", "particle")
MESH_ASSET_EXTENSIONS: tuple[str, ...] = (".obj", ".glb", ".gltf")
EMISSION_SHAPES: tuple[str, ...] = (
    "point",
    "box",
    "sphere",
    "sphere_surface",
    "ring",
    "disc",
    "line",
    "cone",
)


def curve(points: list[tuple[float, float]], interpolation: str = "linear") -> dict[str, Any]:
    return {
        "interpolation": interpolation,
        "points": [{"x": float(x), "y": float(y)} for x, y in points],
    }


def gradient(stops: list[tuple[float, str]]) -> list[dict[str, Any]]:
    return [{"position": float(position), "color": color} for position, color in stops]


COMMON_LAYER: dict[str, Any] = {
    "name": "",
    "enabled": True,
    "start": 0.0,
    "duration": 1.0,
    "properties": {},
    "material": {
        "blend_mode": "additive",
        "unshaded": True,
        "billboard": "enabled",
        "depth_draw": "always",
        "texture": "",
        "tint": "#FFFFFFFF",
        "uv_scroll": [0.0, 0.0],
        "distortion": 0.0,
        "dissolve": 0.0,
        "fresnel": 0.0,
        "emissive_intensity": 1.0,
    },
    "curves": {},
    "gradient": gradient([(0.0, "#FFFFFFFF"), (1.0, "#00000000")]),
}


LAYER_DEFAULTS: dict[str, dict[str, Any]] = {
    "particle": {
        **COMMON_LAYER,
        "properties": {
            "amount": 32,
            "one_shot": True,
            "lifetime": 0.8,
            "explosiveness": 0.8,
            "randomness": 0.15,
            "fixed_fps": 0,
            "local_coords": False,
            "emission_shape": "point",
            "emission_box_extents": [0.25, 0.25, 0.25],
            "emission_radius": 0.5,
            "emission_height": 0.1,
            "direction": [0.0, 1.0, 0.0],
            "spread": 35.0,
            "initial_velocity_min": 1.0,
            "initial_velocity_max": 2.0,
            "gravity": [0.0, -2.0, 0.0],
            "damping": 0.0,
            "radial_accel": 0.0,
            "tangential_accel": 0.0,
            "turbulence": 0.0,
            "attractor_strength": 0.0,
            "attractor_position": [0.0, 0.0, 0.0],
            "scale_min": 0.08,
            "scale_max": 0.16,
            "rotation_min": 0.0,
            "rotation_max": 360.0,
            "angular_velocity_min": -90.0,
            "angular_velocity_max": 90.0,
            "texture": "",
        },
        "curves": {
            "scale": curve([(0.0, 0.35), (0.15, 1.0), (1.0, 0.0)]),
            "alpha": curve([(0.0, 0.0), (0.1, 1.0), (0.75, 1.0), (1.0, 0.0)]),
            "velocity": curve([(0.0, 1.0), (1.0, 0.2)]),
        },
    },
    "mesh_particle": {
        **COMMON_LAYER,
        "properties": {
            "amount": 24,
            "one_shot": True,
            "lifetime": 1.0,
            "mesh": "quad",
            "mesh_asset": "",
            "emission_shape": "point",
            "size": [0.15, 0.15, 0.15],
            "spread": 25.0,
            "initial_velocity": 1.5,
            "gravity": [0.0, -1.5, 0.0],
            "rotation_speed": 0.0,
        },
        "curves": {"scale": curve([(0.0, 0.2), (0.12, 1.0), (1.0, 0.0)])},
    },
    "sprite": {
        **COMMON_LAYER,
        "properties": {
            "texture": "",
            "size": [1.0, 1.0],
            "flipbook_columns": 1,
            "flipbook_rows": 1,
            "flipbook_frames": 1,
            "flipbook_fps": 12.0,
            "flipbook_loop": False,
            "flipbook_start_frame": 0,
            "random_start": False,
            "billboard": "enabled",
            "pixel_snap": False,
        },
        "curves": {"scale": curve([(0.0, 0.5), (0.15, 1.0), (1.0, 0.0)])},
    },
    "light": {
        **COMMON_LAYER,
        "properties": {
            "color": "#8A7CFFFF",
            "energy": 2.0,
            "range": 3.0,
            "shadow_enabled": False,
            "fade": True,
        },
        "curves": {"energy": curve([(0.0, 0.0), (0.12, 1.0), (0.7, 0.55), (1.0, 0.0)])},
    },
    "trail": {
        **COMMON_LAYER,
        "properties": {
            "width": 0.18,
            "lifetime": 0.35,
            "segments": 16,
            "color": "#9C8CFFFF",
            "alpha": 1.0,
            "uv_mode": "stretch",
            "texture": "",
            "target": "self",
        },
        "curves": {"width": curve([(0.0, 1.0), (1.0, 0.0)])},
    },
    "beam": {
        **COMMON_LAYER,
        "properties": {
            "source": [0.0, 0.0, 0.0],
            "target": [0.0, 0.0, -4.0],
            "thickness": 0.12,
            "segments": 12,
            "noise": 0.08,
            "scroll_speed": 1.0,
            "fade": 1.0,
            "color": "#8FC8FFFF",
            "texture": "",
        },
        "curves": {"width": curve([(0.0, 0.0), (0.12, 1.0), (0.85, 1.0), (1.0, 0.0)])},
    },
    "decal": {
        **COMMON_LAYER,
        "properties": {
            "texture": "",
            "size": [2.0, 2.0],
            "color": "#5D48B6B8",
            "height": 0.02,
            "fade": True,
            "rotate": 0.0,
        },
        "curves": {"scale": curve([(0.0, 0.0), (0.2, 1.0), (1.0, 0.8)])},
    },
    "mesh_effect": {
        **COMMON_LAYER,
        "properties": {
            "mesh": "sphere",
            "mesh_asset": "",
            "size": [1.0, 1.0, 1.0],
            "rotation": [0.0, 0.0, 0.0],
            "rotation_speed": [0.0, 45.0, 0.0],
            "dissolve": 0.0,
            "pulse": 0.0,
            "color": "#8E79FFFF",
        },
        "curves": {
            "scale": curve([(0.0, 0.2), (0.18, 1.0), (1.0, 0.8)]),
            "alpha": curve([(0.0, 0.0), (0.1, 1.0), (0.8, 1.0), (1.0, 0.0)]),
        },
    },
    "audio_marker": {
        **COMMON_LAYER,
        "properties": {
            "event_id": "vfx.impact",
            "volume": 1.0,
            "pitch": 1.0,
            "pitch_variation": 0.0,
        },
    },
    "event_marker": {
        **COMMON_LAYER,
        "properties": {
            "event_id": "impact",
            "payload": {},
        },
    },
    "child_effect": {
        **COMMON_LAYER,
        "properties": {
            "effect_id": "",
            "trigger": "on_start",
            "offset": [0.0, 0.0, 0.0],
            "inherit_transform": True,
            "max_instances": 8,
        },
    },
}


BUDGET_PROFILES: dict[str, dict[str, float]] = {
    "Mobile": {"max_particles": 800, "max_lights": 1, "max_draw_calls": 12, "max_layers": 12},
    "Low": {"max_particles": 1800, "max_lights": 2, "max_draw_calls": 24, "max_layers": 20},
    "Medium": {"max_particles": 5000, "max_lights": 4, "max_draw_calls": 48, "max_layers": 32},
    "High": {"max_particles": 14000, "max_lights": 8, "max_draw_calls": 96, "max_layers": 64},
    "Boss": {"max_particles": 30000, "max_lights": 12, "max_draw_calls": 160, "max_layers": 100},
    "Cinematic": {"max_particles": 80000, "max_lights": 24, "max_draw_calls": 300, "max_layers": 200},
}


def default_document(
    effect_id: str,
    name: str | None = None,
    duration: float = 1.0,
    loop: bool = False,
    seed: int = 12345,
) -> dict[str, Any]:
    """Return a complete, serializable document with no shared mutable state."""
    return {
        "schema_version": SCHEMA_VERSION,
        "id": effect_id,
        "name": name or effect_id.replace("_", " ").title(),
        "duration": float(duration),
        "loop": bool(loop),
        "seed": int(seed),
        "metadata": {
            "author": "",
            "description": "",
            "created_with": f"{TOOL_NAME} {TOOL_VERSION}",
            "notes": "",
        },
        "tags": [],
        "layers": [],
        "dependencies": {"textures": [], "meshes": [], "effects": []},
        "timeline": {"events": [], "snap": 0.05},
        "camera_presets": {
            "front": {"position": [0.0, 1.2, 5.0], "target": [0.0, 0.8, 0.0], "fov": 45.0},
            "mmo": {"position": [4.5, 4.0, 5.5], "target": [0.0, 0.7, 0.0], "fov": 50.0},
            "top": {"position": [0.0, 6.0, 0.0], "target": [0.0, 0.0, 0.0], "fov": 45.0},
        },
        "budgets": {"profile": "Medium", "custom": {}},
        "export": {
            "godot_version": GODOT_TARGET,
            "folder_name": effect_id,
            "include_metadata": True,
            "embed_document": True,
            "copy_textures": True,
            "copy_meshes": True,
        },
    }


def make_layer(layer_type: str, layer_id: str, name: str | None = None) -> dict[str, Any]:
    """Create a layer from the authoritative type defaults."""
    if layer_type not in LAYER_DEFAULTS:
        raise KeyError(f"Unknown layer type: {layer_type}")
    layer = deepcopy(LAYER_DEFAULTS[layer_type])
    layer["id"] = layer_id
    layer["name"] = name or layer_id.replace("_", " ").title()
    layer["type"] = layer_type
    return layer


def schema_description() -> dict[str, Any]:
    """Return a stable machine-readable description used by the explain command."""
    layer_fields = {}
    for layer_type, default in LAYER_DEFAULTS.items():
        layer_fields[layer_type] = {
            "required": ["id", "type", "name", "enabled", "start", "duration"],
            "properties": default["properties"],
            "material": default["material"],
            "curves": default["curves"],
            "gradient": default["gradient"],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "godot_target": GODOT_TARGET,
        "layer_types": list(LAYER_TYPES),
        "enums": {
            "blend_modes": list(BLEND_MODES),
            "billboard_modes": list(BILLBOARD_MODES),
            "emission_shapes": list(EMISSION_SHAPES),
            "mesh_asset_extensions": list(MESH_ASSET_EXTENSIONS),
            "budget_profiles": list(BUDGET_PROFILES),
        },
        "document_required": ["schema_version", "id", "name", "duration", "loop", "seed", "layers"],
        "layer_fields": layer_fields,
        "budget_profiles": BUDGET_PROFILES,
    }
