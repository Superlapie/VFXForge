class_name VFXTrail
extends MeshInstance3D

var trail_width: float = 0.18
var trail_lifetime: float = 0.35
var trail_color: Color = Color(0.6, 0.7, 1.0, 0.9)
var trail_material: StandardMaterial3D
var history: Array[Dictionary] = []
var elapsed: float = 0.0
var phase: float = 0.0


func configure(width: float, lifetime: float, color: Color) -> void:
    trail_width = max(0.01, width)
    trail_lifetime = max(0.02, lifetime)
    trail_color = color
    trail_material = StandardMaterial3D.new()
    trail_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    trail_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
    trail_material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
    trail_material.albedo_color = trail_color
    trail_material.emission_enabled = true
    trail_material.emission = trail_color
    trail_material.emission_energy_multiplier = 1.5
    set_process(true)


func _process(delta: float) -> void:
    elapsed += delta
    phase += delta
    # A moving sample makes a standalone preview useful; a game can update
    # global_position externally and the ribbon will follow it.
    var sample_position := Vector3(sin(phase * 4.0) * 0.55, 0.75 + cos(phase * 2.5) * 0.18, cos(phase * 3.0) * 0.3)
    history.push_front({"position": sample_position, "age": 0.0})
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
        var position: Vector3 = sample.get("position", Vector3.ZERO)
        var next_position: Vector3 = position
        if index + 1 < history.size():
            next_position = history[index + 1].get("position", position)
        var tangent := (position - next_position).normalized()
        if tangent.length_squared() < 0.001:
            tangent = Vector3.FORWARD
        var side := tangent.cross(Vector3.UP).normalized()
        if side.length_squared() < 0.001:
            side = tangent.cross(Vector3.RIGHT).normalized()
        var ratio: float = float(index) / max(1.0, float(history.size() - 1))
        var width: float = trail_width * (1.0 - ratio) * (1.0 - ratio * 0.35)
        var alpha: float = (1.0 - ratio) * clamp(1.0 - float(sample.get("age", 0.0)) / trail_lifetime, 0.0, 1.0)
        var vertex_color := Color(trail_color.r, trail_color.g, trail_color.b, trail_color.a * alpha)
        ribbon.surface_set_color(vertex_color)
        ribbon.surface_set_uv(Vector2(ratio, 0.0))
        ribbon.surface_add_vertex(position - side * width)
        ribbon.surface_set_color(vertex_color)
        ribbon.surface_set_uv(Vector2(ratio, 1.0))
        ribbon.surface_add_vertex(position + side * width)
    ribbon.surface_end()
    mesh = ribbon
