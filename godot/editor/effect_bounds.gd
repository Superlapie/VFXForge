class_name VFXEffectBounds
extends RefCounted


static func from_document(document: Dictionary) -> AABB:
	var merged := AABB()
	var has_bounds := false
	for layer_variant in document.get("layers", []):
		if not layer_variant is Dictionary:
			continue
		if not bool(layer_variant.get("enabled", true)):
			continue
		var layer_bounds := _layer_bounds(layer_variant, float(document.get("duration", 1.0)))
		if layer_bounds.size.length_squared() < 0.000001:
			continue
		if has_bounds:
			merged = merged.merge(layer_bounds)
		else:
			merged = layer_bounds
			has_bounds = true
	if not has_bounds:
		return AABB(Vector3(-0.75, 0.0, -0.75), Vector3(1.5, 1.5, 1.5))
	return merged


static func _layer_bounds(layer: Dictionary, _duration: float) -> AABB:
	var layer_type := str(layer.get("type", ""))
	var properties: Dictionary = layer.get("properties", {})
	match layer_type:
		"mesh_effect":
			var size := _vec3(properties.get("size", [1.0, 1.0, 1.0]))
			return AABB(-size * 0.5, size)
		"mesh_particle":
			var mesh_size := _vec3(properties.get("size", [0.15, 0.15, 0.15]))
			return _emission_bounds(properties).merge(AABB(-mesh_size * 0.5, mesh_size))
		"sprite", "decal":
			var flat_size := _vec3(properties.get("size", [1.0, 1.0]))
			return AABB(Vector3(-flat_size.x * 0.5, 0.0, -flat_size.y * 0.5), Vector3(flat_size.x, 0.05, flat_size.y))
		"beam":
			var source := _vec3(properties.get("source", [0.0, 0.0, 0.0]))
			var target := _vec3(properties.get("target", [0.0, 0.0, -4.0]))
			return _points_bounds([source, target], 0.25)
		"light":
			var radius: float = max(0.1, float(properties.get("range", 3.0)))
			return AABB(Vector3(-radius, -radius, -radius), Vector3(radius, radius, radius) * 2.0)
		"particle":
			return _emission_bounds(properties)
		"trail":
			return AABB(Vector3(-0.5, 0.0, -0.5), Vector3(1.0, 1.0, 1.0))
		_:
			return AABB(Vector3(-0.5, 0.0, -0.5), Vector3(1.0, 1.0, 1.0))


static func _emission_bounds(properties: Dictionary) -> AABB:
	var shape := str(properties.get("emission_shape", "point"))
	match shape:
		"box":
			var extents := _vec3(properties.get("emission_box_extents", [0.25, 0.25, 0.25]))
			return AABB(-extents, extents * 2.0)
		"sphere", "sphere_surface", "ring", "disc":
			var radius: float = max(0.05, float(properties.get("emission_radius", 0.5)))
			var height: float = max(0.05, float(properties.get("emission_height", 0.1)))
			return AABB(Vector3(-radius, -height * 0.5, -radius), Vector3(radius * 2.0, height, radius * 2.0))
		_:
			return AABB(Vector3(-0.15, -0.15, -0.15), Vector3(0.3, 0.3, 0.3))


static func _points_bounds(points: Array, padding: float) -> AABB:
	var min_v := Vector3(INF, INF, INF)
	var max_v := Vector3(-INF, -INF, -INF)
	for point_variant in points:
		if point_variant is Array and point_variant.size() >= 3:
			var point := Vector3(float(point_variant[0]), float(point_variant[1]), float(point_variant[2]))
			min_v = min_v.min(point)
			max_v = max_v.max(point)
	return AABB(min_v - Vector3.ONE * padding, (max_v - min_v) + Vector3.ONE * padding * 2.0)


static func _vec3(value: Variant) -> Vector3:
	if value is Array and value.size() >= 3:
		return Vector3(float(value[0]), float(value[1]), float(value[2]))
	if value is Array and value.size() >= 2:
		return Vector3(float(value[0]), float(value[1]), 0.0)
	return Vector3.ZERO
