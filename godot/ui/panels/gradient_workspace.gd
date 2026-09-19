class_name VFXGradientWorkspace
extends PanelContainer

signal edit_requested(path: String, value: Variant)
signal open_layer_requested(layer_id: String)

const Tokens := preload("res://godot/ui/theme/tokens.gd")
const GradientEditorScript := preload("res://godot/editor/gradient_editor.gd")

var layer_menu: OptionButton
var gradient_editor: VFXGradientEditor
var color_picker: ColorPickerButton

var _document: Dictionary = {}
var _selected_layer_id := ""


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

	var color_label := Label.new()
	color_label.text = "Stop color"
	color_label.add_theme_color_override("font_color", Tokens.TEXT_SECONDARY)
	header.add_child(color_label)

	color_picker = ColorPickerButton.new()
	color_picker.custom_minimum_size.x = 54
	color_picker.color_changed.connect(_on_color_changed)
	header.add_child(color_picker)

	gradient_editor = GradientEditorScript.new()
	gradient_editor.custom_minimum_size.y = 72
	gradient_editor.size_flags_vertical = Control.SIZE_EXPAND_FILL
	gradient_editor.gradient_changed.connect(_on_gradient_changed)
	gradient_editor.stop_selected.connect(_on_stop_selected)
	outer.add_child(gradient_editor)

	var hint := Label.new()
	hint.text = "Drag stops to edit color over life. Right-click removes a stop. Double-click the inspector preview to open this workspace."
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	hint.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	outer.add_child(hint)


func set_document(document: Dictionary, selected_layer_id: String) -> void:
	_document = document
	_selected_layer_id = selected_layer_id
	_rebuild_layer_menu()
	_refresh_gradient_editor()


func focus_gradient(layer_id: String) -> void:
	_selected_layer_id = layer_id
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


func _refresh_gradient_editor() -> void:
	var layer := _find_layer(_selected_layer_id)
	if layer.is_empty():
		gradient_editor.set_gradient([])
		return
	gradient_editor.set_gradient(layer.get("gradient", []))


func _find_layer(layer_id: String) -> Dictionary:
	for layer_variant in _document.get("layers", []):
		if layer_variant is Dictionary and str(layer_variant.get("id", "")) == layer_id:
			return layer_variant
	return {}


func _on_layer_selected(index: int) -> void:
	_selected_layer_id = str(layer_menu.get_item_metadata(index))
	open_layer_requested.emit(_selected_layer_id)
	_refresh_gradient_editor()


func _on_gradient_changed(value: Array) -> void:
	if _selected_layer_id.is_empty():
		return
	edit_requested.emit("layers." + _selected_layer_id + ".gradient", value)


func _on_stop_selected(_index: int, color: Color) -> void:
	color_picker.color = color


func _on_color_changed(color: Color) -> void:
	gradient_editor.set_selected_color(color)
