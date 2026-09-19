class_name VFXTimelineView
extends Control

signal scrubbed(time: float)
signal layer_timing_changed(layer_id: String, start: float, duration: float)
signal layer_selected(layer_id: String)

const Tokens := preload("res://godot/ui/theme/tokens.gd")
const LayerIcons := preload("res://godot/ui/icons/layer_icons.gd")

var document: Dictionary = {}
var current_time: float = 0.0
var selected_layer_id: String = ""
var zoom: float = 1.0
var scroll_time: float = 0.0
var row_height: float = 26.0
var label_width: float = 140.0
var ruler_height: float = 24.0
var event_strip_height: float = 18.0

var drag_layer_id: String = ""
var drag_mode: int = 0
var drag_anchor_time: float = 0.0
var drag_initial_start: float = 0.0
var drag_initial_duration: float = 1.0
var drag_current_start: float = 0.0
var drag_current_duration: float = 1.0
var _panning := false
var _pan_anchor_x := 0.0
var _pan_anchor_scroll := 0.0
var _hover_layer_id := ""
var _hover_resize_end := false


func _init() -> void:
	custom_minimum_size = Vector2(300, 160)
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND


func set_document(value: Dictionary) -> void:
	document = value
	queue_redraw()


func set_time(value: float) -> void:
	current_time = value
	queue_redraw()


func set_selected_layer(layer_id: String) -> void:
	selected_layer_id = layer_id
	queue_redraw()


func frame_layer(layer_id: String) -> void:
	var layer := _find_layer(layer_id)
	if layer.is_empty():
		return
	var start: float = float(layer.get("start", 0.0))
	var end: float = start + float(layer.get("duration", float(document.get("duration", 1.0))))
	frame_range(start, end)


func frame_all() -> void:
	frame_range(0.0, float(document.get("duration", 1.0)))


func frame_range(start: float, end: float) -> void:
	var duration: float = max(0.1, float(document.get("duration", 1.0)))
	var span: float = max(0.05, end - start)
	var margin: float = span * 0.15
	var view_start: float = max(0.0, start - margin)
	var view_end: float = min(duration, end + margin)
	var visible_span: float = max(0.05, view_end - view_start)
	var timeline_width: float = max(1.0, size.x - label_width)
	zoom = clamp(duration / visible_span, 0.5, 12.0)
	scroll_time = view_start
	queue_redraw()


func _track_start_y() -> float:
	return ruler_height + event_strip_height


func _find_layer(layer_id: String) -> Dictionary:
	for layer_variant in document.get("layers", []):
		if layer_variant is Dictionary and str(layer_variant.get("id", "")) == layer_id:
			return layer_variant
	return {}


func _layer_color(layer_type: String, enabled: bool) -> Color:
	var base: Color = Tokens.LAYER_COLORS.get(layer_type, Tokens.ACCENT_BLUE)
	if enabled:
		return base
	return Color(base.r, base.g, base.b, 0.35)


func _pixels_per_second(duration: float) -> float:
	var timeline_width: float = max(1.0, size.x - label_width)
	return timeline_width / max(0.1, duration) * zoom


func _time_to_x(time: float, duration: float) -> float:
	return label_width + time * _pixels_per_second(duration) - scroll_time * _pixels_per_second(duration)


func _x_to_time(x: float, duration: float) -> float:
	return (x - label_width) / _pixels_per_second(duration) + scroll_time


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Tokens.TIMELINE_BG, true)
	var duration: float = max(0.1, float(document.get("duration", 1.0)))
	var pps: float = _pixels_per_second(duration)
	var track_y: float = _track_start_y()
	var snap: float = max(0.001, float(document.get("timeline", {}).get("snap", 0.05)))

	_draw_ruler(duration, pps, snap)
	_draw_event_strip(duration, pps, track_y)
	_draw_tracks(duration, pps, track_y)
	_draw_playhead(duration, pps)


func _draw_ruler(duration: float, pps: float, snap: float) -> void:
	draw_rect(Rect2(0, 0, size.x, ruler_height), Tokens.PANEL_BG, true)
	draw_line(Vector2(0, ruler_height - 1), Vector2(size.x, ruler_height - 1), Tokens.TIMELINE_RULER, 1.0)
	draw_line(Vector2(label_width, 0), Vector2(label_width, ruler_height), Tokens.SEPARATOR, 1.0)

	var major_step: float = 1.0
	if zoom > 4.0:
		major_step = 0.5
	elif zoom > 8.0:
		major_step = 0.25

	var tick: float = 0.0
	while tick <= duration + 0.0001:
		var x: float = _time_to_x(tick, duration)
		if x >= label_width and x <= size.x:
			var major: bool = fmod(tick, major_step) < 0.001 or absf(fmod(tick, major_step) - major_step) < 0.001
			var tick_h: float = 10.0 if major else 5.0
			draw_line(Vector2(x, ruler_height - tick_h), Vector2(x, ruler_height - 1), Tokens.TIMELINE_RULER if major else Tokens.BORDER_SUBTLE, 1.0)
			if major:
				draw_string(ThemeDB.fallback_font, Vector2(x + 3, 14), _format_ruler_time(tick), HORIZONTAL_ALIGNMENT_LEFT, -1, Tokens.FONT_SMALL, Tokens.TEXT_MUTED)
		tick += snap

	draw_string(ThemeDB.fallback_font, Vector2(label_width + 6, 14), "Snap %.2f" % snap, HORIZONTAL_ALIGNMENT_LEFT, -1, Tokens.FONT_SMALL, Tokens.TEXT_MUTED)


func _draw_event_strip(duration: float, pps: float, track_y: float) -> void:
	draw_rect(Rect2(0, ruler_height, size.x, event_strip_height), Color(Tokens.PANEL_RAISED, 0.65), true)
	draw_line(Vector2(0, track_y - 1), Vector2(size.x, track_y - 1), Tokens.SEPARATOR, 1.0)
	for event_variant in document.get("timeline", {}).get("events", []):
		if not event_variant is Dictionary:
			continue
		var event: Dictionary = event_variant
		var event_x: float = _time_to_x(float(event.get("time", 0.0)), duration)
		if event_x < label_width or event_x > size.x:
			continue
		draw_line(Vector2(event_x, ruler_height + 2), Vector2(event_x, track_y - 3), Tokens.BRAND_AMBER, 2.0)
		draw_string(ThemeDB.fallback_font, Vector2(event_x + 4, track_y - 6), str(event.get("event_id", "event")), HORIZONTAL_ALIGNMENT_LEFT, -1, Tokens.FONT_SMALL, Tokens.BRAND_AMBER)


func _draw_tracks(duration: float, pps: float, track_y: float) -> void:
	var layers: Array = document.get("layers", [])
	for index in range(layers.size()):
		var y: float = track_y + float(index) * row_height
		draw_line(Vector2(0, y + row_height), Vector2(size.x, y + row_height), Tokens.SEPARATOR, 1.0)
		var layer_variant: Variant = layers[index]
		if not layer_variant is Dictionary:
			continue
		var layer: Dictionary = layer_variant
		var layer_id := str(layer.get("id", ""))
		var layer_type := str(layer.get("type", ""))
		var enabled: bool = bool(layer.get("enabled", true))
		var selected: bool = layer_id == selected_layer_id
		var label_color: Color = Tokens.TEXT_PRIMARY if enabled else Tokens.TEXT_MUTED
		if selected:
			draw_rect(Rect2(0, y + 1, label_width, row_height - 2), Tokens.SELECTION, true)
		var label_text := LayerIcons.glyph(layer_type) + "  " + str(layer.get("name", layer.get("id", "Layer")))
		draw_string(ThemeDB.fallback_font, Vector2(8, y + 17), label_text, HORIZONTAL_ALIGNMENT_LEFT, int(label_width - 12), Tokens.FONT_SMALL, label_color)

		var start: float = float(layer.get("start", 0.0))
		var end: float = start + float(layer.get("duration", duration))
		if layer_id == drag_layer_id and drag_mode != 0:
			start = drag_current_start
			end = drag_current_start + drag_current_duration
		var bar_x: float = _time_to_x(start, duration)
		var bar_w: float = max(4.0, (end - start) * pps)
		var bar_rect := Rect2(bar_x, y + 5, bar_w, row_height - 10)
		var bar_color: Color = _layer_color(layer_type, enabled)
		if selected:
			bar_color = bar_color.lightened(0.12)
		draw_style_box(_bar_style(bar_color, selected), bar_rect)
		if layer_id == _hover_layer_id and _hover_resize_end:
			draw_rect(Rect2(bar_rect.position.x + bar_rect.size.x - 3, bar_rect.position.y, 3, bar_rect.size.y), Tokens.TEXT_PRIMARY, true)


func _draw_playhead(duration: float, pps: float) -> void:
	var playhead_x: float = _time_to_x(current_time, duration)
	draw_line(Vector2(playhead_x, 0), Vector2(playhead_x, size.y), Tokens.TIMELINE_PLAYHEAD, 2.0)
	draw_string(ThemeDB.fallback_font, Vector2(playhead_x + 4, size.y - 4), "%.2f" % current_time, HORIZONTAL_ALIGNMENT_LEFT, -1, Tokens.FONT_SMALL, Tokens.BRAND_AMBER)


func _bar_style(color: Color, selected: bool) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.corner_radius_top_left = Tokens.RADIUS_SM
	style.corner_radius_top_right = Tokens.RADIUS_SM
	style.corner_radius_bottom_left = Tokens.RADIUS_SM
	style.corner_radius_bottom_right = Tokens.RADIUS_SM
	style.border_width_left = 1
	style.border_width_right = 1
	style.border_width_top = 1
	style.border_width_bottom = 1
	style.border_color = Tokens.SELECTION_BORDER if selected else color.lightened(0.18)
	return style


func _format_ruler_time(seconds: float) -> String:
	if seconds >= 60.0:
		return "%d:%02d" % [int(seconds) / 60, int(seconds) % 60]
	if fmod(seconds, 1.0) < 0.001:
		return str(int(seconds))
	return "%.2f" % seconds


func _layer_at_position(position: Vector2) -> Dictionary:
	var track_y: float = _track_start_y()
	if position.y < track_y:
		return {}
	var row_index := int(floor((position.y - track_y) / row_height))
	var layers: Array = document.get("layers", [])
	if row_index < 0 or row_index >= layers.size() or not layers[row_index] is Dictionary:
		return {}
	return layers[row_index]


func _gui_input(event: InputEvent) -> void:
	var duration: float = max(0.1, float(document.get("duration", 1.0)))
	var track_y: float = _track_start_y()

	if event is InputEventMouseMotion:
		var layer: Dictionary = _layer_at_position(event.position)
		if layer.is_empty():
			_hover_layer_id = ""
			_hover_resize_end = false
		else:
			_hover_layer_id = str(layer.get("id", ""))
			if event.position.x >= label_width:
				var start: float = float(layer.get("start", 0.0))
				var end: float = start + float(layer.get("duration", duration))
				var time: float = clamp(_x_to_time(event.position.x, duration), 0.0, duration)
				_hover_resize_end = absf(time - end) < 0.14
			else:
				_hover_resize_end = false
		queue_redraw()

	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_MIDDLE:
		if event.pressed:
			_panning = true
			_pan_anchor_x = event.position.x
			_pan_anchor_scroll = scroll_time
			accept_event()
		else:
			_panning = false
			accept_event()

	if event is InputEventMouseMotion and _panning:
		var pps: float = _pixels_per_second(duration)
		scroll_time = max(0.0, _pan_anchor_scroll - (event.position.x - _pan_anchor_x) / pps)
		queue_redraw()
		accept_event()

	if event is InputEventMouseButton and (event.button_index == MOUSE_BUTTON_WHEEL_UP or event.button_index == MOUSE_BUTTON_WHEEL_DOWN):
		var cursor_time: float = clamp(_x_to_time(event.position.x, duration), 0.0, duration)
		var old_pps: float = _pixels_per_second(duration)
		if event.ctrl_pressed or event.shift_pressed:
			var factor: float = 1.12 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / 1.12
			zoom = clamp(zoom * factor, 0.5, 12.0)
			var new_pps: float = _pixels_per_second(duration)
			scroll_time = cursor_time - (event.position.x - label_width) / new_pps
			scroll_time = max(0.0, scroll_time)
		else:
			scroll_time = max(0.0, scroll_time + (0.25 if event.button_index == MOUSE_BUTTON_WHEEL_DOWN else -0.25))
		queue_redraw()
		accept_event()

	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			var layer_at: Dictionary = _layer_at_position(event.position)
			if not layer_at.is_empty():
				var layer_id := str(layer_at.get("id", ""))
				layer_selected.emit(layer_id)
				if event.position.x >= label_width:
					var start: float = float(layer_at.get("start", 0.0))
					var layer_duration: float = float(layer_at.get("duration", duration))
					var end: float = start + layer_duration
					var time: float = clamp(_x_to_time(event.position.x, duration), 0.0, duration)
					if time >= start - 0.05 and time <= end + 0.05:
						drag_layer_id = layer_id
						drag_mode = 2 if absf(time - end) < 0.14 else 1
						drag_anchor_time = time
						drag_initial_start = start
						drag_initial_duration = layer_duration
						drag_current_start = start
						drag_current_duration = layer_duration
						accept_event()
						return
			if event.position.x >= label_width and event.position.y >= track_y:
				var scrub_time: float = clamp(_x_to_time(event.position.x, duration), 0.0, duration)
				scrubbed.emit(scrub_time)
				accept_event()
				return
		elif drag_mode != 0:
			layer_timing_changed.emit(drag_layer_id, drag_current_start, drag_current_duration)
			drag_layer_id = ""
			drag_mode = 0
			accept_event()
			return

	if event is InputEventMouseMotion and (event.button_mask & MOUSE_BUTTON_MASK_LEFT) != 0 and drag_mode != 0:
		var drag_time: float = clamp(_x_to_time(event.position.x, duration), 0.0, duration)
		var snap: float = max(0.001, float(document.get("timeline", {}).get("snap", 0.05)))
		var delta: float = drag_time - drag_anchor_time
		if drag_mode == 1:
			drag_current_start = max(0.0, round((drag_initial_start + delta) / snap) * snap)
		else:
			drag_current_duration = max(0.01, round((drag_initial_duration + delta) / snap) * snap)
		queue_redraw()
		accept_event()
	elif event is InputEventMouseMotion and (event.button_mask & MOUSE_BUTTON_MASK_LEFT) != 0 and drag_mode == 0 and event.position.x >= label_width:
		var drag_time: float = clamp(_x_to_time(event.position.x, duration), 0.0, duration)
		scrubbed.emit(drag_time)
		accept_event()
