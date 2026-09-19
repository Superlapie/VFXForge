extends SceneTree

const VISUAL_LAYER_TYPES := [
	"particle", "mesh_particle", "sprite", "light", "trail", "beam", "decal", "mesh_effect", "child_effect"
]

var _instance: Node
var _config: Dictionary = {}
var _document: Dictionary = {}
var _warned: bool = false


func _initialize() -> void:
	var config_file := FileAccess.open("res://smoke_config.json", FileAccess.READ)
	if config_file == null:
		push_error("HOST_LIBRARY_SMOKE missing smoke_config.json")
		quit(2)
		return
	var parsed: Variant = JSON.parse_string(config_file.get_as_text())
	if not parsed is Dictionary:
		push_error("HOST_LIBRARY_SMOKE invalid smoke_config.json")
		quit(2)
		return
	_config = parsed
	var resource_root := str(_config.get("resource_root", ""))
	if resource_root.is_empty():
		push_error("HOST_LIBRARY_SMOKE missing resource_root")
		quit(2)
		return
	var document_path := resource_root + "/document.vfx.json"
	var document_file := FileAccess.open(document_path, FileAccess.READ)
	if document_file == null:
		push_error("HOST_LIBRARY_SMOKE missing document: " + document_path)
		quit(2)
		return
	var document_variant: Variant = JSON.parse_string(document_file.get_as_text())
	if not document_variant is Dictionary:
		push_error("HOST_LIBRARY_SMOKE invalid document.vfx.json")
		quit(2)
		return
	_document = document_variant
	var scene: PackedScene = load(resource_root + "/effect.tscn") as PackedScene
	if scene == null:
		push_error("HOST_LIBRARY_SMOKE missing scene")
		quit(2)
		return
	_instance = scene.instantiate()
	if _instance == null:
		push_error("HOST_LIBRARY_SMOKE instantiate failed")
		quit(3)
		return
	if _instance.has_signal("runtime_warning"):
		_instance.connect("runtime_warning", _on_runtime_warning)
	root.add_child(_instance)
	await process_frame
	await process_frame
	if _instance == null or not is_instance_valid(_instance):
		push_error("HOST_LIBRARY_SMOKE runtime instance invalid after enter-tree")
		quit(4)
		return
	if _instance.has_method("play"):
		_instance.call("play")
	_instance.set("is_playing", false)
	var checkpoints: Array = _checkpoint_times()
	for checkpoint_variant in checkpoints:
		var checkpoint: float = float(checkpoint_variant)
		_instance.set("is_playing", false)
		if _instance.has_method("seek"):
			_instance.call("seek", checkpoint)
		if _warned:
			return
		if not _verify_at(checkpoint):
			return
		await process_frame
		await process_frame
		if not is_instance_valid(_instance):
			push_error("HOST_LIBRARY_SMOKE runtime instance invalid after processing t=" + str(checkpoint))
			quit(4)
			return
		_instance.set("is_playing", false)
		if _instance.has_method("seek"):
			_instance.call("seek", checkpoint)
		if not _verify_at(checkpoint):
			return
	if not await _verify_trail_history():
		return
	print("PASS host library smoke")
	quit(0)


func _checkpoint_times() -> Array:
	var values: Array = []
	var raw: Variant = _config.get("checkpoints", [])
	if raw is Array and not raw.is_empty():
		values = raw
	else:
		var duration: float = maxf(0.001, float(_config.get("duration", _document.get("duration", 1.0))))
		values = [0.0, duration * 0.25, duration * 0.5, duration * 0.75, duration]
	return values


func _on_runtime_warning(message: String) -> void:
	if _warned:
		return
	_warned = true
	push_error("HOST_LIBRARY_SMOKE runtime warning: " + message)
	quit(10)


func _verify_at(time: float) -> bool:
	if _instance == null or not is_instance_valid(_instance):
		push_error("HOST_LIBRARY_SMOKE runtime instance invalid at t=" + str(time))
		quit(4)
		return false
	var document_duration: float = maxf(0.001, float(_document.get("duration", 1.0)))
	for layer_variant in _document.get("layers", []):
		if not layer_variant is Dictionary:
			continue
		var layer: Dictionary = layer_variant
		if not bool(layer.get("enabled", true)):
			continue
		var layer_type := str(layer.get("type", ""))
		if layer_type not in VISUAL_LAYER_TYPES:
			continue
		var layer_id := str(layer.get("id", ""))
		if layer_id.is_empty():
			push_error("HOST_LIBRARY_SMOKE enabled visual layer missing id")
			quit(5)
			return false
		var node := _instance.get_node_or_null(NodePath(layer_id))
		if node == null:
			push_error("HOST_LIBRARY_SMOKE missing generated layer node: " + layer_id)
			quit(5)
			return false
		var start: float = float(layer.get("start", 0.0))
		var duration_variant: Variant = layer.get("duration", document_duration)
		var layer_duration: float = maxf(0.001, float(duration_variant))
		var local: float = time - start
		var expected_visible: bool = local + 0.0001 >= 0.0 and local <= layer_duration + 0.0001
		if node.visible != expected_visible:
			push_error(
				"HOST_LIBRARY_SMOKE layer visibility mismatch: %s at t=%s expected=%s actual=%s"
				% [layer_id, str(time), str(expected_visible), str(node.visible)]
			)
			quit(9)
			return false
		var properties_variant: Variant = layer.get("properties", {})
		var properties: Dictionary = properties_variant if properties_variant is Dictionary else {}
		var texture_ref := str(properties.get("texture", ""))
		if not texture_ref.is_empty():
			var texture: Resource = load(_resource_path(texture_ref))
			if texture == null:
				push_error("HOST_LIBRARY_SMOKE texture failed to load: " + texture_ref)
				quit(6)
				return false
		var mesh_ref := str(properties.get("mesh_asset", ""))
		if not mesh_ref.is_empty():
			var mesh: Resource = load(_resource_path(mesh_ref))
			if mesh == null:
				push_error("HOST_LIBRARY_SMOKE mesh failed to load: " + mesh_ref)
				quit(6)
				return false
		if layer_type == "child_effect":
			var child_id := str(properties.get("effect_id", ""))
			if child_id.is_empty():
				push_error("HOST_LIBRARY_SMOKE child_effect missing effect_id")
				quit(7)
				return false
		if layer_type == "trail":
			var trail_path := str(_instance.get("trail_script_path")) if "trail_script_path" in _instance else ""
			if trail_path.is_empty() or load(trail_path) == null:
				push_error("HOST_LIBRARY_SMOKE trail runtime missing")
				quit(8)
				return false
	return true


func _verify_trail_history() -> bool:
	for layer_variant in _document.get("layers", []):
		if not layer_variant is Dictionary:
			continue
		var layer: Dictionary = layer_variant
		if str(layer.get("type", "")) != "trail" or not bool(layer.get("enabled", true)):
			continue
		var layer_id := str(layer.get("id", ""))
		var trail := _instance.get_node_or_null(NodePath(layer_id))
		if trail == null:
			push_error("HOST_LIBRARY_SMOKE missing trail node: " + layer_id)
			quit(8)
			return false
		var tracker := Marker3D.new()
		tracker.name = "TrailTracker"
		root.add_child(tracker)
		var start_pos := Vector3(0.0, 1.0, 0.0)
		var end_pos := Vector3(2.0, 1.0, 0.0)
		tracker.global_position = start_pos
		if trail.has_method("set_tracking_node"):
			trail.call("set_tracking_node", tracker)
		for _i in range(8):
			await process_frame
		tracker.global_position = end_pos
		for _i in range(8):
			await process_frame
		if not trail.has_method("get_world_samples"):
			push_error("HOST_LIBRARY_SMOKE trail missing get_world_samples")
			quit(8)
			return false
		var samples: PackedVector3Array = trail.call("get_world_samples")
		if samples.size() < 2:
			push_error("HOST_LIBRARY_SMOKE trail did not record world samples")
			quit(8)
			return false
		var min_x: float = samples[0].x
		var max_x: float = samples[0].x
		for sample in samples:
			min_x = minf(min_x, sample.x)
			max_x = maxf(max_x, sample.x)
		if min_x > 0.35 or max_x < 1.65:
			push_error(
				"HOST_LIBRARY_SMOKE trail history did not span attachment motion: min_x=%s max_x=%s"
				% [str(min_x), str(max_x)]
			)
			quit(8)
			return false
	return true


func _resource_path(reference: String) -> String:
	var resource_root := str(_config.get("resource_root", ""))
	if reference.begins_with("res://"):
		return reference
	return resource_root + "/" + reference.trim_prefix("./")
