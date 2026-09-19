class_name VFXOutlinerPanel
extends PanelContainer

signal layer_selected(layer_id: String)
signal duplicate_requested()
signal remove_requested()
signal rename_requested()
signal visibility_toggled(layer_id: String)
signal solo_toggled(layer_id: String)
signal lock_toggled(layer_id: String)
signal reorder_requested(layer_id: String, target_index: int)
signal filter_changed()
signal copy_id_requested(layer_id: String)

const Tokens := preload("res://godot/ui/theme/tokens.gd")
const LayerIcons := preload("res://godot/ui/icons/layer_icons.gd")
const LayerTreeScript := preload("res://godot/ui/components/layer_tree.gd")

var hierarchy: VFXLayerTree
var hierarchy_menu: PopupMenu
var filter_field: LineEdit

var _filter_text := ""
var _solo_layer_id := ""
var _locked_layers: Dictionary = {}
var _suppress_selection_signal := false


func _init() -> void:
	custom_minimum_size.x = 230
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", Tokens.SPACE_SM)
	add_child(outer)

	var heading := Label.new()
	heading.text = "Layers"
	heading.add_theme_font_size_override("font_size", Tokens.FONT_HEADING)
	heading.add_theme_color_override("font_color", Tokens.TEXT_HEADING)
	outer.add_child(heading)

	var filter_row := HBoxContainer.new()
	filter_row.add_theme_constant_override("separation", Tokens.SPACE_XS)
	var filter_icon := Label.new()
	filter_icon.text = "🔍"
	filter_icon.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	filter_row.add_child(filter_icon)
	filter_field = LineEdit.new()
	filter_field.placeholder_text = "Filter layers..."
	filter_field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	filter_field.text_changed.connect(_on_filter_changed)
	filter_row.add_child(filter_field)
	outer.add_child(filter_row)

	hierarchy = LayerTreeScript.new()
	hierarchy.name = "Hierarchy"
	hierarchy.hide_root = true
	hierarchy.size_flags_vertical = Control.SIZE_EXPAND_FILL
	hierarchy.columns = 4
	hierarchy.set_column_expand(0, true)
	hierarchy.set_column_custom_minimum_width(1, 24)
	hierarchy.set_column_custom_minimum_width(2, 20)
	hierarchy.set_column_custom_minimum_width(3, 20)
	hierarchy.allow_reselect = true
	hierarchy.allow_rmb_select = true
	hierarchy.item_selected.connect(_on_item_selected)
	hierarchy.gui_input.connect(_on_hierarchy_gui_input)
	hierarchy.reorder_requested.connect(reorder_requested.emit)
	outer.add_child(hierarchy)

	hierarchy_menu = PopupMenu.new()
	hierarchy_menu.add_item("Duplicate", 1)
	hierarchy_menu.add_item("Rename", 3)
	hierarchy_menu.add_item("Solo", 5)
	hierarchy_menu.add_item("Toggle Enabled", 6)
	hierarchy_menu.add_separator()
	hierarchy_menu.add_item("Copy Layer ID", 4)
	hierarchy_menu.add_separator()
	hierarchy_menu.add_item("Move Up", 7)
	hierarchy_menu.add_item("Move Down", 8)
	hierarchy_menu.add_separator()
	hierarchy_menu.add_item("Delete", 2)
	hierarchy_menu.id_pressed.connect(_on_menu_pressed)
	add_child(hierarchy_menu)


func set_editor_overlays(solo_layer_id: String, locked_layers: Dictionary) -> void:
	_solo_layer_id = solo_layer_id
	_locked_layers = locked_layers


func populate(document: Dictionary, selected_layer_id: String) -> void:
	hierarchy.clear()
	var root := hierarchy.create_item()
	var effect_item := hierarchy.create_item(root)
	effect_item.set_text(0, str(document.get("name", "Effect")))
	effect_item.set_metadata(0, "")
	effect_item.set_selectable(0, false)
	for layer_variant in document.get("layers", []):
		if not layer_variant is Dictionary:
			continue
		var layer: Dictionary = layer_variant
		var layer_id := str(layer.get("id", ""))
		var layer_name := str(layer.get("name", layer_id))
		var layer_type := str(layer.get("type", ""))
		if not _filter_text.is_empty() and not layer_name.to_lower().contains(_filter_text) and not layer_type.contains(_filter_text):
			continue
		var item := hierarchy.create_item(root)
		var enabled: bool = bool(layer.get("enabled", true))
		item.set_text(0, LayerIcons.glyph(layer_type) + "  " + layer_name)
		item.set_text(1, "👁" if enabled else "◌")
		item.set_text(2, "S" if _solo_layer_id == layer_id else "·")
		item.set_text(3, "🔒" if bool(_locked_layers.get(layer_id, false)) else "·")
		item.set_metadata(0, layer_id)
		item.set_tooltip_text(0, layer_type + "  •  " + layer_id)
		if not enabled:
			item.set_custom_color(0, Tokens.TEXT_MUTED)
			item.set_custom_color(1, Tokens.TEXT_MUTED)
		if _solo_layer_id == layer_id:
			item.set_custom_color(2, Tokens.BRAND_AMBER)
		if bool(_locked_layers.get(layer_id, false)):
			item.set_custom_color(3, Tokens.WARNING)
	if not selected_layer_id.is_empty():
		select_layer(selected_layer_id)


func layer_ids_in_order(document: Dictionary) -> Array[String]:
	var ids: Array[String] = []
	for layer_variant in document.get("layers", []):
		if layer_variant is Dictionary:
			var layer_id := str(layer_variant.get("id", ""))
			if layer_id.is_empty():
				continue
			if not _filter_text.is_empty():
				var layer_name := str(layer_variant.get("name", layer_id)).to_lower()
				var layer_type := str(layer_variant.get("type", ""))
				if not layer_name.contains(_filter_text) and not layer_type.contains(_filter_text):
					continue
			ids.append(layer_id)
	return ids


func select_layer(layer_id: String) -> void:
	var root := hierarchy.get_root()
	if root == null:
		return
	_suppress_selection_signal = true
	var child := root.get_first_child()
	while child != null:
		if str(child.get_metadata(0)) == layer_id:
			child.select(0)
			_suppress_selection_signal = false
			return
		child = child.get_next()
	_suppress_selection_signal = false


func _on_item_selected() -> void:
	if _suppress_selection_signal:
		return
	var item := hierarchy.get_selected()
	if item == null:
		return
	var layer_id := str(item.get_metadata(0))
	if not layer_id.is_empty():
		layer_selected.emit(layer_id)


func _on_filter_changed(text: String) -> void:
	_filter_text = text.to_lower()
	filter_changed.emit()


func _on_hierarchy_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var item := hierarchy.get_item_at_position(event.position)
		if item == null:
			return
		var layer_id := str(item.get_metadata(0))
		if layer_id.is_empty():
			return
		var column := hierarchy.get_column_at_position(event.position)
		match column:
			1:
				visibility_toggled.emit(layer_id)
				get_viewport().set_input_as_handled()
				return
			2:
				solo_toggled.emit(layer_id)
				get_viewport().set_input_as_handled()
				return
			3:
				lock_toggled.emit(layer_id)
				get_viewport().set_input_as_handled()
				return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
		var item := hierarchy.get_item_at_position(event.position)
		if item != null:
			item.select(0)
			var layer_id := str(item.get_metadata(0))
			if not layer_id.is_empty():
				layer_selected.emit(layer_id)
				hierarchy_menu.position = Vector2i(get_global_mouse_position())
				hierarchy_menu.popup()
				get_viewport().set_input_as_handled()


func _on_menu_pressed(id: int) -> void:
	match id:
		1:
			duplicate_requested.emit()
		2:
			remove_requested.emit()
		3:
			rename_requested.emit()
		4:
			var copy_item := hierarchy.get_selected()
			if copy_item != null:
				var copy_id := str(copy_item.get_metadata(0))
				if not copy_id.is_empty():
					copy_id_requested.emit(copy_id)
		5:
			var item := hierarchy.get_selected()
			if item != null:
				solo_toggled.emit(str(item.get_metadata(0)))
		6:
			var selected := hierarchy.get_selected()
			if selected != null:
				visibility_toggled.emit(str(selected.get_metadata(0)))
		7:
			var move_item := hierarchy.get_selected()
			if move_item != null:
				var move_id := str(move_item.get_metadata(0))
				reorder_requested.emit(move_id, max(0, _layer_index_for_id(move_id) - 1))
		8:
			var down_item := hierarchy.get_selected()
			if down_item != null:
				var down_id := str(down_item.get_metadata(0))
				reorder_requested.emit(down_id, _layer_index_for_id(down_id) + 1)


func _layer_index_for_id(layer_id: String) -> int:
	var index := 0
	for child in _all_layer_items():
		if str(child.get_metadata(0)) == layer_id:
			return index
		index += 1
	return 0


func _all_layer_items() -> Array[TreeItem]:
	var items: Array[TreeItem] = []
	var root := hierarchy.get_root()
	if root == null:
		return items
	var child := root.get_first_child()
	while child != null:
		if not str(child.get_metadata(0)).is_empty():
			items.append(child)
		child = child.get_next()
	return items
