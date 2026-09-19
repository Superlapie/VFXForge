class_name VFXCommandPalette
extends PopupPanel

signal command_invoked(command_id: String)

const Tokens := preload("res://godot/ui/theme/tokens.gd")

var _filter: LineEdit
var _list: ItemList
var _commands: Array[Dictionary] = []


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
	_filter = LineEdit.new()
	_filter.placeholder_text = "Search commands..."
	_filter.text_changed.connect(_refresh_list)
	_filter.gui_input.connect(_on_filter_gui_input)
	outer.add_child(_filter)
	_list = ItemList.new()
	_list.custom_minimum_size = Vector2(520, 280)
	_list.item_activated.connect(_on_item_activated)
	_list.item_selected.connect(func(_index: int) -> void: pass)
	outer.add_child(_list)
	_build_commands()


func open_palette() -> void:
	_filter.text = ""
	_refresh_list()
	popup_centered_clamped(Vector2(560, 360), 0.8)
	_filter.grab_focus()


func _build_commands() -> void:
	_commands = [
		{"id": "file.open", "label": "Open Effect", "group": "File"},
		{"id": "file.save", "label": "Save Effect", "group": "File"},
		{"id": "file.validate", "label": "Validate Effect", "group": "File"},
		{"id": "file.export", "label": "Export Godot Effect", "group": "File"},
		{"id": "edit.undo", "label": "Undo", "group": "Edit"},
		{"id": "edit.redo", "label": "Redo", "group": "Edit"},
		{"id": "layer.add_particle", "label": "Add Layer: Particle", "group": "Layers"},
		{"id": "layer.add_light", "label": "Add Layer: Light", "group": "Layers"},
		{"id": "layer.add_mesh_effect", "label": "Add Layer: Mesh Effect", "group": "Layers"},
		{"id": "preset.browser", "label": "Open Preset Browser", "group": "Presets"},
		{"id": "view.frame_effect", "label": "Frame Effect", "group": "View"},
		{"id": "view.reset_camera", "label": "Reset Camera", "group": "View"},
		{"id": "workspace.timeline", "label": "Switch to Timeline", "group": "Workspace"},
		{"id": "workspace.curves", "label": "Switch to Curves", "group": "Workspace"},
		{"id": "workspace.gradients", "label": "Switch to Gradients", "group": "Workspace"},
		{"id": "workspace.events", "label": "Switch to Events", "group": "Workspace"},
		{"id": "workspace.diagnostics", "label": "Switch to Diagnostics", "group": "Workspace"},
		{"id": "raw.copy_layer_id", "label": "Copy Selected Layer ID", "group": "Developer"},
	]


func _refresh_list() -> void:
	var query := _filter.text.to_lower()
	_list.clear()
	for command in _commands:
		var haystack := (str(command.get("label", "")) + " " + str(command.get("group", ""))).to_lower()
		if query.is_empty() or query in haystack:
			_list.add_item(str(command.get("label", "")))
			_list.set_item_metadata(_list.item_count - 1, str(command.get("id", "")))


func _on_item_activated(index: int) -> void:
	var command_id := str(_list.get_item_metadata(index))
	hide()
	command_invoked.emit(command_id)


func _on_filter_gui_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_ESCAPE:
			hide()
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_DOWN:
			if _list.item_count > 0:
				_list.grab_focus()
				_list.select(0)
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_ENTER or event.keycode == KEY_KP_ENTER:
			if _list.item_count > 0:
				_on_item_activated(_list.get_selected_items()[0] if _list.get_selected_items().size() > 0 else 0)
			get_viewport().set_input_as_handled()
