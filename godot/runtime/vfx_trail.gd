class_name VFXTrail
extends MeshInstance3D

var trail_width: float = 0.18
var trail_lifetime: float = 0.35
var trail_color: Color = Color(0.6, 0.7, 1.0, 0.9)
var trail_material: StandardMaterial3D
var history: Array[Dictionary] = []
var elapsed: float = 0.0
var phase: float = 0.0
var preview_motion: bool = false
var tracking_path: String = ""
var tracking_node: Node3D = null
var trail_segments: int = 20
var width_profile_curve: Dictionary = {}
var _sample_interval: float = 0.02
var _sample_accumulator: float = 0.0


func configure(
    width: float,
    lifetime: float,
    color: Color,
    segments: int = 20,
    width_curve: Dictionary = {},
    alpha_multiplier: float = 1.0,
) -> void:
    trail_width = maxf(0.01, width)
    trail_lifetime = maxf(0.02, lifetime)
    trail_color = color
    trail_color.a *= clampf(alpha_multiplier, 0.0, 1.0)
    trail_segments = clampi(segments, 2, 64)
    width_profile_curve = width_curve if width_curve is Dictionary else {}
    _sample_interval = trail_lifetime / float(trail_segments)
    trail_material = StandardMaterial3D.new()
    trail_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    trail_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
    trail_material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
    trail_material.albedo_color = trail_color
    trail_material.emission_enabled = true
    trail_material.emission = trail_color
    trail_material.emission_energy_multiplier = 1.5
    set_process(true)


func set_tracking_node(node: Node3D) -> void:
    tracking_node = node
    preview_motion = false


func push_sample(world_position: Vector3) -> void:
    history.push_front({"position": world_position, "age": 0.0})
    while history.size() > trail_segments:
        history.pop_back()


func get_world_samples() -> PackedVector3Array:
    var samples := PackedVector3Array()
    for sample in history:
        samples.append(sample.get("position", Vector3.ZERO))
    return samples


func _resolve_tracking_node() -> Node3D:
    if is_instance_valid(tracking_node):
        return tracking_node
    if tracking_path.is_empty():
        return null
    var from_self := get_node_or_null(NodePath(tracking_path))
    if from_self is Node3D:
        tracking_node = from_self as Node3D
        preview_motion = false
        return tracking_node
    return null


func _sample_world_position() -> Vector3:
    var tracked := _resolve_tracking_node()
    if tracked != null:
        return tracked.global_position
    if preview_motion:
        phase += get_process_delta_time()
        var orbit := Vector3(sin(phase * 4.0) * 0.55, 0.75 + cos(phase * 2.5) * 0.18, cos(phase * 3.0) * 0.3)
        return global_position + orbit
    return global_position


func _process(delta: float) -> void:
    elapsed += delta
    _sample_accumulator += delta
    if history.is_empty() or _sample_accumulator >= _sample_interval:
        _sample_accumulator = 0.0
        push_sample(_sample_world_position())
    for sample in history:
        sample["age"] = float(sample.get("age", 0.0)) + delta
    while not history.is_empty() and float(history.back().get("age", 0.0)) > trail_lifetime:
        history.pop_back()
    _rebuild_mesh()


func _rebuild_mesh() -> void:
    if trail_material == null or history.size() < 2:
        return
    var ribbon := ImmediateMesh.new()
    ribbon.surface_begin(Mesh.PRIMITIVE_TRIANGLE_STRIP, trail_material)
    for index in range(history.size()):
        var sample: Dictionary = history[index]
        var world_position: Vector3 = sample.get("position", Vector3.ZERO)
        var position: Vector3 = to_local(world_position)
        var next_position: Vector3 = position
        if index + 1 < history.size():
            next_position = to_local(history[index + 1].get("position", world_position))
        var tangent := (position - next_position).normalized()
        if tangent.length_squared() < 0.001:
            tangent = Vector3.FORWARD
        var side := tangent.cross(Vector3.UP).normalized()
        if side.length_squared() < 0.001:
            side = tangent.cross(Vector3.RIGHT).normalized()
        var ratio: float = float(index) / maxf(1.0, float(history.size() - 1))
        var width_profile: float = _curve_value(width_profile_curve, ratio, 1.0 - ratio)
        var width: float = trail_width * width_profile
        var alpha: float = (1.0 - ratio) * clampf(1.0 - float(sample.get("age", 0.0)) / trail_lifetime, 0.0, 1.0)
        var vertex_color := Color(trail_color.r, trail_color.g, trail_color.b, trail_color.a * alpha)
        ribbon.surface_set_color(vertex_color)
        ribbon.surface_set_uv(Vector2(ratio, 0.0))
        ribbon.surface_add_vertex(position - side * width)
        ribbon.surface_set_color(vertex_color)
        ribbon.surface_set_uv(Vector2(ratio, 1.0))
        ribbon.surface_add_vertex(position + side * width)
    ribbon.surface_end()
    mesh = ribbon


func _curve_value(value: Variant, position: float, fallback: float) -> float:
    if not value is Dictionary:
        return fallback
    var points_variant: Variant = value.get("points", [])
    if not points_variant is Array or points_variant.is_empty():
        return fallback
    var parsed: Array[Vector2] = []
    for point_variant in points_variant:
        if point_variant is Dictionary:
            parsed.append(Vector2(float(point_variant.get("x", 0.0)), float(point_variant.get("y", 0.0))))
    if parsed.is_empty():
        return fallback
    parsed.sort_custom(func(a: Vector2, b: Vector2) -> bool: return a.x < b.x)
    if position <= parsed[0].x:
        return parsed[0].y
    if position >= parsed[-1].x:
        return parsed[-1].y
    for curve_index in range(parsed.size() - 1):
        var first := parsed[curve_index]
        var second := parsed[curve_index + 1]
        if position >= first.x and position <= second.x:
            return lerpf(first.y, second.y, inverse_lerp(first.x, second.x, position))
    return fallback
