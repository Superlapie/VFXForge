class_name VFXInspectorPanel
extends PanelContainer

signal edit_requested(path: String, value: Variant)
signal curve_edit_requested(layer_id: String, curve_key: String)
signal gradient_edit_requested(layer_id: String)

const Tokens := preload("res://godot/ui/theme/tokens.gd")
const Schema := preload("res://godot/ui/schema/inspector_schema.gd")
const LayerIcons := preload("res://godot/ui/icons/layer_icons.gd")
const CollapsibleSectionScript := preload("res://godot/ui/components/collapsible_section.gd")
const NumberFieldScript := preload("res://godot/ui/components/number_field.gd")
const VectorFieldScript := preload("res://godot/ui/components/vector_field.gd")
const CurveEditorScript := preload("res://godot/editor/curve_editor.gd")
const GradientEditorScript := preload("res://godot/editor/gradient_editor.gd")

var inspector: VBoxContainer
var inspector_scroll: ScrollContainer
var inspector_title: Label
var performance_label: Label

var _model: VFXDocument
var _selected_layer_id: String = ""
var _show_advanced := false
var _advanced_toggle: Button


func _init() -> void:
	custom_minimum_size.x = 330
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inspector_scroll = ScrollContainer.new()
	inspector_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	inspector_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inspector_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(inspector_scroll)
	inspector = VBoxContainer.new()
	inspector.name = "InspectorContent"
	inspector.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inspector.add_theme_constant_override("separation", Tokens.SPACE_SM)
	inspector_scroll.add_child(inspector)
	inspector_title = Label.new()
	inspector_title.name = "InspectorTitle"
	inspector_title.add_theme_font_size_override("font_size", Tokens.FONT_HEADING)
	inspector_title.add_theme_color_override("font_color", Tokens.TEXT_HEADING)
	inspector.add_child(inspector_title)


func bind_model(model: VFXDocument) -> void:
	_model = model


func refresh(selected_layer_id: String, metrics_summary: String) -> void:
	_selected_layer_id = selected_layer_id
	performance_label = null
	for child in inspector.get_children():
		if child != inspector_title:
			child.queue_free()
	if _model == null:
		inspector_title.text = "INSPECTOR"
		return
	var selected: Dictionary = _model.get_layer(selected_layer_id) if not selected_layer_id.is_empty() else {}
	if selected.is_empty():
		_build_document_inspector(metrics_summary)
	else:
		_build_layer_inspector(selected)


func _build_document_inspector(metrics_summary: String) -> void:
	inspector_title.text = "EFFECT SETTINGS"
	_add_help("Canonical document saved as JSON. Seed drives deterministic preview.")
	var section: VFXCollapsibleSection = CollapsibleSectionScript.new("General", true)
	inspector.add_child(section)
	for field in Schema.document_fields():
		_add_schema_field(section, field, _model.data, "")
	_add_metric_card(metrics_summary)


func _build_layer_inspector(layer: Dictionary) -> void:
	var layer_type := str(layer.get("type", ""))
	var layer_name := str(layer.get("name", layer.get("id", "Layer")))
	inspector_title.text = LayerIcons.glyph(layer_type) + "  " + layer_name.to_upper()
	var subtitle := Label.new()
	subtitle.text = LayerIcons.type_label(layer_type)
	subtitle.add_theme_color_override("font_color", Tokens.TEXT_SECONDARY)
	subtitle.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	inspector.add_child(subtitle)

	var general: VFXCollapsibleSection = CollapsibleSectionScript.new("General", true)
	inspector.add_child(general)
	for field in Schema.layer_common_fields():
		_add_schema_field(general, field, layer, str(layer.get("id", "")))

	var properties: VFXCollapsibleSection = CollapsibleSectionScript.new("Properties", true)
	inspector.add_child(properties)
	for field in Schema.layer_property_fields(layer_type):
		_add_schema_field(properties, field, layer, str(layer.get("id", "")))
	if layer_type in Schema.mesh_asset_types():
		_add_text_field(properties, "Mesh asset", "mesh_asset", str(layer.get("properties", {}).get("mesh_asset", "")), str(layer.get("id", "")), true)

	var appearance: VFXCollapsibleSection = CollapsibleSectionScript.new("Appearance", true)
	inspector.add_child(appearance)
	for field in Schema.material_fields():
		_add_schema_field(appearance, field, layer, str(layer.get("id", "")))

	var curves: VFXCollapsibleSection = CollapsibleSectionScript.new("Curves", true)
	inspector.add_child(curves)
	var layer_id := str(layer.get("id", ""))
	var layer_curves: Dictionary = layer.get("curves", {})
	var curve_keys: Array = layer_curves.keys()
	curve_keys.sort()
	if curve_keys.is_empty():
		curve_keys = ["scale"]
	for curve_key_variant in curve_keys:
		var curve_key: String = str(curve_key_variant)
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", Tokens.SPACE_SM)
		var label := Label.new()
		label.text = curve_key.capitalize()
		label.custom_minimum_size.x = 72
		label.add_theme_color_override("font_color", Tokens.TEXT_SECONDARY)
		row.add_child(label)
		var curve_editor: VFXCurveEditor = CurveEditorScript.new()
		curve_editor.custom_minimum_size.y = 56
		curve_editor.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		curve_editor.set_curve(layer_curves.get(curve_key, {}))
		curve_editor.curve_changed.connect(func(value: Dictionary) -> void: edit_requested.emit("layers." + layer_id + ".curves." + curve_key, value))
		curve_editor.gui_input.connect(func(event: InputEvent) -> void:
			if event is InputEventMouseButton and event.pressed and event.double_click and event.button_index == MOUSE_BUTTON_LEFT:
				curve_edit_requested.emit(layer_id, curve_key)
		)
		row.add_child(curve_editor)
		curves.add_row(row)
	var curve_hint := Label.new()
	curve_hint.text = "Double-click a curve preview to open the Curves workspace"
	curve_hint.mouse_filter = Control.MOUSE_FILTER_STOP
	curve_hint.gui_input.connect(func(event: InputEvent) -> void:
		if event is InputEventMouseButton and event.pressed and event.double_click and event.button_index == MOUSE_BUTTON_LEFT:
			curve_edit_requested.emit(layer_id, "scale")
	)
	curve_hint.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	curve_hint.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	curves.add_row(curve_hint)

	var gradient_section: VFXCollapsibleSection = CollapsibleSectionScript.new("Color Over Life", true)
	inspector.add_child(gradient_section)
	var gradient_editor: VFXGradientEditor = GradientEditorScript.new()
	gradient_editor.custom_minimum_size.y = 48
	gradient_editor.set_gradient(layer.get("gradient", []))
	gradient_editor.gradient_changed.connect(func(value: Array) -> void: edit_requested.emit("layers." + layer_id + ".gradient", value))
	gradient_editor.gui_input.connect(func(event: InputEvent) -> void:
		if event is InputEventMouseButton and event.pressed and event.double_click and event.button_index == MOUSE_BUTTON_LEFT:
			gradient_edit_requested.emit(layer_id)
	)
	gradient_section.add_row(gradient_editor)
	var gradient_hint := Label.new()
	gradient_hint.text = "Double-click preview to open Gradients workspace"
	gradient_hint.mouse_filter = Control.MOUSE_FILTER_STOP
	gradient_hint.gui_input.connect(func(event: InputEvent) -> void:
		if event is InputEventMouseButton and event.pressed and event.double_click and event.button_index == MOUSE_BUTTON_LEFT:
			gradient_edit_requested.emit(layer_id)
	)
	gradient_hint.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	gradient_hint.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	gradient_section.add_row(gradient_hint)

	_advanced_toggle = Button.new()
	_advanced_toggle.text = ("Advanced  ⌄" if not _show_advanced else "Advanced  ⌃")
	_advanced_toggle.alignment = HORIZONTAL_ALIGNMENT_LEFT
	_advanced_toggle.flat = true
	_advanced_toggle.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	_advanced_toggle.pressed.connect(func() -> void:
		_show_advanced = not _show_advanced
		refresh(_selected_layer_id, "")
	)
	inspector.add_child(_advanced_toggle)
	if _show_advanced:
		var advanced: VFXCollapsibleSection = CollapsibleSectionScript.new("Raw Data", true)
		inspector.add_child(advanced)
		_add_json_field(advanced, "Curve JSON", "layers." + layer_id + ".curves.scale", JSON.stringify(layer.get("curves", {}).get("scale", {})))
		_add_json_field(advanced, "Gradient JSON", "layers." + layer_id + ".gradient", JSON.stringify(layer.get("gradient", [])))


func _add_schema_field(section: VFXCollapsibleSection, field: Dictionary, source: Dictionary, layer_id: String) -> void:
	match str(field.get("kind", "")):
		"text":
			var value: Variant = _resolve_value(field, source, layer_id)
			_add_text_field(section, str(field.get("label", "")), str(field.get("path", "")), str(value), layer_id, bool(field.get("layer", false)), bool(field.get("properties", false)))
		"number":
			var number_value := float(_resolve_value(field, source, layer_id))
			_add_number_field(
				section,
				str(field.get("label", "")),
				str(field.get("path", "")),
				number_value,
				float(field.get("min", 0.0)),
				float(field.get("max", 100.0)),
				float(field.get("step", 0.01)),
				layer_id,
				bool(field.get("layer", false)),
				bool(field.get("material", false)),
				bool(field.get("properties", false)),
				bool(field.get("slider", false)),
				str(field.get("tooltip", "")),
			)
		"option":
			_add_option_field(section, str(field.get("label", "")), str(field.get("path", "")), field.get("options", []), str(_resolve_value(field, source, layer_id)), layer_id, bool(field.get("material", false)), bool(field.get("properties", false)))
		"vector":
			_add_vector_field(section, str(field.get("label", "")), str(field.get("path", "")), _resolve_value(field, source, layer_id), layer_id)
		"color":
			_add_color_field(section, str(field.get("label", "")), str(field.get("path", "")), Color.from_string(str(_resolve_value(field, source, layer_id)), Color.WHITE), layer_id)
		"bool":
			_add_bool_field(section, str(field.get("label", "")), str(field.get("path", "")), bool(_resolve_value(field, source, layer_id)), layer_id)


func _resolve_value(field: Dictionary, source: Dictionary, layer_id: String) -> Variant:
	var path := str(field.get("path", ""))
	if bool(field.get("layer", false)):
		if bool(field.get("properties", false)):
			return source.get("properties", {}).get(path, field.get("default", ""))
		if bool(field.get("material", false)):
			return source.get("material", {}).get(path, field.get("default", ""))
		return source.get(path, field.get("default", ""))
	return _model.data.get(path, field.get("default", ""))


func _full_path(path: String, layer_id: String, properties: bool, material: bool) -> String:
	if layer_id.is_empty():
		return path
	if properties:
		return "layers." + layer_id + ".properties." + path
	if material:
		return "layers." + layer_id + ".material." + path
	return "layers." + layer_id + "." + path


func _add_help(text: String) -> void:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	label.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	inspector.add_child(label)


func _add_metric_card(metrics_summary: String) -> void:
	var card := PanelContainer.new()
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var label := Label.new()
	performance_label = label
	label.text = "PERFORMANCE\n" + metrics_summary.replace("  •  ", "\n")
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.custom_minimum_size.y = 64
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_color_override("font_color", Tokens.TEXT_SECONDARY)
	card.add_child(label)
	inspector.add_child(card)


func _add_text_field(section: VFXCollapsibleSection, label_text: String, path: String, value: String, layer_id: String, is_layer: bool = false, properties: bool = false) -> void:
	var row := HBoxContainer.new()
	var label := Label.new()
	label.text = label_text
	label.custom_minimum_size.x = 118
	row.add_child(label)
	var field := LineEdit.new()
	field.text = value
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var full_path := _full_path(path, layer_id, properties, false) if is_layer else path
	field.text_submitted.connect(func(text: String) -> void: edit_requested.emit(full_path, text))
	field.focus_exited.connect(func() -> void: edit_requested.emit(full_path, field.text))
	row.add_child(field)
	section.add_row(row)


func _add_number_field(
	section: VFXCollapsibleSection,
	label_text: String,
	path: String,
	value: float,
	minimum: float,
	maximum: float,
	step: float,
	layer_id: String,
	is_layer: bool,
	material: bool,
	properties: bool,
	use_slider: bool,
	tooltip: String,
) -> void:
	var full_path := _full_path(path, layer_id, properties, material) if is_layer else path
	var field: VFXNumberField = NumberFieldScript.new(label_text, value, minimum, maximum, step, use_slider, tooltip)
	field.spin.value_changed.connect(func(next_value: float) -> void: edit_requested.emit(full_path, next_value))
	section.add_row(field)


func _add_option_field(section: VFXCollapsibleSection, label_text: String, path: String, options: Array, value: String, layer_id: String, material: bool, properties: bool) -> void:
	var row := HBoxContainer.new()
	var label := Label.new()
	label.text = label_text
	label.custom_minimum_size.x = 118
	row.add_child(label)
	var option := OptionButton.new()
	var typed_options: Array[String] = []
	for item in options:
		typed_options.append(str(item))
	for item in typed_options:
		option.add_item(item)
	option.select(maxi(0, typed_options.find(value)))
	option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var full_path := _full_path(path, layer_id, properties, material)
	option.item_selected.connect(func(index: int) -> void: edit_requested.emit(full_path, typed_options[index]))
	row.add_child(option)
	section.add_row(row)


func _add_vector_field(section: VFXCollapsibleSection, label_text: String, path: String, value: Variant, layer_id: String) -> void:
	var field: VFXVectorField = VectorFieldScript.new(label_text, value if value is Array else [0.0, 0.0, 0.0])
	var full_path := _full_path(path, layer_id, true, false)
	field.value_committed.connect(func(parsed: Array) -> void: edit_requested.emit(full_path, parsed))
	section.add_row(field)


func _add_color_field(section: VFXCollapsibleSection, label_text: String, path: String, value: Color, layer_id: String) -> void:
	var row := HBoxContainer.new()
	var label := Label.new()
	label.text = label_text
	label.custom_minimum_size.x = 118
	row.add_child(label)
	var picker := ColorPickerButton.new()
	picker.color = value
	picker.custom_minimum_size.x = 80
	var full_path := _full_path(path, layer_id, true, false)
	picker.color_changed.connect(func(next_color: Color) -> void: edit_requested.emit(full_path, next_color.to_html(true)))
	row.add_child(picker)
	section.add_row(row)


func _add_bool_field(section: VFXCollapsibleSection, label_text: String, path: String, value: bool, layer_id: String) -> void:
	var toggle := CheckButton.new()
	toggle.text = label_text
	toggle.button_pressed = value
	var full_path := _full_path(path, layer_id, false, false) if not layer_id.is_empty() else path
	toggle.toggled.connect(func(next_value: bool) -> void: edit_requested.emit(full_path, next_value))
	section.add_row(toggle)


func _add_json_field(section: VFXCollapsibleSection, label_text: String, path: String, value: String) -> void:
	var label := Label.new()
	label.text = label_text
	label.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	section.add_row(label)
	var field := TextEdit.new()
	field.text = value
	field.custom_minimum_size.y = 72
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	field.text_changed.connect(func() -> void:
		var parsed: Variant = JSON.parse_string(field.text)
		if parsed != null:
			edit_requested.emit(path, parsed)
	)
	section.add_row(field)
