class_name VFXViewportPanel
extends PanelContainer

signal camera_selected(index: int)
signal stage_preset_selected(index: int)
signal backdrop_selected(index: int)
signal reset_view_requested()
signal grid_toggled(visible: bool)
signal bounds_toggled(visible: bool)
signal frame_effect_requested()

const Tokens := preload("res://godot/ui/theme/tokens.gd")
const PreviewViewScript := preload("res://godot/editor/preview_view.gd")
const PreviewStageScript := preload("res://godot/editor/preview_stage.gd")
const IconButton := preload("res://godot/ui/components/icon_button.gd")

var preview_view: VFXPreviewView
var viewport_container: SubViewportContainer
var metrics_label: Label
var status_label: Label
var perf_label: Label
var camera_menu: OptionButton
var stage_menu: OptionButton
var backdrop_menu: OptionButton
var grid_button: Button
var bounds_button: Button

var _grid_visible := true
var _bounds_visible := false


func _init() -> void:
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var outer := MarginContainer.new()
	outer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	outer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(outer)

	var stack := Control.new()
	stack.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	stack.size_flags_vertical = Control.SIZE_EXPAND_FILL
	outer.add_child(stack)

	preview_view = PreviewViewScript.new()
	viewport_container = preview_view
	viewport_container.stretch = true
	viewport_container.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	stack.add_child(viewport_container)

	_build_viewport_toolbar(stack)
	_build_viewport_footer(stack)


func attach_viewport(viewport: SubViewport) -> void:
	viewport_container.add_child(viewport)


func set_performance_text(text: String) -> void:
	if is_instance_valid(perf_label):
		perf_label.text = text


func _build_viewport_toolbar(parent: Control) -> void:
	var top_left := HBoxContainer.new()
	top_left.name = "ViewportToolbarLeft"
	top_left.add_theme_constant_override("separation", Tokens.SPACE_XS)
	top_left.set_anchors_preset(Control.PRESET_TOP_LEFT)
	top_left.offset_left = Tokens.SPACE_SM
	top_left.offset_top = Tokens.SPACE_SM
	parent.add_child(top_left)

	var perspective := OptionButton.new()
	perspective.add_item("Perspective")
	perspective.selected = 0
	perspective.disabled = true
	top_left.add_child(perspective)

	camera_menu = OptionButton.new()
	camera_menu.name = "CameraMenu"
	for camera_name in ["MMO", "Front", "Side", "Top"]:
		camera_menu.add_item(camera_name)
	camera_menu.selected = 0
	camera_menu.item_selected.connect(camera_selected.emit)
	top_left.add_child(camera_menu)

	var reset_button := IconButton.new("↺", "Reset camera to MMO view")
	reset_button.pressed.connect(reset_view_requested.emit)
	top_left.add_child(reset_button)

	var frame_button := IconButton.new("Frame", "Frame effect bounds")
	frame_button.pressed.connect(frame_effect_requested.emit)
	top_left.add_child(frame_button)

	var top_right := HBoxContainer.new()
	top_right.name = "ViewportToolbarRight"
	top_right.add_theme_constant_override("separation", Tokens.SPACE_XS)
	top_right.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	top_right.offset_right = -Tokens.SPACE_SM
	top_right.offset_top = Tokens.SPACE_SM
	parent.add_child(top_right)

	stage_menu = OptionButton.new()
	stage_menu.name = "StageMenu"
	for label in PreviewStageScript.PRESET_LABELS:
		stage_menu.add_item(label)
	stage_menu.select(PreviewStageScript.PRESET_IDS.find("mmo_combat"))
	stage_menu.item_selected.connect(stage_preset_selected.emit)
	top_right.add_child(stage_menu)

	backdrop_menu = OptionButton.new()
	backdrop_menu.name = "BackdropMenu"
	for stage in ["Dark", "Light", "Night", "Checker"]:
		backdrop_menu.add_item(stage)
	backdrop_menu.item_selected.connect(backdrop_selected.emit)
	top_right.add_child(backdrop_menu)

	grid_button = IconButton.new("Grid", "Toggle stage grid")
	grid_button.toggle_mode = true
	grid_button.button_pressed = true
	grid_button.pressed.connect(func() -> void:
		_grid_visible = grid_button.button_pressed
		grid_toggled.emit(_grid_visible)
	)
	top_right.add_child(grid_button)

	bounds_button = IconButton.new("Bounds", "Toggle effect bounds overlay")
	bounds_button.toggle_mode = true
	bounds_button.pressed.connect(func() -> void:
		_bounds_visible = bounds_button.button_pressed
		bounds_toggled.emit(_bounds_visible)
	)
	top_right.add_child(bounds_button)


func _build_viewport_footer(parent: Control) -> void:
	var footer := HBoxContainer.new()
	footer.name = "ViewportFooter"
	footer.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	footer.offset_bottom = -Tokens.SPACE_XS
	footer.offset_left = Tokens.SPACE_SM
	footer.offset_right = -Tokens.SPACE_SM
	footer.add_theme_constant_override("separation", Tokens.SPACE_MD)
	parent.add_child(footer)

	metrics_label = Label.new()
	metrics_label.name = "MetricsLabel"
	metrics_label.text = "No document loaded"
	metrics_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	metrics_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	metrics_label.add_theme_color_override("font_color", Tokens.TEXT_SECONDARY)
	metrics_label.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	footer.add_child(metrics_label)

	perf_label = Label.new()
	perf_label.name = "PerfLabel"
	perf_label.text = "GPU: GOOD"
	perf_label.add_theme_color_override("font_color", Tokens.SUCCESS)
	perf_label.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	footer.add_child(perf_label)

	status_label = Label.new()
	status_label.name = "StatusLabel"
	status_label.text = "Ready"
	status_label.custom_minimum_size.x = 170
	status_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	status_label.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	status_label.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	footer.add_child(status_label)
