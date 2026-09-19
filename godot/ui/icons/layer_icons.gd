class_name VFXLayerIcons
extends RefCounted


static func glyph(layer_type: String) -> String:
	match layer_type:
		"particle", "mesh_particle":
			return "✦"
		"light":
			return "☀"
		"trail":
			return "〰"
		"beam":
			return "⚡"
		"decal":
			return "▣"
		"mesh_effect":
			return "◇"
		"sprite":
			return "◻"
		"audio_marker", "event_marker":
			return "◆"
		"child_effect":
			return "⎇"
		_:
			return "•"


static func type_label(layer_type: String) -> String:
	match layer_type:
		"particle":
			return "Particle"
		"mesh_particle":
			return "Mesh Particle"
		"mesh_effect":
			return "Mesh Effect"
		"sprite":
			return "Sprite"
		"light":
			return "Light"
		"trail":
			return "Trail"
		"beam":
			return "Beam"
		"decal":
			return "Decal"
		"audio_marker":
			return "Audio Marker"
		"event_marker":
			return "Event Marker"
		"child_effect":
			return "Child Effect"
		_:
			return layer_type.capitalize()
