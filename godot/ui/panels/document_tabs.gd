class_name VFXDocumentTabs
extends PanelContainer

signal tab_selected(index: int)
signal tab_close_requested(index: int)
signal new_tab_requested()

const Tokens := preload("res://godot/ui/theme/tokens.gd")

var tab_bar: TabBar
var close_tab_button: Button
var new_tab_button: Button

var _suppress := false


func _init() -> void:
	custom_minimum_size.y = 34
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", Tokens.SPACE_XS)
	row.add_theme_constant_override("margin_left", Tokens.SPACE_MD)
	row.add_theme_constant_override("margin_right", Tokens.SPACE_MD)
	row.add_theme_constant_override("margin_top", 4)
	row.add_theme_constant_override("margin_bottom", 2)
	add_child(row)

	tab_bar = TabBar.new()
	tab_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tab_bar.tab_changed.connect(_on_tab_changed)
	row.add_child(tab_bar)

	close_tab_button = Button.new()
	close_tab_button.text = "×"
	close_tab_button.tooltip_text = "Close active effect tab"
	close_tab_button.custom_minimum_size.x = 28
	close_tab_button.pressed.connect(func() -> void: tab_close_requested.emit(tab_bar.current_tab))
	row.add_child(close_tab_button)

	new_tab_button = Button.new()
	new_tab_button.text = "+"
	new_tab_button.tooltip_text = "New effect tab"
	new_tab_button.custom_minimum_size.x = 28
	new_tab_button.pressed.connect(new_tab_requested.emit)
	row.add_child(new_tab_button)


func set_tabs(labels: PackedStringArray, active_index: int) -> void:
	_suppress = true
	while tab_bar.get_tab_count() > 0:
		tab_bar.remove_tab(tab_bar.get_tab_count() - 1)
	for label in labels:
		tab_bar.add_tab(label)
	if tab_bar.get_tab_count() > 0:
		tab_bar.current_tab = clampi(active_index, 0, tab_bar.get_tab_count() - 1)
	close_tab_button.disabled = tab_bar.get_tab_count() <= 1
	_suppress = false


func set_active_tab(index: int) -> void:
	if index < 0 or index >= tab_bar.get_tab_count():
		return
	_suppress = true
	tab_bar.current_tab = index
	_suppress = false


func _on_tab_changed(index: int) -> void:
	if _suppress:
		return
	tab_selected.emit(index)
