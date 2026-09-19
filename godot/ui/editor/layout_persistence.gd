class_name VFXLayoutPersistence
extends RefCounted

const PATH := "user://vfx_forge_layout.json"


static func load_state() -> Dictionary:
	if not FileAccess.file_exists(PATH):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(PATH))
	return parsed if parsed is Dictionary else {}


static func save_state(state: Dictionary) -> void:
	var file := FileAccess.open(PATH, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(state, "\t"))


static func default_state() -> Dictionary:
	return {
		"main_split": 260,
		"content_split": 175,
		"editor_split": 520,
		"workspace_tab": 0,
		"stage_preset": "mmo_combat",
		"grid_visible": true,
		"bounds_visible": false,
		"backdrop_index": 0,
		"camera_index": 0,
		"playback_speed_index": 2,
		"panels": {
			"outliner": true,
			"inspector": true,
			"bottom": true,
		},
	}
