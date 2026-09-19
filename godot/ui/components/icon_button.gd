class_name VFXIconButton
extends Button

const Tokens := preload("res://godot/ui/theme/tokens.gd")


func _init(label: String, tooltip: String = "") -> void:
	text = label
	focus_mode = Control.FOCUS_ALL
	custom_minimum_size = Vector2(28, 28)
	flat = true
	if not tooltip.is_empty():
		tooltip_text = tooltip
	add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
