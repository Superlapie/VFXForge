class_name VFXCurveEditor
extends Control

signal curve_changed(value: Dictionary)

var curve_data: Dictionary = {"interpolation": "linear", "points": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]}
var selected_index: int = -1
var dragging: bool = false


func set_curve(value: Variant) -> void:
    if value is Dictionary:
        curve_data = value.duplicate(true)
    if not curve_data.has("points") or not curve_data["points"] is Array:
        curve_data["points"] = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]
    queue_redraw()


func get_curve() -> Dictionary:
    return curve_data.duplicate(true)


func _ready() -> void:
    custom_minimum_size = Vector2(220, 100)
    mouse_default_cursor_shape = Control.CURSOR_CROSS


func _draw() -> void:
    var rect := Rect2(4, 4, size.x - 8, size.y - 8)
    draw_rect(rect, Color("#111827"), true)
    for index in range(1, 4):
        var x := rect.position.x + rect.size.x * float(index) / 4.0
        var y := rect.position.y + rect.size.y * float(index) / 4.0
        draw_line(Vector2(x, rect.position.y), Vector2(x, rect.end.y), Color("#26344B"), 1.0)
        draw_line(Vector2(rect.position.x, y), Vector2(rect.end.x, y), Color("#26344B"), 1.0)
    draw_rect(rect, Color("#52627B"), false, 1.0)
    var points := _screen_points(rect)
    if points.size() > 1:
        for index in range(points.size() - 1):
            draw_line(points[index], points[index + 1], Color("#8CD9FF"), 2.0, true)
    for index in range(points.size()):
        var point_color := Color("#F6C760") if index == selected_index else Color("#E8F0FF")
        draw_circle(points[index], 5.0, point_color)
        draw_circle(points[index], 6.0, Color("#09111F"), false, 1.0)


func _screen_points(rect: Rect2) -> Array[Vector2]:
    var result: Array[Vector2] = []
    for point_variant in curve_data.get("points", []):
        if point_variant is Dictionary:
            var point: Dictionary = point_variant
            result.append(Vector2(
                rect.position.x + float(point.get("x", 0.0)) * rect.size.x,
                rect.end.y - clamp(float(point.get("y", 0.0)), 0.0, 1.0) * rect.size.y
            ))
    return result


func _gui_input(event: InputEvent) -> void:
    var rect := Rect2(4, 4, size.x - 8, size.y - 8)
    if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
        if event.pressed:
            var points := _screen_points(rect)
            selected_index = -1
            var closest := 12.0
            for index in range(points.size()):
                var distance := points[index].distance_to(event.position)
                if distance < closest:
                    closest = distance
                    selected_index = index
            if selected_index < 0:
                var point := {
                    "x": clamp((event.position.x - rect.position.x) / rect.size.x, 0.0, 1.0),
                    "y": clamp((rect.end.y - event.position.y) / rect.size.y, 0.0, 1.0)
                }
                curve_data["points"].append(point)
                _sort_points()
                selected_index = _nearest_index(point)
                _emit_change()
            dragging = true
            queue_redraw()
        else:
            dragging = false
    elif event is InputEventMouseMotion and dragging and selected_index >= 0:
        var point: Dictionary = curve_data["points"][selected_index]
        point["x"] = clamp((event.position.x - rect.position.x) / rect.size.x, 0.0, 1.0)
        point["y"] = clamp((rect.end.y - event.position.y) / rect.size.y, 0.0, 1.0)
        curve_data["points"][selected_index] = point
        _sort_points()
        _emit_change()
        queue_redraw()
    elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
        if selected_index >= 0 and curve_data["points"].size() > 2:
            curve_data["points"].remove_at(selected_index)
            selected_index = -1
            _emit_change()
            queue_redraw()


func _sort_points() -> void:
    curve_data["points"].sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.get("x", 0.0)) < float(b.get("x", 0.0)))


func _nearest_index(point: Dictionary) -> int:
    var nearest := 0
    var best := INF
    for index in range(curve_data["points"].size()):
        var item: Dictionary = curve_data["points"][index]
        var distance := absf(float(item.get("x", 0.0)) - float(point.get("x", 0.0)))
        if distance < best:
            best = distance
            nearest = index
    return nearest


func _emit_change() -> void:
    curve_changed.emit(curve_data.duplicate(true))
