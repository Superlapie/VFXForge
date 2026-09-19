class_name VFXLayerPresets
extends RefCounted

## Deterministic layer and template presets for the preset browser.


static func layer_types() -> Array[String]:
	return [
		"particle", "mesh_particle", "sprite", "light", "trail", "beam",
		"decal", "mesh_effect", "event_marker", "child_effect",
	]


static func building_blocks() -> Array[Dictionary]:
	return [
		{"id": "burst", "label": "Burst", "description": "One-shot radial particle burst", "layers": [{"type": "particle", "prefix": "burst", "overrides": {"properties.amount": 48, "properties.explosiveness": 0.95, "properties.spread": 180.0}}]},
		{"id": "glow", "label": "Glow", "description": "Additive sprite flash", "layers": [{"type": "sprite", "prefix": "glow", "overrides": {"properties.size": [1.2, 1.2], "material.emissive_intensity": 2.5}}]},
		{"id": "ground_ring", "label": "Ground Ring", "description": "Floor telegraph decal", "layers": [{"type": "decal", "prefix": "ground_ring", "overrides": {"properties.size": [2.5, 2.5], "properties.color": "#5D48B6AA"}}]},
		{"id": "impact_flash", "label": "Impact Flash", "description": "Flash plus sparks for hits", "layers": [
			{"type": "light", "prefix": "impact_light", "overrides": {"properties.energy": 3.0, "properties.range": 2.5, "duration": 0.35}},
			{"type": "particle", "prefix": "impact_sparks", "overrides": {"properties.amount": 36, "properties.lifetime": 0.45, "duration": 0.5}},
		]},
		{"id": "ribbon", "label": "Ribbon", "description": "Trail ribbon layer", "layers": [{"type": "trail", "prefix": "ribbon", "overrides": {"properties.width": 0.22, "properties.lifetime": 0.4}}]},
	]


static func effect_templates() -> Array[Dictionary]:
	return [
		{"id": "magic_impact", "label": "Magic Impact", "description": "Flash, sparks, and ground ring", "layers": [
			{"type": "light", "prefix": "impact_light", "overrides": {"duration": 0.4}},
			{"type": "particle", "prefix": "impact_sparks", "overrides": {"properties.amount": 64}},
			{"type": "decal", "prefix": "impact_decal", "overrides": {"properties.size": [1.8, 1.8]}},
		]},
		{"id": "ground_telegraph", "label": "Ground Telegraph", "description": "Warning ring for AoE placement", "layers": [
			{"type": "decal", "prefix": "telegraph", "overrides": {"properties.size": [3.0, 3.0], "start": 0.0, "duration": 2.0}},
			{"type": "mesh_effect", "prefix": "telegraph_ring", "overrides": {"properties.size": [3.0, 3.0, 0.08], "properties.color": "#FF8844AA"}},
		]},
		{"id": "portal", "label": "Portal", "description": "Ring mesh with orbiting motes", "layers": [
			{"type": "mesh_effect", "prefix": "portal_ring", "overrides": {"properties.size": [2.0, 2.0, 0.35], "properties.color": "#A980FFFF"}},
			{"type": "particle", "prefix": "portal_motes", "overrides": {"properties.amount": 96, "properties.emission_shape": "ring", "properties.emission_radius": 1.1}},
			{"type": "light", "prefix": "portal_light", "overrides": {"properties.energy": 2.5, "properties.range": 4.0}},
		]},
		{"id": "weapon_trail", "label": "Weapon Trail", "description": "Trail for melee swings", "layers": [
			{"type": "trail", "prefix": "weapon_trail", "overrides": {"properties.width": 0.16, "properties.lifetime": 0.28}},
			{"type": "particle", "prefix": "weapon_sparks", "overrides": {"properties.amount": 16, "properties.lifetime": 0.2}},
		]},
	]
