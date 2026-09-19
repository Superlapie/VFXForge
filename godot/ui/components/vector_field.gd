class_name VFXVectorField
extends VBoxContainer

signal value_committed(value: Array)

const Tokens := preload("res://godot/ui/theme/tokens.gd")

var _components: Array[SpinBox] = []
var _axis_colors := [Color("#D96B6B"), Color("#6BC48A"), Color("#5EB8D4")]


func _init(label_text: String, value: Variant, tooltip: String = "") -> void:
	add_theme_constant_override("separation", Tokens.SPACE_XS)
	var header := Label.new()
	header.text = label_text
	header.add_theme_color_override("font_color", Tokens.TEXT_SECONDARY)
	if not tooltip.is_empty():
		header.tooltip_text = tooltip
	add_child(header)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", Tokens.SPACE_SM)
	add_child(row)

	var values: Array = value if value is Array else [0.0, 0.0, 0.0]
	var axes := ["X", "Y", "Z"]
	var count := mini(values.size(), 3)
	for index in range(count):
		var axis_row := HBoxContainer.new()
		axis_row.add_theme_constant_override("separation", 4)
		var axis_label := Label.new()
		axis_label.text = axes[index]
		axis_label.custom_minimum_size.x = 14
		axis_label.add_theme_color_override("font_color", _axis_colors[index])
		axis_row.add_child(axis_label)
		var spin := SpinBox.new()
		spin.min_value = -100000.0
		spin.max_value = 100000.0
		spin.step = 0.01
		spin.value = float(values[index])
		spin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		spin.value_changed.connect(_emit_value)
		_components.append(spin)
		axis_row.add_child(spin)
		row.add_child(axis_row)


func _emit_value(_value: float = 0.0) -> void:
	var result: Array = []
	for spin in _components:
		result.append(spin.value)
	value_committed.emit(result)
