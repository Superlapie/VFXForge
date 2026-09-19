class_name VFXAppToolbar
extends PanelContainer

signal add_layer_selected(index: int)
signal command_palette_requested()
signal preset_browser_requested()

const Tokens := preload("res://godot/ui/theme/tokens.gd")

var add_layer_menu: OptionButton


func _init() -> void:
	custom_minimum_size.y = 34
	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", Tokens.SPACE_SM)
	bar.add_theme_constant_override("margin_left", Tokens.SPACE_MD)
	bar.add_theme_constant_override("margin_right", Tokens.SPACE_MD)
	bar.add_theme_constant_override("margin_top", 4)
	bar.add_theme_constant_override("margin_bottom", 4)
	add_child(bar)

	add_layer_menu = OptionButton.new()
	add_layer_menu.name = "AddLayerMenu"
	add_layer_menu.custom_minimum_size.x = 130
	add_layer_menu.add_item("+ Add Layer")
	for layer_type in ["particle", "mesh_particle", "sprite", "light", "trail", "beam", "decal", "mesh_effect", "event_marker", "child_effect"]:
		add_layer_menu.add_item(layer_type.replace("_", " ").capitalize())
	add_layer_menu.item_selected.connect(add_layer_selected.emit)
	bar.add_child(add_layer_menu)

	var presets_button := Button.new()
	presets_button.text = "Presets"
	presets_button.tooltip_text = "Browse building blocks and effect templates"
	presets_button.pressed.connect(preset_browser_requested.emit)
	bar.add_child(presets_button)

	var search := LineEdit.new()
	search.placeholder_text = "Search commands...  Ctrl+K"
	search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	search.editable = false
	search.mouse_filter = Control.MOUSE_FILTER_STOP
	search.gui_input.connect(func(event: InputEvent) -> void:
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			command_palette_requested.emit()
			get_viewport().set_input_as_handled()
	)
	search.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	bar.add_child(search)
