class_name VFXInspectorSchema
extends RefCounted

## Schema-driven inspector field definitions for layer and document editing.


static func document_fields() -> Array[Dictionary]:
	return [
		{"kind": "text", "label": "Display name", "path": "name", "tooltip": "Human-readable effect name shown in the editor."},
		{"kind": "number", "label": "Duration (seconds)", "path": "duration", "min": 0.01, "max": 3600.0, "step": 0.01, "tooltip": "Total effect duration in seconds."},
		{"kind": "number", "label": "Deterministic seed", "path": "seed", "min": -2147483648.0, "max": 2147483647.0, "step": 1.0, "tooltip": "Seed for reproducible preview and export."},
		{"kind": "bool", "label": "Loop preview", "path": "loop", "tooltip": "Restart preview when playback reaches the end."},
	]


static func layer_common_fields() -> Array[Dictionary]:
	return [
		{"kind": "text", "label": "Layer name", "path": "name", "layer": true},
		{"kind": "bool", "label": "Enabled", "path": "enabled", "layer": true},
		{"kind": "number", "label": "Start (seconds)", "path": "start", "min": 0.0, "max": 3600.0, "step": 0.01, "layer": true, "tooltip": "When this layer becomes active."},
		{"kind": "number", "label": "Duration (seconds)", "path": "duration", "min": 0.01, "max": 3600.0, "step": 0.01, "layer": true, "tooltip": "How long this layer runs."},
	]


static func layer_property_fields(layer_type: String) -> Array[Dictionary]:
	match layer_type:
		"particle", "mesh_particle":
			return [
				{"kind": "number", "label": "Amount", "path": "amount", "min": 0.0, "max": 200000.0, "step": 1.0, "layer": true, "properties": true, "tooltip": "Maximum simultaneous particles."},
				{"kind": "number", "label": "Lifetime", "path": "lifetime", "min": 0.01, "max": 3600.0, "step": 0.01, "layer": true, "properties": true},
				{"kind": "number", "label": "Initial velocity", "path": "initial_velocity_min", "min": 0.0, "max": 100.0, "step": 0.05, "layer": true, "properties": true},
				{"kind": "option", "label": "Emission shape", "path": "emission_shape", "options": ["point", "box", "sphere", "sphere_surface", "ring", "disc", "line", "cone"], "layer": true, "properties": true},
				{"kind": "vector", "label": "Gravity", "path": "gravity", "layer": true, "properties": true, "default": [0.0, -2.0, 0.0]},
			]
		"light":
			return [
				{"kind": "number", "label": "Energy", "path": "energy", "min": 0.0, "max": 100.0, "step": 0.1, "layer": true, "properties": true, "slider": true},
				{"kind": "number", "label": "Range", "path": "range", "min": 0.1, "max": 100.0, "step": 0.1, "layer": true, "properties": true},
				{"kind": "color", "label": "Color", "path": "color", "layer": true, "properties": true},
			]
		"sprite", "decal", "mesh_effect":
			return [
				{"kind": "vector", "label": "Size", "path": "size", "layer": true, "properties": true, "default": [1.0, 1.0, 1.0] if layer_type == "mesh_effect" else [1.0, 1.0]},
				{"kind": "color", "label": "Color", "path": "color", "layer": true, "properties": true},
			]
		"trail":
			return [
				{"kind": "number", "label": "Width", "path": "width", "min": 0.01, "max": 10.0, "step": 0.01, "layer": true, "properties": true},
				{"kind": "number", "label": "Trail lifetime", "path": "lifetime", "min": 0.02, "max": 10.0, "step": 0.01, "layer": true, "properties": true},
				{"kind": "color", "label": "Color", "path": "color", "layer": true, "properties": true},
			]
		"beam":
			return [
				{"kind": "number", "label": "Thickness", "path": "thickness", "min": 0.01, "max": 10.0, "step": 0.01, "layer": true, "properties": true},
				{"kind": "number", "label": "Noise", "path": "noise", "min": 0.0, "max": 10.0, "step": 0.01, "layer": true, "properties": true},
				{"kind": "vector", "label": "Target", "path": "target", "layer": true, "properties": true, "default": [0.0, 0.0, -4.0]},
			]
		"audio_marker", "event_marker":
			return [
				{"kind": "text", "label": "Event ID", "path": "event_id", "layer": true, "properties": true},
			]
		"child_effect":
			return [
				{"kind": "text", "label": "Effect reference", "path": "effect_id", "layer": true, "properties": true},
			]
		_:
			return []


static func material_fields() -> Array[Dictionary]:
	return [
		{"kind": "option", "label": "Blend mode", "path": "blend_mode", "options": ["additive", "alpha", "premultiplied", "multiply"], "material": true},
		{"kind": "number", "label": "Emissive intensity", "path": "emissive_intensity", "min": 0.0, "max": 100.0, "step": 0.1, "material": true, "slider": true, "tooltip": "Brightness multiplier for unshaded materials."},
	]


static func mesh_asset_types() -> Array[String]:
	return ["mesh_particle", "mesh_effect"]
