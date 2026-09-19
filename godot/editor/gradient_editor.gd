class_name VFXGradientEditor
extends Control

signal gradient_changed(value: Array)
signal stop_selected(index: int, color: Color)

var stops: Array = [
    {"position": 0.0, "color": "#FFFFFFFF"},
    {"position": 1.0, "color": "#00000000"}
]
var selected_index: int = -1
var dragging: bool = false


func set_gradient(value: Variant) -> void:
    if value is Array and not value.is_empty():
        stops = value.duplicate(true)
    queue_redraw()


func get_gradient() -> Array:
    return stops.duplicate(true)


func _ready() -> void:
    custom_minimum_size = Vector2(220, 58)
    mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND


func _draw() -> void:
    var bar := Rect2(6, 8, size.x - 12, 28)
    var steps: int = max(1, int(bar.size.x))
    for index in range(steps):
        var normalized: float = float(index) / float(max(1, steps - 1))
        draw_rect(Rect2(bar.position.x + index, bar.position.y, 1.0, bar.size.y), _sample(normalized), true)
    draw_rect(bar, Color("#66748A"), false, 1.0)
    for index in range(stops.size()):
        var stop: Dictionary = stops[index]
        var x: float = bar.position.x + clamp(float(stop.get("position", 0.0)), 0.0, 1.0) * bar.size.x
        var color := Color.from_string(str(stop.get("color", "#FFFFFFFF")), Color.WHITE)
        draw_colored_polygon(PackedVector2Array([Vector2(x - 6, 42), Vector2(x + 6, 42), Vector2(x, 50)]), color)
        draw_line(Vector2(x, 38), Vector2(x, 52), Color("#E8F0FF") if index == selected_index else Color("#7D8CA4"), 2.0)


func _sample(position: float) -> Color:
    var ordered := stops.duplicate(true)
    ordered.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.get("position", 0.0)) < float(b.get("position", 0.0)))
    if ordered.is_empty():
        return Color.TRANSPARENT
    if position <= float(ordered[0].get("position", 0.0)):
        return Color.from_string(str(ordered[0].get("color", "#FFFFFFFF")), Color.WHITE)
    for index in range(ordered.size() - 1):
        var first: Dictionary = ordered[index]
        var second: Dictionary = ordered[index + 1]
        var first_position := float(first.get("position", 0.0))
        var second_position := float(second.get("position", 1.0))
        if position <= second_position:
            var ratio := inverse_lerp(first_position, second_position, position)
            return Color.from_string(str(first.get("color", "#FFFFFFFF")), Color.WHITE).lerp(Color.from_string(str(second.get("color", "#FFFFFFFF")), Color.WHITE), ratio)
    return Color.from_string(str(ordered.back().get("color", "#FFFFFFFF")), Color.WHITE)


func _gui_input(event: InputEvent) -> void:
    var bar := Rect2(6, 8, size.x - 12, 28)
    if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
        if event.pressed:
            selected_index = -1
            for index in range(stops.size()):
                var stop: Dictionary = stops[index]
                var x := bar.position.x + float(stop.get("position", 0.0)) * bar.size.x
                if absf(x - event.position.x) < 10.0:
                    selected_index = index
            if selected_index < 0:
                var position: float = clamp((event.position.x - bar.position.x) / bar.size.x, 0.0, 1.0)
                stops.append({"position": position, "color": "#FFFFFFFF"})
                _sort_stops()
                selected_index = _nearest_index(position)
                _emit_change()
            _emit_selection()
            dragging = true
            queue_redraw()
        else:
            dragging = false
    elif event is InputEventMouseMotion and dragging and selected_index >= 0:
        stops[selected_index]["position"] = clamp((event.position.x - bar.position.x) / bar.size.x, 0.0, 1.0)
        _sort_stops()
        _emit_change()
        queue_redraw()
    elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT and event.pressed and selected_index >= 0 and stops.size() > 2:
        stops.remove_at(selected_index)
        selected_index = -1
        _emit_change()
        queue_redraw()


func set_selected_color(color: Color) -> void:
    if selected_index < 0 or selected_index >= stops.size():
        return
    stops[selected_index]["color"] = color.to_html(true)
    _emit_change()
    queue_redraw()


func _sort_stops() -> void:
    stops.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.get("position", 0.0)) < float(b.get("position", 0.0)))


func _nearest_index(position: float) -> int:
    var nearest := 0
    var distance := INF
    for index in range(stops.size()):
        var next_distance := absf(float(stops[index].get("position", 0.0)) - position)
        if next_distance < distance:
            distance = next_distance
            nearest = index
    return nearest


func _emit_change() -> void:
    gradient_changed.emit(stops.duplicate(true))


func _emit_selection() -> void:
    if selected_index >= 0 and selected_index < stops.size():
        stop_selected.emit(selected_index, Color.from_string(str(stops[selected_index].get("color", "#FFFFFFFF")), Color.WHITE))
