class_name VFXCollapsibleSection
extends VBoxContainer

const SectionHeaderScript := preload("res://godot/ui/components/section_header.gd")
const Tokens := preload("res://godot/ui/theme/tokens.gd")

var body: VBoxContainer
var header: VFXSectionHeader


func _init(title: String, starts_open: bool = true) -> void:
	add_theme_constant_override("separation", Tokens.SPACE_XS)
	header = SectionHeaderScript.new(title, starts_open)
	add_child(header)
	body = VBoxContainer.new()
	body.add_theme_constant_override("separation", Tokens.SPACE_XS)
	body.visible = starts_open
	add_child(body)
	header.open_changed.connect(func(open: bool) -> void: body.visible = open)


func add_row(node: Control) -> void:
	body.add_child(node)
