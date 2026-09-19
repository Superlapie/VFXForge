extends SceneTree


func _fail(message: String) -> void:
    push_error(message)
    quit(4)


func _real_mesh(mesh: Mesh) -> bool:
    if mesh == null or mesh.get_surface_count() <= 0:
        return false
    var arrays: Array = mesh.surface_get_arrays(0)
    if arrays.size() <= Mesh.ARRAY_VERTEX:
        return false
    var vertices: Variant = arrays[Mesh.ARRAY_VERTEX]
    return vertices is PackedVector3Array and vertices.size() >= 3


func _initialize() -> void:
    var scene: PackedScene = load("res://effect.tscn")
    if scene == null:
        _fail("The exported effect scene could not be loaded")
        return
    var instance: Node = scene.instantiate()
    root.add_child(instance)
    await process_frame
    await process_frame

    var mesh_effect := instance.get_node_or_null("totem") as MeshInstance3D
    if mesh_effect == null or not _real_mesh(mesh_effect.mesh):
        _fail("The exported custom mesh_effect did not produce real mesh geometry")
        return
    var mesh_particles := instance.get_node_or_null("totem_particles") as GPUParticles3D
    if mesh_particles == null or not _real_mesh(mesh_particles.draw_pass_1):
        _fail("The exported custom mesh_particle did not produce real mesh geometry")
        return
    if instance.has_method("seek"):
        instance.call("seek", 0.55)
    await process_frame
    print("USER_E2E_EXPORT_PASS surfaces=%d particle_surfaces=%d" % [mesh_effect.mesh.get_surface_count(), mesh_particles.draw_pass_1.get_surface_count()])
    quit(0)
