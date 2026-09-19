class_name VFXViewportGizmos
extends Node3D

signal gizmo_changed(layer_id: String, path: String, value: Variant)

const Tokens := preload("res://godot/ui/theme/tokens.gd")

var selected_layer_id: String = ""
var selected_layer: Dictionary = {}
var show_overlays: bool = true

var _root: Node3D
var _drag_handle: String = ""
var _drag_plane := Plane()
var _drag_start := Vector3.ZERO
var _drag_path := ""
var _drag_layer_id := ""


func _init() -> void:
	name = "ViewportGizmos"
	_root = Node3D.new()
	_root.name = "GizmoRoot"
	add_child(_root)


func set_selection(layer_id: String, layer: Dictionary) -> void:
	selected_layer_id = layer_id
	selected_layer = layer
	_rebuild()


func set_overlays_visible(visible: bool) -> void:
	show_overlays = visible
	_root.visible = visible


func update_bounds_box(bounds: AABB, visible: bool) -> void:
	_clear_named("effect_bounds")
	if not visible or bounds.size.length_squared() < 0.00001:
		return
	_add_wire_box(bounds, "effect_bounds", Tokens.ACCENT_CYAN, 0.55)


func _rebuild() -> void:
	for child in _root.get_children():
		if str(child.name) != "effect_bounds":
			child.queue_free()
	if selected_layer.is_empty() or not show_overlays:
		return
	var layer_type := str(selected_layer.get("type", ""))
	var properties: Dictionary = selected_layer.get("properties", {})
	match layer_type:
		"mesh_effect", "sprite", "decal":
			_add_transform_axes()
			if layer_type == "decal":
				_add_decal_footprint(properties)
		"beam":
			_add_beam_handles(properties)
		"light":
			_add_light_radius(properties)
		"particle", "mesh_particle":
			_add_emission_volume(properties)


func _add_transform_axes() -> void:
	_add_axis_line(Vector3.ZERO, Vector3.RIGHT * 0.8, Color("#D96B6B"), "axis_x")
	_add_axis_line(Vector3.ZERO, Vector3.UP * 0.8, Color("#6BC48A"), "axis_y")
	_add_axis_line(Vector3.ZERO, Vector3.BACK * 0.8, Color("#5EB8D4"), "axis_z")


func _add_decal_footprint(properties: Dictionary) -> void:
	var size := _vec2(properties.get("size", [2.0, 2.0]))
	var bounds := AABB(Vector3(-size.x * 0.5, 0.0, -size.y * 0.5), Vector3(size.x, 0.02, size.y))
	_add_wire_box(bounds, "decal_bounds", Tokens.BRAND_AMBER, 0.8)


func _add_beam_handles(properties: Dictionary) -> void:
	var source := _vec3(properties.get("source", [0.0, 0.0, 0.0]))
	var target := _vec3(properties.get("target", [0.0, 0.0, -4.0]))
	_add_handle_sphere(source, "beam_source", Tokens.ACCENT_CYAN)
	_add_handle_sphere(target, "beam_target", Tokens.BRAND_AMBER)
	_add_axis_line(source, target, Color("#E8EAED", 0.7), "beam_line")


func _add_light_radius(properties: Dictionary) -> void:
	var radius: float = max(0.1, float(properties.get("range", 3.0)))
	_add_wire_sphere(Vector3.ZERO, radius, "light_range", Tokens.BRAND_AMBER)


func _add_emission_volume(properties: Dictionary) -> void:
	var shape := str(properties.get("emission_shape", "point"))
	match shape:
		"box":
			var extents := _vec3(properties.get("emission_box_extents", [0.25, 0.25, 0.25]))
			_add_wire_box(AABB(-extents, extents * 2.0), "emission_box", Tokens.ACCENT_CYAN, 0.75)
			_add_handle_sphere(extents, "emission_box_handle", Tokens.BRAND_AMBER, 0.09)
		"sphere", "sphere_surface", "ring", "disc":
			var radius: float = max(0.05, float(properties.get("emission_radius", 0.5)))
			_add_wire_sphere(Vector3.ZERO, radius, "emission_sphere", Tokens.ACCENT_CYAN)
			_add_handle_sphere(Vector3(radius, 0.0, 0.0), "emission_radius_handle", Tokens.BRAND_AMBER, 0.09)
		_:
			_add_handle_sphere(Vector3.ZERO, "emission_point", Tokens.ACCENT_CYAN, 0.08)


func try_begin_drag(camera: Camera3D, screen_position: Vector2) -> bool:
	if selected_layer.is_empty() or camera == null:
		return false
	var layer_type := str(selected_layer.get("type", ""))
	var handles: Array[String] = []
	if layer_type == "beam":
		handles = ["beam_source", "beam_target"]
	elif layer_type in ["particle", "mesh_particle"]:
		var shape := str(selected_layer.get("properties", {}).get("emission_shape", "point"))
		match shape:
			"box":
				handles = ["emission_box_handle"]
			"sphere", "sphere_surface", "ring", "disc":
				handles = ["emission_radius_handle"]
	if handles.is_empty():
		return false
	var origin := camera.project_ray_origin(screen_position)
	var direction := camera.project_ray_normal(screen_position)
	var nearest := ""
	var nearest_distance := 0.35
	for handle_name in handles:
		var node := _root.get_node_or_null(handle_name)
		if node == null:
			continue
		var closest := _ray_point_distance(origin, direction, node.global_position)
		if closest < nearest_distance:
			nearest_distance = closest
			nearest = handle_name
	if nearest.is_empty():
		return false
	_drag_handle = nearest
	_drag_layer_id = selected_layer_id
	match nearest:
		"beam_source":
			_drag_path = "properties.source"
		"beam_target":
			_drag_path = "properties.target"
		"emission_box_handle":
			_drag_path = "properties.emission_box_extents"
		"emission_radius_handle":
			_drag_path = "properties.emission_radius"
	var handle_node := _root.get_node(nearest)
	_drag_plane = Plane(camera.global_transform.basis.z, handle_node.global_position)
	return true


func update_drag(camera: Camera3D, screen_position: Vector2) -> void:
	if _drag_handle.is_empty() or camera == null:
		return
	var origin := camera.project_ray_origin(screen_position)
	var direction := camera.project_ray_normal(screen_position)
	var hit := _intersect_plane(origin, direction, _drag_plane)
	var handle_node := _root.get_node_or_null(_drag_handle)
	if handle_node != null:
		handle_node.position = hit
	match _drag_handle:
		"beam_source", "beam_target":
			var other_handle := "beam_target" if _drag_handle == "beam_source" else "beam_source"
			var other_node := _root.get_node_or_null(other_handle)
			var line := _root.get_node_or_null("beam_line") as MeshInstance3D
			if line != null and handle_node != null and other_node != null:
				line.queue_free()
				_add_axis_line(handle_node.position, other_node.position, Color("#E8EAED", 0.7), "beam_line")
		"emission_box_handle":
			var new_extents := Vector3(max(0.05, absf(hit.x)), max(0.05, absf(hit.y)), max(0.05, absf(hit.z)))
			handle_node.position = new_extents
			_clear_named("emission_box")
			_add_wire_box(AABB(-new_extents, new_extents * 2.0), "emission_box", Tokens.ACCENT_CYAN, 0.75)
		"emission_radius_handle":
			var radius: float = max(0.05, hit.length())
			handle_node.position = Vector3(radius, 0.0, 0.0)
			_clear_named("emission_sphere")
			_add_wire_sphere(Vector3.ZERO, radius, "emission_sphere", Tokens.ACCENT_CYAN)


func finish_drag() -> void:
	if _drag_handle.is_empty():
		return
	var handle_node := _root.get_node_or_null(_drag_handle)
	if handle_node == null:
		_drag_handle = ""
		_drag_path = ""
		_drag_layer_id = ""
		return
	var value: Variant = null
	match _drag_handle:
		"beam_source", "beam_target":
			value = [handle_node.position.x, handle_node.position.y, handle_node.position.z]
		"emission_box_handle":
			value = [absf(handle_node.position.x), absf(handle_node.position.y), absf(handle_node.position.z)]
		"emission_radius_handle":
			value = max(0.05, handle_node.position.length())
	if value != null:
		gizmo_changed.emit(_drag_layer_id, "layers." + _drag_layer_id + "." + _drag_path, value)
	_drag_handle = ""
	_drag_path = ""
	_drag_layer_id = ""


func _clear_named(node_name: String) -> void:
	var existing := _root.get_node_or_null(node_name)
	if existing != null:
		existing.queue_free()


func _add_wire_box(bounds: AABB, node_name: String, color: Color, alpha: float = 0.7) -> void:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = node_name
	var immediate := ImmediateMesh.new()
	var corners: Array[Vector3] = [
		bounds.position,
		bounds.position + Vector3(bounds.size.x, 0, 0),
		bounds.position + Vector3(bounds.size.x, 0, bounds.size.z),
		bounds.position + Vector3(0, 0, bounds.size.z),
		bounds.position + Vector3(0, bounds.size.y, 0),
		bounds.position + bounds.size,
	]
	var edges: Array[Vector3] = [
		corners[0], corners[1], corners[1], corners[2], corners[2], corners[3], corners[3], corners[0],
		corners[4], corners[5], corners[5], corners[6], corners[6], corners[7], corners[7], corners[4],
		corners[0], corners[4], corners[1], corners[5], corners[2], corners[6], corners[3], corners[7],
	]
	immediate.surface_begin(Mesh.PRIMITIVE_LINES, _line_material(color, alpha))
	for point in edges:
		immediate.surface_add_vertex(point)
	immediate.surface_end()
	mesh_instance.mesh = immediate
	_root.add_child(mesh_instance)


func _add_wire_sphere(center: Vector3, radius: float, node_name: String, color: Color) -> void:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = node_name
	var immediate := ImmediateMesh.new()
	var material := _line_material(color, 0.65)
	immediate.surface_begin(Mesh.PRIMITIVE_LINE_STRIP, material)
	for index in range(65):
		var angle: float = TAU * float(index) / 64.0
		immediate.surface_add_vertex(center + Vector3(cos(angle) * radius, 0.0, sin(angle) * radius))
	immediate.surface_end()
	mesh_instance.mesh = immediate
	_root.add_child(mesh_instance)


func _add_axis_line(from: Vector3, to: Vector3, color: Color, node_name: String) -> void:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = node_name
	var immediate := ImmediateMesh.new()
	immediate.surface_begin(Mesh.PRIMITIVE_LINES, _line_material(color, 0.9))
	immediate.surface_add_vertex(from)
	immediate.surface_add_vertex(to)
	immediate.surface_end()
	mesh_instance.mesh = immediate
	_root.add_child(mesh_instance)


func _add_handle_sphere(position: Vector3, node_name: String, color: Color, radius: float = 0.12) -> void:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = node_name
	var sphere := SphereMesh.new()
	sphere.radius = radius
	sphere.height = radius * 2.0
	mesh_instance.mesh = sphere
	mesh_instance.position = position
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.emission_enabled = true
	material.emission = color
	material.emission_energy_multiplier = 1.4
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color.a = 0.85
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mesh_instance.material_override = material
	_root.add_child(mesh_instance)


func _line_material(color: Color, alpha: float) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color = Color(color.r, color.g, color.b, alpha)
	material.no_depth_test = true
	return material


func _ray_point_distance(origin: Vector3, direction: Vector3, point: Vector3) -> float:
	var projection: float = direction.dot(point - origin)
	var closest: Vector3 = origin + direction * clamp(projection, 0.0, 1000.0)
	return closest.distance_to(point)


func _intersect_plane(origin: Vector3, direction: Vector3, plane: Plane) -> Vector3:
	var denom: float = plane.normal.dot(direction)
	if absf(denom) < 0.0001:
		return origin
	var t: float = (plane.d - plane.normal.dot(origin)) / denom
	return origin + direction * max(0.0, t)


func _vec2(value: Variant) -> Vector2:
	if value is Array and value.size() >= 2:
		return Vector2(float(value[0]), float(value[1]))
	return Vector2.ONE


func _vec3(value: Variant) -> Vector3:
	if value is Array and value.size() >= 3:
		return Vector3(float(value[0]), float(value[1]), float(value[2]))
	return Vector3.ZERO
