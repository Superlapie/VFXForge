class_name VFXPreviewView
extends SubViewportContainer

var preview_camera: Camera3D
var target: Vector3 = Vector3(0.0, 0.8, 0.0)
var distance: float = 7.0
var yaw: float = 0.68
var pitch: float = 0.38
var drag_mode: int = 0


func _ready() -> void:
    mouse_filter = Control.MOUSE_FILTER_STOP


func set_camera(camera: Camera3D) -> void:
    preview_camera = camera
    sync_from_camera()


func sync_from_camera() -> void:
    if preview_camera == null:
        return
    var offset := preview_camera.position - target
    distance = max(0.5, offset.length())
    yaw = atan2(offset.x, offset.z)
    pitch = asin(clamp(offset.y / distance, -0.98, 0.98))


func reset_view() -> void:
    target = Vector3(0.0, 0.8, 0.0)
    distance = 7.0
    yaw = 0.68
    pitch = 0.38
    _apply_orbit()


func _gui_input(event: InputEvent) -> void:
    if preview_camera == null:
        return
    if event is InputEventMouseButton:
        if event.button_index == MOUSE_BUTTON_LEFT or event.button_index == MOUSE_BUTTON_RIGHT or event.button_index == MOUSE_BUTTON_MIDDLE:
            drag_mode = event.button_index if event.pressed else 0
            accept_event()
        elif event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
            distance = max(0.5, distance * 0.88)
            _apply_orbit()
            accept_event()
        elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
            distance = min(50.0, distance * 1.14)
            _apply_orbit()
            accept_event()
    elif event is InputEventMouseMotion and drag_mode != 0:
        if drag_mode == MOUSE_BUTTON_LEFT or drag_mode == MOUSE_BUTTON_RIGHT:
            yaw -= event.relative.x * 0.008
            pitch = clamp(pitch - event.relative.y * 0.008, -1.42, 1.42)
            _apply_orbit()
        elif drag_mode == MOUSE_BUTTON_MIDDLE:
            var scale := distance * 0.0025
            var right := preview_camera.global_transform.basis.x
            var up := preview_camera.global_transform.basis.y
            target -= right * event.relative.x * scale
            target += up * event.relative.y * scale
            _apply_orbit()
        accept_event()


func _apply_orbit() -> void:
    if preview_camera == null:
        return
    var horizontal := cos(pitch) * distance
    preview_camera.position = target + Vector3(sin(yaw) * horizontal, sin(pitch) * distance, cos(yaw) * horizontal)
    preview_camera.look_at(target)
