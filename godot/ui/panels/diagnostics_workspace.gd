class_name VFXDiagnosticsWorkspace
extends PanelContainer

signal navigate_requested(layer_id: String, path: String)

const Tokens := preload("res://godot/ui/theme/tokens.gd")

var summary_label: Label
var list: ItemList
var detail_label: Label
var goto_button: Button

var _entries: Array[Dictionary] = []
var _selected_index := -1


func _init() -> void:
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", Tokens.SPACE_SM)
	add_child(outer)

	summary_label = Label.new()
	summary_label.text = "No diagnostics"
	summary_label.add_theme_color_override("font_color", Tokens.TEXT_HEADING)
	outer.add_child(summary_label)

	list = ItemList.new()
	list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	list.item_selected.connect(_on_item_selected)
	outer.add_child(list)

	detail_label = Label.new()
	detail_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	detail_label.custom_minimum_size.y = 48
	detail_label.add_theme_color_override("font_color", Tokens.TEXT_SECONDARY)
	outer.add_child(detail_label)

	goto_button = Button.new()
	goto_button.text = "Go to Layer"
	goto_button.pressed.connect(_on_goto_pressed)
	outer.add_child(goto_button)


func set_entries(entries: Array) -> void:
	_entries.clear()
	for entry_variant in entries:
		if entry_variant is Dictionary:
			_entries.append(entry_variant)
	_rebuild()


func issue_count() -> int:
	return _entries.size()


func _rebuild() -> void:
	list.clear()
	_selected_index = -1
	detail_label.text = ""
	if _entries.is_empty():
		summary_label.text = "Diagnostics clear"
		summary_label.add_theme_color_override("font_color", Tokens.SUCCESS)
		goto_button.disabled = true
		return
	var errors := 0
	var warnings := 0
	for entry in _entries:
		if str(entry.get("severity", "warning")) == "error":
			errors += 1
		else:
			warnings += 1
	summary_label.text = "%d issue(s)  •  %d error  •  %d warning" % [_entries.size(), errors, warnings]
	summary_label.add_theme_color_override("font_color", Tokens.WARNING if errors > 0 else Tokens.BRAND_AMBER)
	for index in range(_entries.size()):
		var entry: Dictionary = _entries[index]
		var prefix := "ERROR" if str(entry.get("severity")) == "error" else "WARN"
		list.add_item("[%s] %s" % [prefix, str(entry.get("title", "Issue"))])
		list.set_item_metadata(index, index)
	goto_button.disabled = true


func _on_item_selected(index: int) -> void:
	_selected_index = index
	if index < 0 or index >= _entries.size():
		return
	var entry: Dictionary = _entries[index]
	detail_label.text = str(entry.get("message", "")) + "\n" + str(entry.get("path", ""))
	goto_button.disabled = str(entry.get("layer_id", "")).is_empty()


func _on_goto_pressed() -> void:
	if _selected_index < 0 or _selected_index >= _entries.size():
		return
	var entry: Dictionary = _entries[_selected_index]
	navigate_requested.emit(str(entry.get("layer_id", "")), str(entry.get("path", "")))
