class_name VFXSectionHeader
extends Button

signal open_changed(is_open: bool)

const Tokens := preload("res://godot/ui/theme/tokens.gd")

var section_open: bool = true
var _title: String = ""


func _init(title: String, starts_open: bool = true) -> void:
	_title = title
	section_open = starts_open
	text = _header_text()
	alignment = HORIZONTAL_ALIGNMENT_LEFT
	focus_mode = Control.FOCUS_NONE
	flat = true
	custom_minimum_size.y = 28
	add_theme_font_size_override("font_size", Tokens.FONT_HEADING)
	add_theme_color_override("font_color", Tokens.TEXT_HEADING)
	add_theme_color_override("font_hover_color", Tokens.TEXT_PRIMARY)
	pressed.connect(_on_pressed)


func _header_text() -> String:
	return ("⌃ " if section_open else "⌄ ") + _title.to_upper()


func _on_pressed() -> void:
	section_open = not section_open
	text = _header_text()
	open_changed.emit(section_open)


func set_section_open(value: bool) -> void:
	section_open = value
	text = _header_text()
