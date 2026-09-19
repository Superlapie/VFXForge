class_name VFXRenameDialog
extends AcceptDialog

signal rename_confirmed(new_name: String)

var name_field: LineEdit


func _init() -> void:
	title = "Rename Layer"
	ok_button_text = "Rename"
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 12)
	margin.add_theme_constant_override("margin_right", 12)
	margin.add_theme_constant_override("margin_top", 8)
	margin.add_theme_constant_override("margin_bottom", 8)
	add_child(margin)
	name_field = LineEdit.new()
	name_field.placeholder_text = "Layer name"
	name_field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	margin.add_child(name_field)
	confirmed.connect(_on_confirmed)
	name_field.text_submitted.connect(func(_text: String) -> void: _on_confirmed())


func open_rename(current_name: String) -> void:
	name_field.text = current_name
	popup_centered(Vector2(360, 120))
	name_field.grab_focus()
	name_field.select_all()


func _on_confirmed() -> void:
	var trimmed := name_field.text.strip_edges()
	if trimmed.is_empty():
		return
	rename_confirmed.emit(trimmed)
