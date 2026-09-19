class_name VFXPresetBrowser
extends PopupPanel

signal preset_selected(preset_kind: String, preset_id: String)

const Tokens := preload("res://godot/ui/theme/tokens.gd")
const LayerPresets := preload("res://godot/ui/data/layer_presets.gd")

var _tabs: TabBar
var _list: ItemList
var _description: Label


func _init() -> void:
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", Tokens.SPACE_MD)
	margin.add_theme_constant_override("margin_right", Tokens.SPACE_MD)
	margin.add_theme_constant_override("margin_top", Tokens.SPACE_SM)
	margin.add_theme_constant_override("margin_bottom", Tokens.SPACE_SM)
	add_child(margin)
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", Tokens.SPACE_SM)
	margin.add_child(outer)

	var heading := Label.new()
	heading.text = "Preset Browser"
	heading.add_theme_color_override("font_color", Tokens.TEXT_HEADING)
	outer.add_child(heading)

	_tabs = TabBar.new()
	_tabs.add_tab("Building Blocks")
	_tabs.add_tab("Effect Templates")
	_tabs.tab_changed.connect(_refresh_list)
	outer.add_child(_tabs)

	_list = ItemList.new()
	_list.custom_minimum_size = Vector2(520, 260)
	_list.item_activated.connect(_on_item_activated)
	outer.add_child(_list)

	_description = Label.new()
	_description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_description.custom_minimum_size.y = 42
	_description.add_theme_color_override("font_color", Tokens.TEXT_SECONDARY)
	_description.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	outer.add_child(_description)
	_list.item_selected.connect(_on_item_selected)
	_refresh_list()


func open_browser() -> void:
	popup_centered_clamped(Vector2(560, 420), 0.8)


func _refresh_list() -> void:
	_list.clear()
	_description.text = ""
	if _tabs.current_tab == 0:
		for preset in LayerPresets.building_blocks():
			_list.add_item(str(preset.get("label", "Preset")))
			_list.set_item_metadata(_list.item_count - 1, "block:" + str(preset.get("id", "")))
	else:
		for preset in LayerPresets.effect_templates():
			_list.add_item(str(preset.get("label", "Template")))
			_list.set_item_metadata(_list.item_count - 1, "template:" + str(preset.get("id", "")))


func _on_item_selected(index: int) -> void:
	var metadata := str(_list.get_item_metadata(index))
	var kind := metadata.get_slice(":", 0)
	var preset_id := metadata.get_slice(":", 1)
	var source: Array = LayerPresets.building_blocks() if kind == "block" else LayerPresets.effect_templates()
	for preset in source:
		if str(preset.get("id", "")) == preset_id:
			_description.text = str(preset.get("description", ""))
			return


func _on_item_activated(index: int) -> void:
	var metadata := str(_list.get_item_metadata(index))
	var kind := metadata.get_slice(":", 0)
	var preset_id := metadata.get_slice(":", 1)
	hide()
	preset_selected.emit(kind, preset_id)
