class_name VFXAppMenubar
extends PanelContainer

signal menu_action(action: String)
signal validate_requested()
signal export_requested()
signal panel_visibility_changed(panel_id: String, visible: bool)

const Tokens := preload("res://godot/ui/theme/tokens.gd")

var project_title: Label
var dirty_indicator: Label
var document_tab: Label

var _panel_menu_ids := {
	"outliner": 41,
	"inspector": 42,
	"bottom": 43,
}


func _init() -> void:
	custom_minimum_size.y = 36
	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", Tokens.SPACE_MD)
	bar.add_theme_constant_override("margin_left", Tokens.SPACE_MD)
	bar.add_theme_constant_override("margin_right", Tokens.SPACE_MD)
	bar.add_theme_constant_override("margin_top", 6)
	bar.add_theme_constant_override("margin_bottom", 6)
	add_child(bar)

	var brand := Label.new()
	brand.text = "VFX FORGE"
	brand.add_theme_font_size_override("font_size", Tokens.FONT_BRAND)
	brand.add_theme_color_override("font_color", Tokens.BRAND_AMBER)
	bar.add_child(brand)

	for menu_name in ["File", "Edit", "View", "Effect", "Window", "Help"]:
		var menu_button := MenuButton.new()
		menu_button.text = menu_name
		menu_button.flat = true
		menu_button.add_theme_color_override("font_color", Tokens.TEXT_SECONDARY)
		_populate_menu(menu_button, menu_name)
		bar.add_child(menu_button)

	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bar.add_child(spacer)

	document_tab = Label.new()
	document_tab.text = "[ Untitled.vfx ]"
	document_tab.add_theme_color_override("font_color", Tokens.TEXT_PRIMARY)
	document_tab.add_theme_font_size_override("font_size", Tokens.FONT_UI)
	bar.add_child(document_tab)

	project_title = Label.new()
	project_title.visible = false
	project_title.text = "Untitled Effect"
	bar.add_child(project_title)

	dirty_indicator = Label.new()
	dirty_indicator.text = ""
	dirty_indicator.add_theme_color_override("font_color", Tokens.BRAND_AMBER)
	bar.add_child(dirty_indicator)

	var validate_button := Button.new()
	validate_button.text = "Validate"
	validate_button.tooltip_text = "Validate the current effect document"
	validate_button.pressed.connect(validate_requested.emit)
	bar.add_child(validate_button)

	var export_button := Button.new()
	export_button.text = "Export"
	export_button.tooltip_text = "Export Godot effect package"
	export_button.pressed.connect(export_requested.emit)
	bar.add_child(export_button)


func set_document_name(name: String, dirty: bool) -> void:
	project_title.text = name
	var suffix := " ●" if dirty else ""
	document_tab.text = "[ " + name + ".vfx" + suffix + " ]"
	dirty_indicator.text = ""


func set_panel_visibility(panels: Dictionary) -> void:
	for menu_button in _menu_buttons():
		if menu_button.text != "Window":
			continue
		var popup: PopupMenu = menu_button.get_popup()
		for panel_id in _panel_menu_ids:
			var menu_id: int = _panel_menu_ids[panel_id]
			var item_index := popup.get_item_index(menu_id)
			if item_index >= 0:
				popup.set_item_checked(item_index, bool(panels.get(panel_id, true)))


func _menu_buttons() -> Array[MenuButton]:
	var buttons: Array[MenuButton] = []
	for child in get_child(0).get_children():
		if child is MenuButton:
			buttons.append(child)
	return buttons


func _populate_menu(menu_button: MenuButton, menu_name: String) -> void:
	var popup: PopupMenu = menu_button.get_popup()
	match menu_name:
		"File":
			popup.add_item("Open...", 1)
			popup.add_item("Save", 2)
			popup.add_item("Save As...", 3)
			popup.add_separator()
			popup.add_item("Export...", 4)
		"Edit":
			popup.add_item("Undo", 10)
			popup.add_item("Redo", 11)
		"View":
			popup.add_item("Frame Effect", 20)
			popup.add_item("Reset Camera", 21)
		"Effect":
			popup.add_item("Validate", 30)
		"Window":
			popup.add_item("Command Palette...", 40)
			popup.add_separator()
			popup.add_check_item("Outliner", 41)
			popup.add_check_item("Inspector", 42)
			popup.add_check_item("Bottom Workspace", 43)
		"Help":
			popup.add_item("About VFX Forge", 50)
	popup.id_pressed.connect(_on_menu_pressed)


func _on_menu_pressed(id: int) -> void:
	for panel_id in _panel_menu_ids:
		if _panel_menu_ids[panel_id] == id:
			for menu_button in _menu_buttons():
				if menu_button.text == "Window":
					var popup: PopupMenu = menu_button.get_popup()
					var item_index := popup.get_item_index(id)
					if item_index >= 0:
						var visible := popup.is_item_checked(item_index)
						popup.set_item_checked(item_index, not visible)
						panel_visibility_changed.emit(panel_id, not visible)
			return
	menu_action.emit(_menu_name_for_id(id) + ":" + str(id))


func _menu_name_for_id(id: int) -> String:
	if id < 10:
		return "File"
	if id < 20:
		return "Edit"
	if id < 30:
		return "View"
	if id < 40:
		return "Effect"
	if id < 50:
		return "Window"
	return "Help"
