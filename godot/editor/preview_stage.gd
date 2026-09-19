class_name VFXPreviewStage
extends Node3D

signal preset_changed(preset_id: String)

const Tokens := preload("res://godot/ui/theme/tokens.gd")

const PRESET_IDS: Array[String] = [
	"empty",
	"humanoid",
	"ground_target",
	"caster_target",
	"weapon",
	"large_creature",
	"mmo_combat",
]

const PRESET_LABELS: Array[String] = [
	"Empty",
	"Humanoid",
	"Ground Target",
	"Caster → Target",
	"Weapon",
	"Large Creature",
	"MMO Combat",
]

var current_preset: String = "mmo_combat"
var show_grid: bool = true

var _floor: MeshInstance3D
var _grid: MeshInstance3D
var _actors: Node3D
var _target_marker: MeshInstance3D


func _init() -> void:
	name = "PreviewStage"
	_floor = _make_plane(18.0, Color("#141820"), 0.92)
	add_child(_floor)
	_grid = _make_grid(18.0)
	add_child(_grid)
	_actors = Node3D.new()
	_actors.name = "StageActors"
	add_child(_actors)
	apply_preset("mmo_combat")


func apply_preset(preset_id: String) -> void:
	current_preset = preset_id if preset_id in PRESET_IDS else "empty"
	_clear_actors()
	match current_preset:
		"humanoid":
			_add_capsule(Vector3(0.0, 0.85, 0.0), 0.34, 1.7, Color("#2A3140", 0.45))
		"ground_target":
			_add_ground_ring(Vector3.ZERO, 2.0)
			_add_tile_grid_markers(3.0)
		"caster_target":
			_add_capsule(Vector3(-2.5, 0.85, 0.0), 0.34, 1.7, Color("#2A3140", 0.42))
			_add_capsule(Vector3(2.5, 0.85, 0.0), 0.34, 1.7, Color("#2A3140", 0.42))
			_add_ground_ring(Vector3(2.5, 0.01, 0.0), 1.2)
		"weapon":
			_add_capsule(Vector3(0.0, 0.85, 0.0), 0.28, 1.6, Color("#2A3140", 0.38))
			_add_anchor_marker("hand", Vector3(0.45, 1.05, 0.15))
			_add_anchor_marker("blade", Vector3(0.95, 1.15, 0.55))
			_add_anchor_marker("tip", Vector3(1.35, 1.05, 1.05))
		"large_creature":
			_add_capsule(Vector3(0.0, 1.35, 0.0), 0.75, 2.7, Color("#2A3140", 0.38))
		"mmo_combat":
			_add_capsule(Vector3(-1.2, 0.85, 0.8), 0.34, 1.7, Color("#2A3140", 0.38))
			_add_ground_ring(Vector3(0.0, 0.01, -1.5), 2.5, Color("#3A4558", 0.35))
		_:
			pass
	preset_changed.emit(current_preset)


func set_grid_visible(visible: bool) -> void:
	show_grid = visible
	if is_instance_valid(_grid):
		_grid.visible = visible


func get_mmo_camera_target() -> Vector3:
	match current_preset:
		"caster_target":
			return Vector3(0.0, 0.9, 0.0)
		"ground_target":
			return Vector3(0.0, 0.2, 0.0)
		"weapon":
			return Vector3(0.6, 1.0, 0.5)
		"large_creature":
			return Vector3(0.0, 1.2, 0.0)
		"mmo_combat":
			return Vector3(0.0, 0.75, -0.4)
		_:
			return Vector3(0.0, 0.8, 0.0)


func _clear_actors() -> void:
	for child in _actors.get_children():
		child.queue_free()


func _make_plane(size: float, color: Color, roughness: float) -> MeshInstance3D:
	var floor := MeshInstance3D.new()
	floor.name = "StageFloor"
	var plane := PlaneMesh.new()
	plane.size = Vector2(size, size)
	floor.mesh = plane
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = roughness
	floor.material_override = material
	return floor


func _make_grid(size: float) -> MeshInstance3D:
	var grid := MeshInstance3D.new()
	grid.name = "StageGrid"
	var plane := PlaneMesh.new()
	plane.size = Vector2(size, size)
	grid.mesh = plane
	grid.position.y = 0.006
	var material := StandardMaterial3D.new()
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color = Color(0.24, 0.28, 0.36, 0.12)
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	grid.material_override = material
	return grid


func _add_capsule(position: Vector3, radius: float, height: float, color: Color) -> void:
	var body := MeshInstance3D.new()
	var capsule := CapsuleMesh.new()
	capsule.radius = radius
	capsule.height = height
	body.mesh = capsule
	body.position = position
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	body.material_override = material
	_actors.add_child(body)


func _add_ground_ring(center: Vector3, radius: float, color: Color = Color("#4A7FD4", 0.28)) -> void:
	var ring := MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = radius * 0.92
	torus.outer_radius = radius
	ring.mesh = torus
	ring.position = center
	ring.rotation_degrees.x = 90.0
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ring.material_override = material
	_actors.add_child(ring)


func _add_tile_grid_markers(span: float) -> void:
	for offset in [-span, 0.0, span]:
		var marker := MeshInstance3D.new()
		var plane := PlaneMesh.new()
		plane.size = Vector2(span, span)
		marker.mesh = plane
		marker.position = Vector3(offset, 0.005, offset)
		var material := StandardMaterial3D.new()
		material.albedo_color = Color("#5C6370", 0.08)
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		marker.material_override = material
		_actors.add_child(marker)


func _add_anchor_marker(anchor_name: String, position: Vector3) -> void:
	var marker := MeshInstance3D.new()
	marker.name = anchor_name
	var sphere := SphereMesh.new()
	sphere.radius = 0.05
	sphere.height = 0.1
	marker.mesh = sphere
	marker.position = position
	var material := StandardMaterial3D.new()
	material.albedo_color = Tokens.ACCENT_CYAN
	material.emission_enabled = true
	material.emission = Tokens.ACCENT_CYAN
	material.emission_energy_multiplier = 1.2
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	marker.material_override = material
	_actors.add_child(marker)
