class_name VFXNumberField
extends HBoxContainer

signal value_committed(value: float)

const Tokens := preload("res://godot/ui/theme/tokens.gd")

var spin: SpinBox
var slider: HSlider
var _label: Label
var _dragging := false
var _drag_start_x := 0.0
var _drag_start_value := 0.0


func _init(
	label_text: String,
	value: float,
	minimum: float,
	maximum: float,
	step: float,
	use_slider: bool = false,
	tooltip: String = "",
) -> void:
	add_theme_constant_override("separation", Tokens.SPACE_SM)
	_label = Label.new()
	_label.text = label_text
	_label.custom_minimum_size.x = 118
	_label.mouse_filter = Control.MOUSE_FILTER_STOP
	_label.gui_input.connect(_on_label_gui_input)
	if not tooltip.is_empty():
		_label.tooltip_text = tooltip
	add_child(_label)

	if use_slider and maximum > minimum:
		slider = HSlider.new()
		slider.min_value = minimum
		slider.max_value = maximum
		slider.step = step
		slider.value = value
		slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		slider.custom_minimum_size.x = 90
		add_child(slider)

	spin = SpinBox.new()
	spin.min_value = minimum
	spin.max_value = maximum
	spin.step = step
	spin.value = value
	spin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spin.custom_minimum_size.x = 72
	spin.value_changed.connect(func(next_value: float) -> void:
		if slider != null:
			slider.set_value_no_signal(next_value)
		value_committed.emit(next_value)
	)
	add_child(spin)

	if slider != null:
		slider.value_changed.connect(func(next_value: float) -> void:
			spin.set_value_no_signal(next_value)
			value_committed.emit(next_value)
		)

	if not tooltip.is_empty():
		spin.tooltip_text = tooltip


func _on_label_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			_dragging = true
			_drag_start_x = event.position.x
			_drag_start_value = spin.value
		else:
			_dragging = false
	elif event is InputEventMouseMotion and _dragging:
		var scale := spin.step
		if Input.is_key_pressed(KEY_SHIFT):
			scale *= 0.1
		elif Input.is_key_pressed(KEY_CTRL):
			scale *= 10.0
		var delta: float = (event.position.x - _drag_start_x) * scale
		spin.value = clamp(_drag_start_value + delta, spin.min_value, spin.max_value)
