class_name VFXCurvesWorkspace
extends PanelContainer

signal edit_requested(path: String, value: Variant)
signal open_layer_requested(layer_id: String)

const Tokens := preload("res://godot/ui/theme/tokens.gd")
const CurveEditorScript := preload("res://godot/editor/curve_editor.gd")

var layer_menu: OptionButton
var curve_menu: OptionButton
var curve_editor: VFXCurveEditor

var _document: Dictionary = {}
var _selected_layer_id := ""
var _current_curve_key := "scale"


func _init() -> void:
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", Tokens.SPACE_SM)
	add_child(outer)

	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", Tokens.SPACE_SM)
	outer.add_child(header)

	var layer_label := Label.new()
	layer_label.text = "Layer"
	layer_label.add_theme_color_override("font_color", Tokens.TEXT_SECONDARY)
	header.add_child(layer_label)

	layer_menu = OptionButton.new()
	layer_menu.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	layer_menu.item_selected.connect(_on_layer_selected)
	header.add_child(layer_menu)

	var curve_label := Label.new()
	curve_label.text = "Curve"
	curve_label.add_theme_color_override("font_color", Tokens.TEXT_SECONDARY)
	header.add_child(curve_label)

	curve_menu = OptionButton.new()
	curve_menu.custom_minimum_size.x = 120
	curve_menu.item_selected.connect(_on_curve_selected)
	header.add_child(curve_menu)

	curve_editor = CurveEditorScript.new()
	curve_editor.size_flags_vertical = Control.SIZE_EXPAND_FILL
	curve_editor.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	curve_editor.curve_changed.connect(_on_curve_changed)
	outer.add_child(curve_editor)

	var hint := Label.new()
	hint.text = "Drag points to edit. Right-click removes a point. Changes write to the canonical curve JSON."
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	hint.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	outer.add_child(hint)


func set_document(document: Dictionary, selected_layer_id: String) -> void:
	_document = document
	_selected_layer_id = selected_layer_id
	_rebuild_layer_menu()
	_refresh_curve_editor()


func focus_curve(layer_id: String, curve_key: String) -> void:
	_selected_layer_id = layer_id
	_current_curve_key = curve_key
	set_document(_document, layer_id)


func _rebuild_layer_menu() -> void:
	layer_menu.clear()
	var select_index := 0
	var index := 0
	for layer_variant in _document.get("layers", []):
		if not layer_variant is Dictionary:
			continue
		var layer: Dictionary = layer_variant
		var layer_id := str(layer.get("id", ""))
		layer_menu.add_item(str(layer.get("name", layer_id)))
		layer_menu.set_item_metadata(index, layer_id)
		if layer_id == _selected_layer_id:
			select_index = index
		index += 1
	if layer_menu.item_count > 0:
		layer_menu.select(select_index)
		_selected_layer_id = str(layer_menu.get_item_metadata(select_index))


func _refresh_curve_editor() -> void:
	curve_menu.clear()
	var layer := _find_layer(_selected_layer_id)
	if layer.is_empty():
		curve_editor.set_curve({})
		return
	var curves: Dictionary = layer.get("curves", {})
	var keys: Array = curves.keys()
	keys.sort()
	var select_index := 0
	for key_index in range(keys.size()):
		var key: String = str(keys[key_index])
		curve_menu.add_item(key.capitalize())
		curve_menu.set_item_metadata(key_index, key)
		if key == _current_curve_key:
			select_index = key_index
	if curve_menu.item_count == 0:
		curve_menu.add_item("Scale")
		curve_menu.set_item_metadata(0, "scale")
		_current_curve_key = "scale"
	else:
		curve_menu.select(select_index)
		_current_curve_key = str(curve_menu.get_item_metadata(select_index))
	var curve_value: Variant = layer.get("curves", {}).get(_current_curve_key, {"interpolation": "linear", "points": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]})
	curve_editor.set_curve(curve_value)


func _find_layer(layer_id: String) -> Dictionary:
	for layer_variant in _document.get("layers", []):
		if layer_variant is Dictionary and str(layer_variant.get("id", "")) == layer_id:
			return layer_variant
	return {}


func _on_layer_selected(index: int) -> void:
	_selected_layer_id = str(layer_menu.get_item_metadata(index))
	open_layer_requested.emit(_selected_layer_id)
	_refresh_curve_editor()


func _on_curve_selected(index: int) -> void:
	_current_curve_key = str(curve_menu.get_item_metadata(index))
	_refresh_curve_editor()


func _on_curve_changed(value: Dictionary) -> void:
	if _selected_layer_id.is_empty():
		return
	edit_requested.emit("layers." + _selected_layer_id + ".curves." + _current_curve_key, value)
