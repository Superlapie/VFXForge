class_name VFXStatusBar
extends PanelContainer

const Tokens := preload("res://godot/ui/theme/tokens.gd")

var status_label: Label
var gpu_label: Label


func _init() -> void:
	custom_minimum_size.y = 24
	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", Tokens.SPACE_MD)
	bar.add_theme_constant_override("margin_left", Tokens.SPACE_MD)
	bar.add_theme_constant_override("margin_right", Tokens.SPACE_MD)
	bar.add_theme_constant_override("margin_top", 2)
	bar.add_theme_constant_override("margin_bottom", 2)
	add_child(bar)

	status_label = Label.new()
	status_label.text = "Ready"
	status_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	status_label.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	status_label.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	bar.add_child(status_label)

	gpu_label = Label.new()
	gpu_label.text = "GPU: GOOD"
	gpu_label.add_theme_color_override("font_color", Tokens.SUCCESS)
	gpu_label.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	bar.add_child(gpu_label)
