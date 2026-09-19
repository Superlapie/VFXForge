extends SceneTree

const DocumentScript = preload("res://godot/model/vfx_document.gd")


func _fail(message: String) -> void:
    push_error(message)
    quit(5)


func _real_mesh(mesh: Mesh) -> bool:
    if mesh == null or mesh.get_surface_count() <= 0:
        return false
    var arrays: Array = mesh.surface_get_arrays(0)
    if arrays.size() <= Mesh.ARRAY_VERTEX:
        return false
    var vertices: Variant = arrays[Mesh.ARRAY_VERTEX]
    return vertices is PackedVector3Array and vertices.size() >= 3


func _initialize() -> void:
    var scene: PackedScene = load("res://godot/app/Main.tscn")
    if scene == null:
        _fail("The editor scene could not be loaded")
        return
    var main := scene.instantiate()
    root.add_child(main)
    await process_frame
    await process_frame

    main.model = DocumentScript.load_file("res://examples/portal.vfx.json")
    main.source_path = "res://examples/portal.vfx.json"
    main.selected_layer_id = "portal_ring"
    main._refresh_all()
    await process_frame
    await process_frame

    if main.project_title.text != "Portal":
        _fail("GUI did not display the canonical project name")
        return
    if main.timeline == null or main.preview_view == null or main.inspector == null:
        _fail("GUI did not build the preview, timeline, and inspector surfaces")
        return
    if main.content_split.get_child(0).size.x < 600.0 or main.content_split.get_child(1).size.x < 300.0:
        _fail("GUI split layout made the preview or inspector unusably narrow")
        return
    main.preview_view.target = Vector3(3.0, 2.0, 3.0)
    main.preview_view.yaw = 1.4
    main._on_reset_view_pressed()
    if main.camera_menu.selected != 0 or main.preview_view.target != Vector3(0.0, 0.8, 0.0):
        _fail("GUI reset-view control did not restore the canonical preview camera")
        return
    main._on_add_layer_selected(1)
    await process_frame
    var added_layer_id: String = main.selected_layer_id
    if added_layer_id.is_empty() or main.model.get_layer(added_layer_id).is_empty():
        _fail("GUI add-layer action did not select and persist the new canonical layer")
        return
    var spinners: Array[Node] = main.inspector.find_children("*", "SpinBox", true, false)
    if spinners.size() < 3:
        _fail("GUI particle inspector did not expose editable numeric controls")
        return
    var amount_spinner: SpinBox = spinners[2] as SpinBox
    amount_spinner.value = 96.0
    amount_spinner.value_changed.emit(96.0)
    await process_frame
    if int(main.model.get_path("layers." + added_layer_id + ".properties.amount")) != 96:
        _fail("GUI particle amount control did not update the canonical properties object")
        return
    main.undo_redo.undo()
    await process_frame
    if int(main.model.get_path("layers." + added_layer_id + ".properties.amount")) == 96:
        _fail("GUI property edit did not participate in undo history")
        return
    main.undo_redo.redo()
    await process_frame
    if int(main.model.get_path("layers." + added_layer_id + ".properties.amount")) != 96:
        _fail("GUI property edit did not participate in redo history")
        return
    main.selected_layer_id = "portal_ring"
    main._refresh_all()
    await process_frame
    if main.hierarchy.get_root() == null:
        _fail("GUI hierarchy has no root item")
        return
    var first_layer: TreeItem = main.hierarchy.get_root().get_first_child().get_next()
    if first_layer == null or str(first_layer.get_metadata(0)) != "portal_ring":
        _fail("GUI hierarchy did not expose the stable mesh layer ID")
        return
    var mesh_node := main.runtime.get_node_or_null("portal_ring") as MeshInstance3D
    if mesh_node == null or not _real_mesh(mesh_node.mesh):
        _fail("GUI preview runtime did not instantiate the real imported model")
        return

    var inspector_has_mesh_field := false
    for child_variant in main.inspector.find_children("*", "LineEdit", true, false):
        if child_variant is LineEdit and (child_variant as LineEdit).text == "assets/models/forge_totem.obj":
            inspector_has_mesh_field = true
            break
    if not inspector_has_mesh_field:
        _fail("GUI inspector did not expose the canonical mesh asset field")
        return

    main._edit_path("layers.portal_ring.properties.size", [1.35, 1.35, 1.35])
    await process_frame
    if main.model.get_path("layers.portal_ring.properties.size").size() != 3:
        _fail("GUI inspector edit did not update the canonical model")
        return
    main.undo_redo.undo()
    await process_frame
    if JSON.stringify(main.model.get_path("layers.portal_ring.properties.size")) == JSON.stringify([1.35, 1.35, 1.35]):
        _fail("GUI undo did not restore the canonical model")
        return
    main.undo_redo.redo()
    await process_frame
    if JSON.stringify(main.model.get_path("layers.portal_ring.properties.size")) != JSON.stringify([1.35, 1.35, 1.35]):
        _fail("GUI redo did not reapply the canonical model edit")
        return

    main.runtime.seek(1.2)
    if abs(main.runtime.elapsed - 1.2) > 0.01:
        _fail("GUI runtime preview did not seek the canonical timeline")
        return
    var final_mesh_node := main.runtime.get_node_or_null("portal_ring") as MeshInstance3D
    if final_mesh_node == null or not _real_mesh(final_mesh_node.mesh):
        _fail("GUI redo refresh did not rebuild the real imported model")
        return
    var future_model: VFXDocument = DocumentScript.from_dictionary({"schema_version": 99, "id": "future_effect"})
    if int(future_model.data.get("schema_version", 0)) != 99 or future_model.basic_validation().get("errors", []).is_empty() or future_model.basic_validation().get("errors", [])[0].get("code") != "FUTURE_SCHEMA":
        _fail("Godot model silently reinterpreted a future schema")
        return
    print("USER_E2E_GUI_PASS mesh_surfaces=%d" % final_mesh_node.mesh.get_surface_count())
    quit(0)
