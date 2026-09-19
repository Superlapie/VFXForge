class_name VFXTimelineView
extends Control

signal scrubbed(time: float)
signal layer_timing_changed(layer_id: String, start: float, duration: float)

var document: Dictionary = {}
var current_time: float = 0.0
var zoom: float = 1.0
var scroll_time: float = 0.0
var row_height: float = 25.0
var drag_layer_id: String = ""
var drag_mode: int = 0
var drag_anchor_time: float = 0.0
var drag_initial_start: float = 0.0
var drag_initial_duration: float = 1.0
var drag_current_start: float = 0.0
var drag_current_duration: float = 1.0


func set_document(value: Dictionary) -> void:
    document = value
    queue_redraw()


func set_time(value: float) -> void:
    current_time = value
    queue_redraw()


func _ready() -> void:
    custom_minimum_size = Vector2(300, 160)
    mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND


func _draw() -> void:
    draw_rect(Rect2(Vector2.ZERO, size), Color("#0B1220"), true)
    var duration: float = max(0.1, float(document.get("duration", 1.0)))
    var label_width: float = 112.0
    var timeline_width: float = max(1.0, size.x - label_width)
    var pixels_per_second: float = timeline_width / duration * zoom
    for second in range(int(ceil(duration)) + 1):
        var x: float = label_width + float(second) * pixels_per_second - scroll_time * pixels_per_second
        if x < label_width or x > size.x:
            continue
        draw_line(Vector2(x, 0), Vector2(x, size.y), Color("#26344B"), 1.0)
        draw_string(ThemeDB.fallback_font, Vector2(x + 3, 16), str(second), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color("#8291A9"))
    draw_line(Vector2(label_width, 22), Vector2(size.x, 22), Color("#31425D"), 1.0)
    var layers: Array = document.get("layers", [])
    for index in range(layers.size()):
        var y: float = 26.0 + float(index) * row_height
        draw_line(Vector2(0, y + row_height), Vector2(size.x, y + row_height), Color("#17243A"), 1.0)
        var layer_variant: Variant = layers[index]
        if not layer_variant is Dictionary:
            continue
        var layer: Dictionary = layer_variant
        draw_string(ThemeDB.fallback_font, Vector2(8, y + 17), str(layer.get("name", layer.get("id", "Layer"))), HORIZONTAL_ALIGNMENT_LEFT, label_width - 16, 11, Color("#CBD7E8"))
        var start: float = float(layer.get("start", 0.0))
        var end: float = start + float(layer.get("duration", duration))
        if str(layer.get("id", "")) == drag_layer_id and drag_mode != 0:
            start = drag_current_start
            end = drag_current_start + drag_current_duration
        var bar_rect: Rect2 = Rect2(label_width + start * pixels_per_second - scroll_time * pixels_per_second, y + 4, max(4.0, (end - start) * pixels_per_second), row_height - 8)
        var bar_color: Color = Color("#5D72C8") if bool(layer.get("enabled", true)) else Color("#3C4659")
        draw_style_box(_bar_style(bar_color), bar_rect)
    for event_variant in document.get("timeline", {}).get("events", []):
        if not event_variant is Dictionary:
            continue
        var event: Dictionary = event_variant
        var event_x: float = label_width + float(event.get("time", 0.0)) * pixels_per_second - scroll_time * pixels_per_second
        if event_x >= label_width and event_x <= size.x:
            draw_line(Vector2(event_x, 20), Vector2(event_x, size.y), Color("#F6C760"), 2.0)
            draw_string(ThemeDB.fallback_font, Vector2(event_x + 4, size.y - 7), str(event.get("event_id", "event")), HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color("#F6C760"))
    var playhead_x: float = label_width + current_time * pixels_per_second - scroll_time * pixels_per_second
    draw_line(Vector2(playhead_x, 0), Vector2(playhead_x, size.y), Color("#F7F2D0"), 2.0)


func _bar_style(color: Color) -> StyleBoxFlat:
    var style := StyleBoxFlat.new()
    style.bg_color = color
    style.corner_radius_top_left = 4
    style.corner_radius_top_right = 4
    style.corner_radius_bottom_left = 4
    style.corner_radius_bottom_right = 4
    style.border_width_left = 1
    style.border_width_right = 1
    style.border_width_top = 1
    style.border_width_bottom = 1
    style.border_color = color.lightened(0.22)
    return style


func _gui_input(event: InputEvent) -> void:
    var label_width: float = 112.0
    var duration: float = max(0.1, float(document.get("duration", 1.0)))
    var pixels_per_second: float = max(1.0, (size.x - label_width) / duration * zoom)
    if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
        var time: float = clamp((event.position.x - label_width) / pixels_per_second + scroll_time, 0.0, duration)
        var row_index := int(floor((event.position.y - 26.0) / row_height))
        var layers: Array = document.get("layers", [])
        if event.position.x >= label_width and row_index >= 0 and row_index < layers.size() and layers[row_index] is Dictionary:
            var layer: Dictionary = layers[row_index]
            var start: float = float(layer.get("start", 0.0))
            var layer_duration: float = float(layer.get("duration", 1.0))
            var end: float = start + layer_duration
            if time >= start - 0.05 and time <= end + 0.05:
                drag_layer_id = str(layer.get("id", ""))
                drag_mode = 2 if absf(time - end) < 0.14 else 1
                drag_anchor_time = time
                drag_initial_start = start
                drag_initial_duration = layer_duration
                drag_current_start = start
                drag_current_duration = layer_duration
                accept_event()
                return
        scrubbed.emit(time)
        accept_event()
    elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed and drag_mode != 0:
        layer_timing_changed.emit(drag_layer_id, drag_current_start, drag_current_duration)
        drag_layer_id = ""
        drag_mode = 0
        accept_event()
    elif event is InputEventMouseMotion and (event.button_mask & MOUSE_BUTTON_MASK_LEFT) != 0:
        var drag_time: float = clamp((event.position.x - label_width) / pixels_per_second + scroll_time, 0.0, duration)
        if drag_mode != 0:
            var snap: float = max(0.001, float(document.get("timeline", {}).get("snap", 0.05)))
            var delta: float = drag_time - drag_anchor_time
            if drag_mode == 1:
                drag_current_start = max(0.0, round((drag_initial_start + delta) / snap) * snap)
            else:
                drag_current_duration = max(0.01, round((drag_initial_duration + delta) / snap) * snap)
            queue_redraw()
        else:
            scrubbed.emit(drag_time)
        accept_event()
    elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_WHEEL_UP:
        zoom = clamp(zoom * 1.12, 0.5, 6.0)
        queue_redraw()
    elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
        zoom = clamp(zoom / 1.12, 0.5, 6.0)
        queue_redraw()
