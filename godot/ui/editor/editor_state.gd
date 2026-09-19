class_name VFXEditorState
extends RefCounted

## Editor-only UI state that does not belong in canonical .vfx.json.

var solo_layer_id: String = ""
var locked_layers: Dictionary = {}


func is_locked(layer_id: String) -> bool:
	return bool(locked_layers.get(layer_id, false))


func set_locked(layer_id: String, locked: bool) -> void:
	if locked:
		locked_layers[layer_id] = true
	else:
		locked_layers.erase(layer_id)


func toggle_solo(layer_id: String) -> void:
	if solo_layer_id == layer_id:
		solo_layer_id = ""
	else:
		solo_layer_id = layer_id


func clear_for_document() -> void:
	solo_layer_id = ""
	locked_layers.clear()
