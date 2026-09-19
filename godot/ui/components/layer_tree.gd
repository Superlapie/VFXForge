class_name VFXLayerTree
extends Tree

signal reorder_requested(layer_id: String, target_index: int)

var track_start_offset: float = 0.0
var row_height: float = 24.0


func _get_drag_data(at_position: Vector2) -> Variant:
	var item := get_item_at_position(at_position)
	if item == null:
		return null
	var layer_id := str(item.get_metadata(0))
	if layer_id.is_empty():
		return null
	set_drop_mode_flags(DROP_MODE_ON_ITEM | DROP_MODE_INBETWEEN)
	return {"layer_id": layer_id}


func _can_drop_data(at_position: Vector2, data: Variant) -> bool:
	return data is Dictionary and not str(data.get("layer_id", "")).is_empty()


func _drop_data(at_position: Vector2, data: Variant) -> void:
	var layer_id := str(data.get("layer_id", ""))
	var target_index := _layer_index_at_position(at_position)
	reorder_requested.emit(layer_id, target_index)


func _layer_index_at_position(position: Vector2) -> int:
	var item := get_item_at_position(position)
	if item == null:
		return 0
	var root := get_root()
	if root == null:
		return 0
	var index := 0
	var child := root.get_first_child()
	while child != null:
		if child == item:
			return max(0, index - 1)
		if not str(child.get_metadata(0)).is_empty():
			index += 1
		child = child.get_next()
	return max(0, index - 1)
