extends SceneTree

const VISUAL_LAYER_TYPES := [
	"particle", "mesh_particle", "sprite", "light", "trail", "beam", "decal", "mesh_effect", "child_effect"
]

var _instance: Node
var _config: Dictionary = {}
var _document: Dictionary = {}


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
	var scene := load(resource_root + "/effect.tscn")
	if scene == null:
		push_error("HOST_LIBRARY_SMOKE missing scene")
		quit(2)
		return
	_instance = (scene as PackedScene).instantiate()
	if _instance == null:
		push_error("HOST_LIBRARY_SMOKE instantiate failed")
		quit(3)
		return
	root.add_child(_instance)
	if _instance.has_method("play"):
		_instance.call("play")
	var frame_count := int(_config.get("frame_count", 30))
	for _i in range(frame_count):
		await process_frame
	_verify()


func _verify() -> void:
	if _instance == null or not is_instance_valid(_instance):
		push_error("HOST_LIBRARY_SMOKE runtime instance invalid")
		quit(4)
		return
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
			return
		var node := _instance.get_node_or_null(NodePath(layer_id))
		if node == null:
			push_error("HOST_LIBRARY_SMOKE missing generated layer node: " + layer_id)
			quit(5)
			return
		var properties: Dictionary = layer.get("properties", {}) if layer.get("properties", {}) is Dictionary else {}
		var texture_ref := str(properties.get("texture", ""))
		if not texture_ref.is_empty():
			var texture := load(_resource_path(texture_ref))
			if texture == null:
				push_error("HOST_LIBRARY_SMOKE texture failed to load: " + texture_ref)
				quit(6)
				return
		var mesh_ref := str(properties.get("mesh_asset", ""))
		if not mesh_ref.is_empty():
			var mesh := load(_resource_path(mesh_ref))
			if mesh == null:
				push_error("HOST_LIBRARY_SMOKE mesh failed to load: " + mesh_ref)
				quit(6)
				return
		if layer_type == "child_effect":
			var child_id := str(properties.get("effect_id", ""))
			if child_id.is_empty():
				push_error("HOST_LIBRARY_SMOKE child_effect missing effect_id")
				quit(7)
				return
		if layer_type == "trail":
			var trail_path := str(_instance.get("trail_script_path")) if "trail_script_path" in _instance else ""
			if trail_path.is_empty() or load(trail_path) == null:
				push_error("HOST_LIBRARY_SMOKE trail runtime missing")
				quit(8)
				return
	print("PASS host library smoke")
	quit(0)


func _resource_path(reference: String) -> String:
	var resource_root := str(_config.get("resource_root", ""))
	if reference.begins_with("res://"):
		return reference
	return resource_root + "/" + reference.trim_prefix("./")
