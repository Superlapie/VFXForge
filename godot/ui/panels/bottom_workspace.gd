class_name VFXBottomWorkspace
extends PanelContainer

signal scrubbed(time: float)
signal layer_timing_changed(layer_id: String, start: float, duration: float)
signal play_requested()
signal pause_requested()
signal stop_requested()
signal speed_changed(speed: float)
signal workspace_changed(index: int)
signal curve_edit_requested(path: String, value: Variant)
signal curve_layer_selected(layer_id: String)
signal events_changed(events: Array)
signal event_scrub_requested(time: float)
signal diagnostics_navigate(layer_id: String, path: String)

const Tokens := preload("res://godot/ui/theme/tokens.gd")
const TimelineScript := preload("res://godot/editor/timeline_view.gd")
const CurvesWorkspaceScript := preload("res://godot/ui/panels/curves_workspace.gd")
const GradientWorkspaceScript := preload("res://godot/ui/panels/gradient_workspace.gd")
const EventsWorkspaceScript := preload("res://godot/ui/panels/events_workspace.gd")
const DiagnosticsWorkspaceScript := preload("res://godot/ui/panels/diagnostics_workspace.gd")

var timeline: VFXTimelineView
var curves_workspace: VFXCurvesWorkspace
var gradients_workspace: VFXGradientWorkspace
var events_workspace: VFXEventsWorkspace
var diagnostics_workspace: VFXDiagnosticsWorkspace
var playback_time_label: Label
var playback_slider: HSlider
var speed_menu: OptionButton
var workspace_tabs: TabBar

var _stack: Control
var _timeline_host: Control


func _init() -> void:
	custom_minimum_size.y = 210
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", 0)
	add_child(outer)

	_build_transport_bar(outer)
	_stack = Control.new()
	_stack.size_flags_vertical = Control.SIZE_EXPAND_FILL
	outer.add_child(_stack)

	_timeline_host = Control.new()
	_timeline_host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_stack.add_child(_timeline_host)

	timeline = TimelineScript.new()
	timeline.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	timeline.scrubbed.connect(scrubbed.emit)
	timeline.layer_timing_changed.connect(layer_timing_changed.emit)
	_timeline_host.add_child(timeline)

	curves_workspace = CurvesWorkspaceScript.new()
	curves_workspace.visible = false
	curves_workspace.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	curves_workspace.edit_requested.connect(curve_edit_requested.emit)
	curves_workspace.open_layer_requested.connect(curve_layer_selected.emit)
	_stack.add_child(curves_workspace)

	gradients_workspace = GradientWorkspaceScript.new()
	gradients_workspace.visible = false
	gradients_workspace.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	gradients_workspace.edit_requested.connect(curve_edit_requested.emit)
	gradients_workspace.open_layer_requested.connect(curve_layer_selected.emit)
	_stack.add_child(gradients_workspace)

	events_workspace = EventsWorkspaceScript.new()
	events_workspace.visible = false
	events_workspace.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	events_workspace.events_changed.connect(events_changed.emit)
	events_workspace.event_selected.connect(event_scrub_requested.emit)
	_stack.add_child(events_workspace)

	diagnostics_workspace = DiagnosticsWorkspaceScript.new()
	diagnostics_workspace.visible = false
	diagnostics_workspace.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	diagnostics_workspace.navigate_requested.connect(diagnostics_navigate.emit)
	_stack.add_child(diagnostics_workspace)

	workspace_tabs = TabBar.new()
	workspace_tabs.add_tab("Timeline")
	workspace_tabs.add_tab("Curves")
	workspace_tabs.add_tab("Gradients")
	workspace_tabs.add_tab("Events")
	workspace_tabs.add_tab("Diagnostics")
	workspace_tabs.tab_changed.connect(_on_tab_changed)
	outer.add_child(workspace_tabs)


func _build_transport_bar(parent: VBoxContainer) -> void:
	var bar := HBoxContainer.new()
	bar.custom_minimum_size.y = 32
	bar.add_theme_constant_override("separation", Tokens.SPACE_SM)
	bar.add_theme_constant_override("margin_left", Tokens.SPACE_MD)
	bar.add_theme_constant_override("margin_right", Tokens.SPACE_MD)
	parent.add_child(bar)

	for spec in [["▶", "Play", play_requested], ["⏸", "Pause", pause_requested], ["⏹", "Stop", stop_requested]]:
		var button := Button.new()
		button.text = spec[0]
		button.tooltip_text = spec[1]
		button.flat = true
		button.pressed.connect(spec[2].emit)
		bar.add_child(button)

	speed_menu = OptionButton.new()
	speed_menu.name = "SpeedMenu"
	for label in ["0.25x", "0.5x", "1.0x", "2.0x"]:
		speed_menu.add_item(label)
	speed_menu.selected = 2
	speed_menu.item_selected.connect(func(index: int) -> void:
		speed_changed.emit([0.25, 0.5, 1.0, 2.0][index])
	)
	bar.add_child(speed_menu)

	playback_time_label = Label.new()
	playback_time_label.name = "PlaybackTimeLabel"
	playback_time_label.text = "00:00.000 / 00:01.000"
	playback_time_label.add_theme_color_override("font_color", Tokens.BRAND_AMBER)
	playback_time_label.add_theme_font_size_override("font_size", Tokens.FONT_MONO)
	playback_time_label.custom_minimum_size.x = 180
	bar.add_child(playback_time_label)

	playback_slider = HSlider.new()
	playback_slider.name = "PlaybackSlider"
	playback_slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	playback_slider.min_value = 0.0
	playback_slider.max_value = 1.0
	playback_slider.step = 0.001
	playback_slider.value_changed.connect(scrubbed.emit)
	bar.add_child(playback_slider)


func set_document(document: Dictionary, selected_layer_id: String) -> void:
	timeline.set_document(document)
	curves_workspace.set_document(document, selected_layer_id)
	gradients_workspace.set_document(document, selected_layer_id)
	events_workspace.set_document(document)
	playback_slider.max_value = max(0.1, float(document.get("duration", 1.0)))


func set_diagnostics(entries: Array) -> void:
	diagnostics_workspace.set_entries(entries)
	var count: int = diagnostics_workspace.issue_count()
	workspace_tabs.set_tab_title(4, "Diagnostics" if count == 0 else "Diagnostics (%d)" % count)


func set_workspace_tab(index: int) -> void:
	if index >= 0 and index < workspace_tabs.get_tab_count():
		workspace_tabs.current_tab = index
		_on_tab_changed(index)


func focus_curve_workspace(layer_id: String, curve_key: String = "scale") -> void:
	set_workspace_tab(1)
	curves_workspace.focus_curve(layer_id, curve_key)


func focus_gradient_workspace(layer_id: String) -> void:
	set_workspace_tab(2)
	gradients_workspace.focus_gradient(layer_id)


func set_time(time: float, duration: float) -> void:
	timeline.set_time(time)
	playback_slider.set_value_no_signal(time)
	playback_time_label.text = _format_time(time) + " / " + _format_time(duration)


func _format_time(seconds: float) -> String:
	var whole := int(seconds)
	var fraction := int(round((seconds - whole) * 1000.0))
	return "%02d:%02d.%03d" % [whole / 60, whole % 60, fraction]


func _on_tab_changed(index: int) -> void:
	_timeline_host.visible = index == 0
	curves_workspace.visible = index == 1
	gradients_workspace.visible = index == 2
	events_workspace.visible = index == 3
	diagnostics_workspace.visible = index == 4
	workspace_changed.emit(index)
