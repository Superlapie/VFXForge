"""Small authored presets expressed in the same canonical project format."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .schema import default_document, make_layer


def _base(effect_id: str, name: str, duration: float, seed: int = 12345) -> dict[str, Any]:
    return default_document(effect_id, name, duration, False, seed)


def _add(document: dict[str, Any], layer_type: str, layer_id: str, **updates: Any) -> None:
    layer = make_layer(layer_type, layer_id)
    for key, value in updates.items():
        if key in {"start", "duration", "enabled", "name", "material", "curves", "gradient"}:
            layer[key] = deepcopy(value)
        else:
            layer.setdefault("properties", {})[key] = deepcopy(value)
    document["layers"].append(layer)


def preset_arcane_impact() -> dict[str, Any]:
    doc = _base("arcane_impact", "Arcane Impact", 1.5, 18473)
    doc["tags"] = ["impact", "magic", "arcane"]
    _add(doc, "decal", "rune_circle", duration=1.4, size=[2.4, 2.4], color="#765CFF78")
    _add(doc, "particle", "sparks", duration=1.0, amount=64, lifetime=0.75, emission_shape="sphere", emission_radius=0.18, initial_velocity_min=2.4, initial_velocity_max=4.2, gravity=[0.0, -4.0, 0.0], scale_min=0.04, scale_max=0.1)
    _add(doc, "sprite", "flash", duration=0.32, size=[1.8, 1.8], color="#C2B5FFFF")
    _add(doc, "light", "impact_light", duration=0.55, color="#8B78FFFF", energy=4.0, range=4.5)
    doc["timeline"]["events"].append({"id": "impact", "event_id": "impact", "time": 0.08, "data": {"shake": 0.25}})
    return doc


def preset_fire_impact() -> dict[str, Any]:
    doc = _base("fire_impact", "Fire Impact", 1.35, 40391)
    doc["tags"] = ["impact", "fire", "burst"]
    _add(doc, "decal", "scorch", duration=1.35, size=[2.2, 2.2], color="#FF6A2E80")
    _add(doc, "particle", "embers", duration=1.2, amount=88, lifetime=1.0, emission_shape="cone", spread=48.0, initial_velocity_min=1.8, initial_velocity_max=3.8, gravity=[0.0, -2.0, 0.0], color="#FF9A3CFF")
    _add(doc, "sprite", "fireball", duration=0.7, size=[1.6, 1.6], color="#FFB05CFF")
    _add(doc, "light", "fire_light", duration=0.9, color="#FF6B2EFF", energy=5.0, range=4.0)
    return doc


def preset_healing_aura() -> dict[str, Any]:
    doc = _base("healing_aura", "Healing Aura", 2.6, 9182)
    doc["loop"] = True
    doc["tags"] = ["aura", "healing", "buff"]
    _add(doc, "particle", "motes", duration=2.6, amount=48, one_shot=False, lifetime=2.4, emission_shape="ring", emission_radius=1.0, initial_velocity_min=0.15, initial_velocity_max=0.45, gravity=[0.0, 0.2, 0.0], color="#80FFB9FF")
    _add(doc, "decal", "circle", duration=2.6, size=[2.6, 2.6], color="#49E99A54")
    _add(doc, "light", "healing_light", duration=2.6, color="#73FFC0FF", energy=1.8, range=3.2)
    return doc


def preset_ground_warning() -> dict[str, Any]:
    doc = _base("ground_warning_circle", "Ground Warning Circle", 2.2, 55310)
    doc["tags"] = ["telegraph", "ground", "warning"]
    _add(doc, "decal", "warning_circle", duration=2.2, size=[3.5, 3.5], color="#FF465C78")
    _add(doc, "particle", "dust", duration=2.2, amount=20, one_shot=False, lifetime=1.2, emission_shape="ring", emission_radius=1.6, initial_velocity_min=0.05, initial_velocity_max=0.2, gravity=[0.0, 0.1, 0.0], color="#FFB07780")
    _add(doc, "event_marker", "damage_frame", start=1.8, duration=0.05, event_id="damage_frame", payload={"severity": "warning"})
    return doc


def preset_lightning_beam() -> dict[str, Any]:
    doc = _base("lightning_beam", "Lightning Beam", 1.1, 71127)
    doc["tags"] = ["beam", "lightning", "boss"]
    _add(doc, "beam", "bolt", duration=0.95, source=[0.0, 1.2, 0.0], target=[0.0, 1.0, -5.5], thickness=0.16, segments=18, noise=0.22, color="#A9E8FFFF")
    _add(doc, "light", "bolt_light", duration=0.8, color="#79D8FFFF", energy=4.5, range=5.0)
    _add(doc, "event_marker", "cast", duration=0.05, event_id="cast", payload={"channel": "lightning"})
    return doc


def preset_weapon_trail() -> dict[str, Any]:
    doc = _base("weapon_trail", "Weapon Trail", 0.9, 26591)
    doc["tags"] = ["trail", "weapon", "melee"]
    _add(doc, "trail", "blade_trail", duration=0.85, width=0.24, lifetime=0.4, segments=20, color="#C4D8FFFF")
    _add(doc, "particle", "trail_sparks", duration=0.8, amount=18, lifetime=0.5, emission_shape="line", initial_velocity_min=0.6, initial_velocity_max=1.8, gravity=[0.0, -1.0, 0.0], color="#B7D5FFFF")
    return doc


def preset_portal() -> dict[str, Any]:
    doc = _base("portal", "Portal", 3.0, 60012)
    doc["loop"] = True
    doc["tags"] = ["portal", "environment", "magic"]
    _add(doc, "mesh_effect", "portal_ring", duration=3.0, size=[2.0, 2.0, 0.35], color="#A980FFFF", pulse=0.2)
    _add(doc, "particle", "portal_motes", duration=3.0, amount=42, one_shot=False, lifetime=2.0, emission_shape="ring", emission_radius=0.9, initial_velocity_min=0.1, initial_velocity_max=0.5, gravity=[0.0, 0.2, 0.0], color="#C7A8FFFF")
    _add(doc, "light", "portal_light", duration=3.0, color="#8060FFFF", energy=2.5, range=3.5)
    return doc


def preset_dust_burst() -> dict[str, Any]:
    doc = _base("dust_burst", "Dust Burst", 1.4, 22380)
    doc["tags"] = ["dust", "impact", "environment"]
    _add(doc, "particle", "dust_cloud", duration=1.4, amount=72, lifetime=1.2, emission_shape="sphere", emission_radius=0.35, initial_velocity_min=0.4, initial_velocity_max=1.5, gravity=[0.0, 0.4, 0.0], scale_min=0.1, scale_max=0.25, color="#D4B78CFF")
    _add(doc, "decal", "dust_shadow", duration=1.0, size=[1.5, 1.5], color="#8B725044")
    return doc


PRESETS = {
    "arcane_impact": preset_arcane_impact,
    "fire_impact": preset_fire_impact,
    "healing_aura": preset_healing_aura,
    "ground_warning_circle": preset_ground_warning,
    "lightning_beam": preset_lightning_beam,
    "weapon_trail": preset_weapon_trail,
    "portal": preset_portal,
    "dust_burst": preset_dust_burst,
}


def list_presets() -> list[str]:
    return sorted(PRESETS)


def make_preset(name: str) -> dict[str, Any]:
    if name not in PRESETS:
        raise KeyError(f"Unknown preset '{name}'. Available presets: {', '.join(list_presets())}")
    return PRESETS[name]()
