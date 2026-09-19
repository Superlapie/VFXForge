class_name VFXEventsWorkspace
extends PanelContainer

signal events_changed(events: Array)
signal event_selected(time: float)
signal edit_requested(path: String, value: Variant)

const Tokens := preload("res://godot/ui/theme/tokens.gd")

var event_list: ItemList
var time_field: SpinBox
var id_field: LineEdit
var _events: Array = []
var _selected_index := -1


func _init() -> void:
	var outer := HBoxContainer.new()
	outer.add_theme_constant_override("separation", Tokens.SPACE_MD)
	add_child(outer)

	var left := VBoxContainer.new()
	left.custom_minimum_size.x = 220
	left.size_flags_vertical = Control.SIZE_EXPAND_FILL
	outer.add_child(left)

	var heading := Label.new()
	heading.text = "Timeline Events"
	heading.add_theme_color_override("font_color", Tokens.TEXT_HEADING)
	left.add_child(heading)

	event_list = ItemList.new()
	event_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	event_list.item_selected.connect(_on_item_selected)
	event_list.item_activated.connect(_on_item_activated)
	left.add_child(event_list)

	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", Tokens.SPACE_SM)
	left.add_child(buttons)
	var add_button := Button.new()
	add_button.text = "+ Add"
	add_button.pressed.connect(_on_add_pressed)
	buttons.add_child(add_button)
	var remove_button := Button.new()
	remove_button.text = "Remove"
	remove_button.pressed.connect(_on_remove_pressed)
	buttons.add_child(remove_button)

	var right := VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right.add_theme_constant_override("separation", Tokens.SPACE_SM)
	outer.add_child(right)

	var detail_heading := Label.new()
	detail_heading.text = "Event Details"
	detail_heading.add_theme_color_override("font_color", Tokens.TEXT_HEADING)
	right.add_child(detail_heading)

	var time_row := HBoxContainer.new()
	time_row.add_theme_constant_override("separation", Tokens.SPACE_SM)
	right.add_child(time_row)
	var time_label := Label.new()
	time_label.text = "Time (s)"
	time_label.custom_minimum_size.x = 72
	time_row.add_child(time_label)
	time_field = SpinBox.new()
	time_field.min_value = 0.0
	time_field.max_value = 3600.0
	time_field.step = 0.01
	time_field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	time_field.value_changed.connect(_commit_selected_event)
	right.add_child(time_field)

	var id_row := HBoxContainer.new()
	id_row.add_theme_constant_override("separation", Tokens.SPACE_SM)
	right.add_child(id_row)
	var id_label := Label.new()
	id_label.text = "Event ID"
	id_label.custom_minimum_size.x = 72
	id_row.add_child(id_label)
	id_field = LineEdit.new()
	id_field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	id_field.text_submitted.connect(func(_text: String) -> void: _commit_selected_event())
	id_field.focus_exited.connect(_commit_selected_event)
	id_row.add_child(id_field)

	var hint := Label.new()
	hint.text = "Events mark gameplay sync points. Double-click an event to scrub the preview."
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
	hint.add_theme_color_override("font_color", Tokens.TEXT_MUTED)
	right.add_child(hint)


func set_document(document: Dictionary) -> void:
	var timeline: Dictionary = document.get("timeline", {})
	_events = timeline.get("events", []).duplicate(true)
	_rebuild_list()


func _rebuild_list() -> void:
	event_list.clear()
	for index in range(_events.size()):
		var event_variant: Variant = _events[index]
		if not event_variant is Dictionary:
			continue
		var event: Dictionary = event_variant
		event_list.add_item("%.2fs  •  %s" % [float(event.get("time", 0.0)), str(event.get("event_id", "event"))])
		event_list.set_item_metadata(index, index)
	if _events.is_empty():
		time_field.set_value_no_signal(0.0)
		id_field.text = ""


func _on_item_selected(index: int) -> void:
	_selected_index = index
	if index < 0 or index >= _events.size():
		return
	var event: Dictionary = _events[index]
	time_field.set_value_no_signal(float(event.get("time", 0.0)))
	id_field.text = str(event.get("event_id", "event"))


func _on_item_activated(index: int) -> void:
	if index < 0 or index >= _events.size():
		return
	var event: Dictionary = _events[index]
	event_selected.emit(float(event.get("time", 0.0)))


func _on_add_pressed() -> void:
	_events.append({"time": 0.0, "event_id": "event", "data": {}})
	_rebuild_list()
	event_list.select(_events.size() - 1)
	_on_item_selected(_events.size() - 1)
	_emit_events()


func _on_remove_pressed() -> void:
	if _selected_index < 0 or _selected_index >= _events.size():
		return
	_events.remove_at(_selected_index)
	_selected_index = -1
	_rebuild_list()
	_emit_events()


func _commit_selected_event(_value: Variant = null) -> void:
	if _selected_index < 0 or _selected_index >= _events.size():
		return
	var event: Dictionary = _events[_selected_index]
	event["time"] = time_field.value
	event["event_id"] = id_field.text
	_events[_selected_index] = event
	_rebuild_list()
	event_list.select(_selected_index)
	_emit_events()


func _emit_events() -> void:
	events_changed.emit(_events.duplicate(true))
