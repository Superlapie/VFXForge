extends Control

const VFXDocumentScript = preload("res://godot/model/vfx_document.gd")
const TimelineScript = preload("res://godot/editor/timeline_view.gd")
const CurveEditorScript = preload("res://godot/editor/curve_editor.gd")
const GradientEditorScript = preload("res://godot/editor/gradient_editor.gd")
const PreviewViewScript = preload("res://godot/editor/preview_view.gd")

var model: VFXDocument
var runtime: VFXRuntime
var undo_redo := UndoRedo.new()
var source_path: String = ""
var selected_layer_id: String = ""
var playing: bool = false

var hierarchy: Tree
var inspector: VBoxContainer
var inspector_scroll: ScrollContainer
var timeline: VFXTimelineView
var viewport_container: SubViewportContainer
var preview_view: VFXPreviewView
var preview_viewport: SubViewport
var preview_camera: Camera3D
var preview_environment: WorldEnvironment
var metrics_label: Label
var status_label: Label
var project_title: Label
var dirty_label: Label
var playback_time_label: Label
var playback_slider: HSlider
var camera_menu: OptionButton
var background_menu: OptionButton
var speed_menu: OptionButton
var file_dialog: FileDialog
var autosave_timer: Timer
var inspector_title: Label
var performance_label: Label
var curve_editor: VFXCurveEditor
var gradient_editor: VFXGradientEditor
var hierarchy_menu: PopupMenu
var main_split: HSplitContainer
var content_split: HSplitContainer


func _ready() -> void:
    _build_theme()
    _build_interface()
    _build_preview()
    _connect_input()
    _load_startup_document()


func _exit_tree() -> void:
    if is_instance_valid(undo_redo):
        undo_redo.free()


func _build_theme() -> void:
    var theme := Theme.new()
    theme.default_font_size = 13
    theme.set_color("font_color", "Label", Color("#CBD7E8"))
    theme.set_color("font_color", "Button", Color("#DCE7F7"))
    theme.set_color("font_hover_color", "Button", Color.WHITE)
    theme.set_color("font_pressed_color", "Button", Color.WHITE)
    theme.set_color("font_color", "LineEdit", Color("#E8F0FF"))
    theme.set_color("caret_color", "LineEdit", Color("#8CD9FF"))
    theme.set_color("font_color", "Tree", Color("#CBD7E8"))
    theme.set_color("font_selected_color", "Tree", Color.WHITE)
    theme.set_color("font_hover_color", "Tree", Color.WHITE)
    theme.set_color("selection_color", "Tree", Color("#324B74"))
    theme.set_color("font_color", "SpinBox", Color("#E8F0FF"))
    theme.set_color("font_color", "OptionButton", Color("#E8F0FF"))
    theme.set_stylebox("normal", "Button", _style("#18263D", "#314766", 6))
    theme.set_stylebox("hover", "Button", _style("#243A5A", "#5B83B6", 6))
    theme.set_stylebox("pressed", "Button", _style("#355887", "#8CD9FF", 6))
    theme.set_stylebox("normal", "LineEdit", _style("#0C1627", "#2A3D5A", 5))
    theme.set_stylebox("focus", "LineEdit", _style("#0C1627", "#6EA5D8", 5))
    theme.set_stylebox("normal", "OptionButton", _style("#18263D", "#314766", 6))
    theme.set_stylebox("hover", "OptionButton", _style("#243A5A", "#5B83B6", 6))
    theme.set_stylebox("panel", "PanelContainer", _style("#0E1728", "#263851", 0))
    theme.set_stylebox("panel", "Panel", _style("#0E1728", "#263851", 0))
    theme.set_stylebox("read_only", "LineEdit", _style("#0C1627", "#22344E", 5))
    self.theme = theme


func _style(fill: String, border: String, radius: int) -> StyleBoxFlat:
    var style := StyleBoxFlat.new()
    style.bg_color = Color(fill)
    style.border_color = Color(border)
    style.border_width_left = 1
    style.border_width_right = 1
    style.border_width_top = 1
    style.border_width_bottom = 1
    style.corner_radius_top_left = radius
    style.corner_radius_top_right = radius
    style.corner_radius_bottom_left = radius
    style.corner_radius_bottom_right = radius
    style.content_margin_left = 8
    style.content_margin_right = 8
    style.content_margin_top = 5
    style.content_margin_bottom = 5
    return style


func _build_interface() -> void:
    var background := ColorRect.new()
    background.color = Color("#080E19")
    background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    add_child(background)

    var root := VBoxContainer.new()
    root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    root.add_theme_constant_override("separation", 0)
    add_child(root)

    root.add_child(_build_toolbar())
    main_split = HSplitContainer.new()
    main_split.name = "MainSplit"
    main_split.size_flags_vertical = Control.SIZE_EXPAND_FILL
    root.add_child(main_split)
    main_split.add_child(_build_hierarchy())
    content_split = HSplitContainer.new()
    content_split.name = "ContentSplit"
    content_split.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    content_split.add_child(_build_center())
    content_split.add_child(_build_inspector())
    main_split.add_child(content_split)
    root.add_child(_build_timeline_panel())

    file_dialog = FileDialog.new()
    file_dialog.access = FileDialog.ACCESS_FILESYSTEM
    file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
    file_dialog.filters = PackedStringArray(["*.vfx.json ; VFX Forge documents", "*.json ; JSON documents"])
    file_dialog.file_selected.connect(_on_file_selected)
    add_child(file_dialog)

    autosave_timer = Timer.new()
    autosave_timer.wait_time = 30.0
    autosave_timer.autostart = true
    autosave_timer.timeout.connect(_on_autosave)
    add_child(autosave_timer)
    call_deferred("_configure_split_layout")


func _configure_split_layout() -> void:
    if not is_instance_valid(main_split) or not is_instance_valid(content_split):
        return
    await get_tree().process_frame
    main_split.split_offset = 260
    content_split.split_offsets = PackedInt32Array([175])
    await get_tree().process_frame
    main_split.split_offset = 260
    # Keep a readable inspector at the 1440px reference viewport while still
    # allowing the center preview to grow on wider displays.
    content_split.split_offsets = PackedInt32Array([175])


func _build_toolbar() -> Control:
    var panel := PanelContainer.new()
    panel.custom_minimum_size.y = 58
    var bar := HBoxContainer.new()
    bar.add_theme_constant_override("separation", 6)
    bar.add_theme_constant_override("margin_left", 12)
    bar.add_theme_constant_override("margin_right", 12)
    bar.add_theme_constant_override("margin_top", 8)
    bar.add_theme_constant_override("margin_bottom", 8)
    panel.add_child(bar)

    var brand := Label.new()
    brand.text = "VFX FORGE"
    brand.add_theme_font_size_override("font_size", 18)
    brand.add_theme_color_override("font_color", Color("#F2C76B"))
    bar.add_child(brand)
    var badge := Label.new()
    badge.text = "  AI-FIRST / GODOT 4.x  "
    badge.add_theme_color_override("font_color", Color("#8CD9FF"))
    bar.add_child(badge)
    bar.add_child(_separator())
    bar.add_child(_toolbar_button("Open", _on_open_pressed))
    bar.add_child(_toolbar_button("Save", _on_save_pressed))
    bar.add_child(_toolbar_button("Undo", func() -> void: undo_redo.undo()))
    bar.add_child(_toolbar_button("Redo", func() -> void: undo_redo.redo()))
    bar.add_child(_separator())
    var add_menu := OptionButton.new()
    add_menu.name = "AddLayerMenu"
    add_menu.custom_minimum_size.x = 122
    add_menu.add_item("Add layer")
    for layer_type in ["particle", "mesh_particle", "sprite", "light", "trail", "beam", "decal", "mesh_effect", "event_marker", "child_effect"]:
        add_menu.add_item("+ " + layer_type)
    add_menu.item_selected.connect(_on_add_layer_selected)
    bar.add_child(add_menu)
    bar.add_child(_separator())
    bar.add_child(_toolbar_button("Play", _on_play_pressed))
    bar.add_child(_toolbar_button("Pause", _on_pause_pressed))
    bar.add_child(_toolbar_button("Stop", _on_stop_pressed))
    speed_menu = OptionButton.new()
    speed_menu.add_item("0.25x")
    speed_menu.add_item("0.5x")
    speed_menu.add_item("1.0x")
    speed_menu.add_item("2.0x")
    speed_menu.selected = 2
    speed_menu.item_selected.connect(func(index: int) -> void:
        runtime.playback_speed = [0.25, 0.5, 1.0, 2.0][index]
    )
    bar.add_child(speed_menu)
    bar.add_child(_separator())
    var camera_label := Label.new()
    camera_label.text = "Camera"
    bar.add_child(camera_label)
    camera_menu = OptionButton.new()
    for camera_name in ["mmo", "front", "side", "top"]:
        camera_menu.add_item(camera_name)
    camera_menu.selected = 0
    camera_menu.item_selected.connect(_on_camera_selected)
    bar.add_child(camera_menu)
    var reset_view := _toolbar_button("Reset view", _on_reset_view_pressed)
    reset_view.tooltip_text = "Reset the preview camera to the MMO view"
    bar.add_child(reset_view)
    var background_label := Label.new()
    background_label.text = "Stage"
    bar.add_child(background_label)
    background_menu = OptionButton.new()
    for stage in ["dark", "light", "night", "checker"]:
        background_menu.add_item(stage)
    background_menu.item_selected.connect(_on_background_selected)
    bar.add_child(background_menu)
    project_title = Label.new()
    project_title.text = "Untitled Effect"
    project_title.custom_minimum_size.x = 108
    project_title.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
    project_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
    project_title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
    project_title.add_theme_color_override("font_color", Color("#E7EEF9"))
    bar.add_child(project_title)
    dirty_label = Label.new()
    dirty_label.text = "  SAVED  "
    dirty_label.custom_minimum_size.x = 68
    dirty_label.add_theme_color_override("font_color", Color("#73D29B"))
    bar.add_child(dirty_label)
    status_label = Label.new()
    status_label.text = "Ready"
    status_label.custom_minimum_size.x = 170
    status_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
    status_label.add_theme_color_override("font_color", Color("#63748E"))
    status_label.add_theme_font_size_override("font_size", 11)
    return panel


func _build_hierarchy() -> Control:
    var panel := PanelContainer.new()
    panel.custom_minimum_size.x = 230
    var outer := VBoxContainer.new()
    outer.add_theme_constant_override("separation", 8)
    panel.add_child(outer)
    var heading := Label.new()
    heading.text = "  EFFECT HIERARCHY"
    heading.add_theme_font_size_override("font_size", 11)
    heading.add_theme_color_override("font_color", Color("#8494AE"))
    outer.add_child(heading)
    hierarchy = Tree.new()
    hierarchy.name = "Hierarchy"
    hierarchy.hide_root = true
    hierarchy.size_flags_vertical = Control.SIZE_EXPAND_FILL
    hierarchy.columns = 2
    hierarchy.set_column_expand(0, true)
    hierarchy.set_column_expand(1, false)
    hierarchy.set_column_custom_minimum_width(1, 72)
    hierarchy.item_selected.connect(_on_hierarchy_selected)
    hierarchy.gui_input.connect(_on_hierarchy_gui_input)
    outer.add_child(hierarchy)
    var hint := Label.new()
    hint.text = "Click a layer to inspect\nRight-click a layer for actions"
    hint.add_theme_color_override("font_color", Color("#63748E"))
    hint.add_theme_font_size_override("font_size", 11)
    outer.add_child(hint)
    hierarchy_menu = PopupMenu.new()
    hierarchy_menu.add_item("Duplicate layer", 1)
    hierarchy_menu.add_item("Remove layer", 2)
    hierarchy_menu.id_pressed.connect(_on_hierarchy_menu_pressed)
    add_child(hierarchy_menu)
    return panel


func _build_center() -> Control:
    var panel := PanelContainer.new()
    panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    var outer := VBoxContainer.new()
    outer.add_theme_constant_override("separation", 0)
    panel.add_child(outer)
    var header := HBoxContainer.new()
    header.custom_minimum_size.y = 34
    var title := Label.new()
    title.text = "  REAL-TIME PREVIEW"
    title.add_theme_font_size_override("font_size", 11)
    title.add_theme_color_override("font_color", Color("#8494AE"))
    header.add_child(title)
    var helper := Label.new()
    helper.text = "  orbit: drag   pan: middle drag   zoom: wheel"
    helper.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    helper.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
    helper.add_theme_color_override("font_color", Color("#63748E"))
    helper.add_theme_font_size_override("font_size", 11)
    header.add_child(helper)
    outer.add_child(header)
    preview_view = PreviewViewScript.new()
    viewport_container = preview_view
    viewport_container.stretch = true
    viewport_container.size_flags_vertical = Control.SIZE_EXPAND_FILL
    viewport_container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    outer.add_child(viewport_container)
    var overlay := HBoxContainer.new()
    overlay.custom_minimum_size.y = 34
    metrics_label = Label.new()
    metrics_label.text = "No document loaded"
    metrics_label.size_flags_horizontal = Control.SIZE_FILL
    metrics_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
    metrics_label.add_theme_color_override("font_color", Color("#9CAEC9"))
    overlay.add_child(metrics_label)
    overlay.add_child(status_label)
    playback_time_label = Label.new()
    playback_time_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    playback_time_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
    playback_time_label.add_theme_color_override("font_color", Color("#F6C760"))
    overlay.add_child(playback_time_label)
    outer.add_child(overlay)
    return panel


func _build_inspector() -> Control:
    var panel := PanelContainer.new()
    panel.custom_minimum_size.x = 330
    panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    inspector_scroll = ScrollContainer.new()
    inspector_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
    inspector_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    panel.add_child(inspector_scroll)
    inspector = VBoxContainer.new()
    inspector.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    inspector.add_theme_constant_override("separation", 8)
    inspector_scroll.add_child(inspector)
    inspector_title = Label.new()
    inspector_title.text = "INSPECTOR"
    inspector_title.add_theme_font_size_override("font_size", 11)
    inspector_title.add_theme_color_override("font_color", Color("#8494AE"))
    inspector.add_child(inspector_title)
    return panel


func _build_timeline_panel() -> Control:
    var panel := PanelContainer.new()
    panel.custom_minimum_size.y = 190
    timeline = TimelineScript.new()
    timeline.size_flags_vertical = Control.SIZE_EXPAND_FILL
    timeline.scrubbed.connect(_on_scrubbed)
    timeline.layer_timing_changed.connect(_on_layer_timing_changed)
    panel.add_child(timeline)
    return panel


func _build_preview() -> void:
    preview_viewport = SubViewport.new()
    preview_viewport.name = "PreviewViewport"
    preview_viewport.size = Vector2i(900, 580)
    preview_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    preview_viewport.transparent_bg = false
    viewport_container.add_child(preview_viewport)
    var world := Node3D.new()
    world.name = "PreviewWorld"
    preview_viewport.add_child(world)
    preview_environment = WorldEnvironment.new()
    var environment := Environment.new()
    environment.background_mode = Environment.BG_COLOR
    environment.background_color = Color("#0B1220")
    environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    environment.ambient_light_color = Color("#5D6C8A")
    environment.ambient_light_energy = 0.6
    environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
    preview_environment.environment = environment
    world.add_child(preview_environment)
    preview_camera = Camera3D.new()
    preview_camera.current = true
    preview_camera.fov = 50.0
    world.add_child(preview_camera)
    preview_view.set_camera(preview_camera)
    _set_camera("mmo")
    var key_light := DirectionalLight3D.new()
    key_light.rotation_degrees = Vector3(-52, -28, 0)
    key_light.light_energy = 1.2
    key_light.light_color = Color("#C4D5FF")
    world.add_child(key_light)
    var floor := MeshInstance3D.new()
    var plane := PlaneMesh.new()
    plane.size = Vector2(14, 14)
    floor.mesh = plane
    var floor_material := StandardMaterial3D.new()
    floor_material.albedo_color = Color("#121C2C")
    floor_material.roughness = 0.92
    floor.material_override = floor_material
    world.add_child(floor)
    var grid := MeshInstance3D.new()
    var grid_mesh := PlaneMesh.new()
    grid_mesh.size = Vector2(14, 14)
    grid.mesh = grid_mesh
    grid.rotation_degrees.x = 0.0
    var grid_material := StandardMaterial3D.new()
    grid_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
    grid_material.albedo_color = Color(0.2, 0.28, 0.42, 0.08)
    grid.material_override = grid_material
    grid.position.y = 0.006
    world.add_child(grid)
    var dummy := MeshInstance3D.new()
    dummy.name = "ScaleDummy"
    var capsule := CapsuleMesh.new()
    capsule.radius = 0.34
    capsule.height = 1.7
    dummy.mesh = capsule
    dummy.position.y = 0.85
    var dummy_material := StandardMaterial3D.new()
    dummy_material.albedo_color = Color("#2A3850")
    dummy_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
    dummy_material.albedo_color.a = 0.42
    dummy.material_override = dummy_material
    world.add_child(dummy)
    runtime = VFXRuntime.new()
    runtime.name = "PreviewRuntime"
    runtime.time_changed.connect(_on_runtime_time)
    runtime.runtime_warning.connect(_on_runtime_warning)
    preview_viewport.add_child(runtime)


func _connect_input() -> void:
    if not InputMap.has_action("save_project"):
        InputMap.add_action("save_project")


func _load_startup_document() -> void:
    var requested := ""
    var recovered := false
    var arguments := OS.get_cmdline_args()
    for argument in arguments:
        if argument.ends_with(".vfx.json"):
            requested = argument
    if requested.is_empty() and FileAccess.file_exists("res://examples/arcane_impact.vfx.json"):
        requested = "res://examples/arcane_impact.vfx.json"
    if requested.is_empty():
        model = VFXDocumentScript.create("untitled_effect", "Untitled Effect")
    else:
        var recovery_path := requested + ".autosave"
        if FileAccess.file_exists(recovery_path) and FileAccess.get_modified_time(recovery_path) > FileAccess.get_modified_time(requested):
            model = VFXDocumentScript.load_file(recovery_path)
            model.source_path = requested
            model.is_dirty = true
            recovered = true
        else:
            model = VFXDocumentScript.load_file(requested)
        source_path = requested
    model.changed.connect(_on_model_changed)
    model.dirty_changed.connect(_on_dirty_changed)
    _refresh_all()
    if not model.load_error.is_empty():
        status_label.text = str(model.load_error.get("code", "LOAD_ERROR")) + ": " + str(model.load_error.get("message", "Could not load document."))
        status_label.add_theme_color_override("font_color", Color("#F6C760"))
    elif recovered:
        status_label.text = "Recovered newer autosave; review before saving"


func _refresh_all() -> void:
    if model == null:
        return
    project_title.text = str(model.data.get("name", "Untitled Effect"))
    _refresh_hierarchy()
    _refresh_inspector()
    _refresh_runtime()
    timeline.set_document(model.data)
    _update_metrics()


func _refresh_hierarchy() -> void:
    hierarchy.clear()
    var root := hierarchy.create_item()
    var effect_item := hierarchy.create_item(root)
    effect_item.set_text(0, str(model.data.get("name", "Effect")))
    effect_item.set_text(1, "EFFECT")
    effect_item.set_metadata(0, "")
    for layer_variant in model.data.get("layers", []):
        if not layer_variant is Dictionary:
            continue
        var layer: Dictionary = layer_variant
        var item := hierarchy.create_item(root)
        item.set_text(0, str(layer.get("name", layer.get("id", "Layer"))))
        item.set_text(1, str(layer.get("type", "")).to_upper())
        item.set_metadata(0, str(layer.get("id", "")))
        item.set_tooltip_text(0, str(layer.get("id", "")) + "  •  " + str(layer.get("type", "")))
        if not bool(layer.get("enabled", true)):
            item.set_custom_color(0, Color("#69778C"))
    if not selected_layer_id.is_empty():
        _select_tree_layer(selected_layer_id)


func _select_tree_layer(layer_id: String) -> void:
    var root := hierarchy.get_root()
    if root == null:
        return
    var item := root.get_first_child()
    while item != null:
        var child := item.get_first_child()
        while child != null:
            if str(child.get_metadata(0)) == layer_id:
                child.select(0)
                return
            child = child.get_next()
        item = item.get_next()


func _refresh_inspector() -> void:
    performance_label = null
    for child in inspector.get_children():
        if child != inspector_title:
            child.queue_free()
    var selected := model.get_layer(selected_layer_id) if not selected_layer_id.is_empty() else {}
    if selected.is_empty():
        _build_document_inspector()
    else:
        _build_layer_inspector(selected)


func _build_document_inspector() -> void:
    inspector_title.text = "EFFECT SETTINGS"
    _add_help("Canonical document • saved as JSON • stable seed drives deterministic preview")
    _add_text_field("Display name", "name", str(model.data.get("name", "")))
    _add_number_field("Duration (seconds)", "duration", float(model.data.get("duration", 1.0)), 0.01, 3600.0, 0.01)
    _add_number_field("Deterministic seed", "seed", float(model.data.get("seed", 12345)), -2147483648.0, 2147483647.0, 1.0)
    var loop := CheckButton.new()
    loop.text = "Loop preview"
    loop.button_pressed = bool(model.data.get("loop", false))
    loop.toggled.connect(func(value: bool) -> void: _edit_path("loop", value))
    inspector.add_child(loop)
    _add_metric_card()


func _build_layer_inspector(layer: Dictionary) -> void:
    inspector_title.text = "LAYER  /  " + str(layer.get("type", "")).to_upper()
    var subtitle := Label.new()
    subtitle.text = str(layer.get("id", "")) + "  •  stable ID"
    subtitle.add_theme_color_override("font_color", Color("#8CD9FF"))
    inspector.add_child(subtitle)
    _add_text_field("Layer name", "name", str(layer.get("name", "")), true)
    var enabled := CheckButton.new()
    enabled.text = "Enabled"
    enabled.button_pressed = bool(layer.get("enabled", true))
    enabled.toggled.connect(func(value: bool) -> void: _edit_path("layers." + str(layer.get("id")) + ".enabled", value))
    inspector.add_child(enabled)
    _add_number_field("Start (seconds)", "start", float(layer.get("start", 0.0)), 0.0, 3600.0, 0.01, true, layer)
    _add_number_field("Duration (seconds)", "duration", float(layer.get("duration", 1.0)), 0.01, 3600.0, 0.01, true, layer)
    _add_section("Runtime properties")
    var layer_id := str(layer.get("id", ""))
    var properties: Dictionary = layer.get("properties", {})
    match str(layer.get("type", "")):
        "particle", "mesh_particle":
            _add_number_field("Amount", "amount", float(properties.get("amount", 32)), 0.0, 200000.0, 1.0, true, layer)
            _add_number_field("Lifetime", "lifetime", float(properties.get("lifetime", 0.8)), 0.01, 3600.0, 0.01, true, layer)
            _add_number_field("Initial velocity", "initial_velocity_min", float(properties.get("initial_velocity_min", properties.get("initial_velocity", 1.0))), 0.0, 100.0, 0.05, true, layer)
            _add_option_field("Emission shape", "emission_shape", ["point", "box", "sphere", "sphere_surface", "ring", "disc", "line", "cone"], str(properties.get("emission_shape", "point")), layer)
            _add_vector_field("Gravity", "gravity", properties.get("gravity", [0.0, -2.0, 0.0]), layer)
        "light":
            _add_number_field("Energy", "energy", float(properties.get("energy", 1.0)), 0.0, 100.0, 0.1, true, layer)
            _add_number_field("Range", "range", float(properties.get("range", 3.0)), 0.1, 100.0, 0.1, true, layer)
            _add_color_field("Color", "color", Color.from_string(str(properties.get("color", "#8A7CFFFF")), Color.WHITE), layer)
        "sprite", "decal", "mesh_effect":
            _add_vector_field("Size", "size", properties.get("size", [1.0, 1.0, 1.0] if layer.get("type") == "mesh_effect" else [1.0, 1.0]), layer)
            _add_color_field("Color", "color", Color.from_string(str(properties.get("color", "#8A7CFFFF")), Color.WHITE), layer)
        "trail":
            _add_number_field("Width", "width", float(properties.get("width", 0.18)), 0.01, 10.0, 0.01, true, layer)
            _add_number_field("Trail lifetime", "lifetime", float(properties.get("lifetime", 0.35)), 0.02, 10.0, 0.01, true, layer)
            _add_color_field("Color", "color", Color.from_string(str(properties.get("color", "#9C8CFFFF")), Color.WHITE), layer)
        "beam":
            _add_number_field("Thickness", "thickness", float(properties.get("thickness", 0.12)), 0.01, 10.0, 0.01, true, layer)
            _add_number_field("Noise", "noise", float(properties.get("noise", 0.08)), 0.0, 10.0, 0.01, true, layer)
            _add_vector_field("Target", "target", properties.get("target", [0.0, 0.0, -4.0]), layer)
        "audio_marker", "event_marker":
            _add_text_field("Event ID", "event_id", str(properties.get("event_id", "impact")), true, layer)
        "child_effect":
            _add_text_field("Effect reference", "effect_id", str(properties.get("effect_id", "")), true, layer)
    if str(layer.get("type", "")) in ["mesh_particle", "mesh_effect"]:
        _add_text_field("Mesh asset (.obj/.glb)", "mesh_asset", str(properties.get("mesh_asset", "")), true, layer)
    _add_section("Material")
    _add_option_field("Blend mode", "blend_mode", ["additive", "alpha", "premultiplied", "multiply"], str(layer.get("material", {}).get("blend_mode", "additive")), layer, true)
    _add_number_field("Emissive intensity", "emissive_intensity", float(layer.get("material", {}).get("emissive_intensity", 1.0)), 0.0, 100.0, 0.1, true, layer, true)
    _add_section("Scale / alpha curve")
    curve_editor = CurveEditorScript.new()
    curve_editor.set_curve(layer.get("curves", {}).get("scale", {}))
    curve_editor.curve_changed.connect(func(value: Dictionary) -> void: _edit_path("layers." + layer_id + ".curves.scale", value))
    inspector.add_child(curve_editor)
    _add_json_field("Curve points (numeric)", "layers." + layer_id + ".curves.scale", JSON.stringify(layer.get("curves", {}).get("scale", {})), 4)
    _add_section("Color gradient")
    gradient_editor = GradientEditorScript.new()
    gradient_editor.set_gradient(layer.get("gradient", []))
    gradient_editor.gradient_changed.connect(func(value: Array) -> void: _edit_path("layers." + layer_id + ".gradient", value))
    inspector.add_child(gradient_editor)
    var gradient_color := ColorPickerButton.new()
    gradient_color.text = "Edit selected stop color"
    gradient_color.color = Color.WHITE
    gradient_editor.stop_selected.connect(func(_index: int, color: Color) -> void: gradient_color.color = color)
    gradient_color.color_changed.connect(func(color: Color) -> void: gradient_editor.set_selected_color(color))
    inspector.add_child(gradient_color)
    _add_json_field("Gradient stops (numeric)", "layers." + layer_id + ".gradient", JSON.stringify(layer.get("gradient", [])), 4)


func _add_metric_card() -> void:
    var card := PanelContainer.new()
    card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    var label := Label.new()
    performance_label = label
    label.text = "PERFORMANCE\n" + metrics_label.text
    label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    label.custom_minimum_size.y = 64
    label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    label.add_theme_color_override("font_color", Color("#9CAEC9"))
    card.add_child(label)
    inspector.add_child(card)


func _add_help(text: String) -> void:
    var label := Label.new()
    label.text = text
    label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    label.add_theme_color_override("font_color", Color("#71829D"))
    label.add_theme_font_size_override("font_size", 11)
    inspector.add_child(label)


func _add_section(text: String) -> void:
    var label := Label.new()
    label.text = text.to_upper()
    label.add_theme_color_override("font_color", Color("#8494AE"))
    label.add_theme_font_size_override("font_size", 11)
    inspector.add_child(label)


func _add_text_field(label_text: String, path: String, value: String, is_layer: bool = false, layer: Dictionary = {}) -> void:
    var row := HBoxContainer.new()
    var label := Label.new()
    label.text = label_text
    label.custom_minimum_size.x = 118
    row.add_child(label)
    var field := LineEdit.new()
    field.text = value
    field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    var full_path := path
    if is_layer:
        full_path = "layers." + str(layer.get("id", "")) + "." + path
    field.text_submitted.connect(func(text: String) -> void: _edit_path(full_path, text))
    field.focus_exited.connect(func() -> void: _edit_path(full_path, field.text))
    row.add_child(field)
    inspector.add_child(row)


func _add_number_field(label_text: String, path: String, value: float, minimum: float, maximum: float, step: float, is_layer: bool = false, layer: Dictionary = {}, material: bool = false) -> void:
    var row := HBoxContainer.new()
    var label := Label.new()
    label.text = label_text
    label.custom_minimum_size.x = 118
    row.add_child(label)
    var spin := SpinBox.new()
    spin.min_value = minimum
    spin.max_value = maximum
    spin.step = step
    spin.value = value
    spin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    var full_path := path
    if is_layer:
        full_path = "layers." + str(layer.get("id", "")) + "." + ("material." + path if material else path)
    spin.value_changed.connect(func(next_value: float) -> void: _edit_path(full_path, next_value))
    row.add_child(spin)
    inspector.add_child(row)


func _add_option_field(label_text: String, path: String, options: Array[String], value: String, layer: Dictionary = {}, material: bool = false) -> void:
    var row := HBoxContainer.new()
    var label := Label.new()
    label.text = label_text
    label.custom_minimum_size.x = 118
    row.add_child(label)
    var option := OptionButton.new()
    for item in options:
        option.add_item(item)
    option.select(max(0, options.find(value)))
    option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    var full_path := "layers." + str(layer.get("id", "")) + "." + ("material." + path if material else path)
    option.item_selected.connect(func(index: int) -> void: _edit_path(full_path, options[index]))
    row.add_child(option)
    inspector.add_child(row)


func _add_vector_field(label_text: String, path: String, value: Variant, layer: Dictionary) -> void:
    var row := HBoxContainer.new()
    var label := Label.new()
    label.text = label_text
    label.custom_minimum_size.x = 118
    row.add_child(label)
    var field := LineEdit.new()
    field.text = JSON.stringify(value)
    field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    var full_path := "layers." + str(layer.get("id", "")) + "." + path
    field.text_submitted.connect(func(text: String) -> void:
        var parsed: Variant = JSON.parse_string(text)
        if parsed is Array:
            _edit_path(full_path, parsed)
    )
    field.focus_exited.connect(func() -> void:
        var parsed: Variant = JSON.parse_string(field.text)
        if parsed is Array:
            _edit_path(full_path, parsed)
    )
    row.add_child(field)
    inspector.add_child(row)


func _add_color_field(label_text: String, path: String, value: Color, layer: Dictionary) -> void:
    var row := HBoxContainer.new()
    var label := Label.new()
    label.text = label_text
    label.custom_minimum_size.x = 118
    row.add_child(label)
    var picker := ColorPickerButton.new()
    picker.color = value
    picker.custom_minimum_size.x = 80
    var full_path := "layers." + str(layer.get("id", "")) + ".properties." + path
    picker.color_changed.connect(func(next_color: Color) -> void: _edit_path(full_path, next_color.to_html(true)))
    row.add_child(picker)
    inspector.add_child(row)


func _add_json_field(label_text: String, path: String, value: String, lines: int) -> void:
    var label := Label.new()
    label.text = label_text
    label.add_theme_color_override("font_color", Color("#8B9CB6"))
    inspector.add_child(label)
    var field := TextEdit.new()
    field.text = value
    field.custom_minimum_size.y = float(lines * 18)
    field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    field.text_changed.connect(func() -> void:
        var parsed: Variant = JSON.parse_string(field.text)
        if parsed != null:
            _edit_path(path, parsed)
    )
    inspector.add_child(field)


func _toolbar_button(text: String, callback: Callable) -> Button:
    var button := Button.new()
    button.text = text
    button.tooltip_text = text
    button.focus_mode = Control.FOCUS_ALL
    button.pressed.connect(callback)
    return button


func _separator() -> Control:
    var separator := VSeparator.new()
    separator.custom_minimum_size.x = 6
    return separator


func _on_hierarchy_selected() -> void:
    var item := hierarchy.get_selected()
    if item == null:
        return
    selected_layer_id = str(item.get_metadata(0))
    _refresh_inspector()


func _on_hierarchy_gui_input(event: InputEvent) -> void:
    if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
        var item := hierarchy.get_item_at_position(event.position)
        if item != null:
            item.select(0)
            selected_layer_id = str(item.get_metadata(0))
            if not selected_layer_id.is_empty():
                hierarchy_menu.position = Vector2i(get_global_mouse_position())
                hierarchy_menu.popup()
                get_viewport().set_input_as_handled()


func _on_hierarchy_menu_pressed(id: int) -> void:
    var layer := model.get_layer(selected_layer_id)
    if layer.is_empty():
        return
    var before := model.data.duplicate(true)
    var after_model := VFXDocumentScript.from_dictionary(before)
    if id == 2:
        after_model.remove_layer(selected_layer_id)
        selected_layer_id = ""
        _apply_snapshot_action(before, after_model.data, "Remove layer")
    elif id == 1:
        var duplicate := layer.duplicate(true)
        var new_id := _unique_layer_id(str(layer.get("type", "layer")) + "_copy")
        duplicate["id"] = new_id
        duplicate["name"] = str(layer.get("name", new_id)) + " Copy"
        after_model.data["layers"].append(duplicate)
        selected_layer_id = new_id
        _apply_snapshot_action(before, after_model.data, "Duplicate layer")


func _on_add_layer_selected(index: int) -> void:
    if index <= 0:
        return
    var types := ["particle", "mesh_particle", "sprite", "light", "trail", "beam", "decal", "mesh_effect", "event_marker", "child_effect"]
    var layer_type: String = types[index - 1]
    var layer_id := _unique_layer_id(layer_type)
    var before := model.data.duplicate(true)
    var after_model := VFXDocumentScript.from_dictionary(before)
    after_model.add_layer(layer_type, layer_id)
    selected_layer_id = layer_id
    _apply_snapshot_action(before, after_model.data, "Add " + layer_type)


func _unique_layer_id(prefix: String) -> String:
    var index := 1
    while not model.get_layer(prefix + "_" + str(index)).is_empty():
        index += 1
    return prefix + "_" + str(index)


func _edit_path(path: String, value: Variant) -> void:
    var old_value: Variant = model.get_path(path)
    if JSON.stringify(old_value) == JSON.stringify(value):
        return
    undo_redo.create_action("Edit " + path)
    undo_redo.add_do_method(Callable(model, "set_path").bind(path, value))
    undo_redo.add_undo_method(Callable(model, "set_path").bind(path, old_value))
    undo_redo.add_do_method(Callable(self, "_after_undo_edit"))
    undo_redo.add_undo_method(Callable(self, "_after_undo_edit"))
    undo_redo.commit_action()


func _apply_snapshot_action(before: Dictionary, after: Dictionary, title: String) -> void:
    undo_redo.create_action(title)
    undo_redo.add_do_method(Callable(self, "_apply_snapshot").bind(after))
    undo_redo.add_undo_method(Callable(self, "_apply_snapshot").bind(before))
    undo_redo.commit_action()


func _apply_snapshot(snapshot: Dictionary) -> void:
    model.data = snapshot.duplicate(true)
    model.mark_dirty()
    _after_undo_edit()


func _after_undo_edit() -> void:
    _refresh_all()


func _refresh_runtime() -> void:
    if runtime == null:
        return
    runtime.set_document(model.data, _asset_root_for_source())


func _asset_root_for_source() -> String:
    if source_path.begins_with("res://"):
        return source_path.get_base_dir()
    var project_directory := ProjectSettings.globalize_path("res://")
    if source_path.begins_with(project_directory):
        var relative_path := source_path.trim_prefix(project_directory).trim_prefix("/")
        return "res://" + relative_path.get_base_dir()
    return "res://"


func _update_metrics() -> void:
    if model == null:
        return
    var particles := 0
    var lights := 0
    var draws := 0
    var triangles := 0
    for layer_variant in model.data.get("layers", []):
        if not layer_variant is Dictionary or not layer_variant.get("enabled", true):
            continue
        var layer: Dictionary = layer_variant
        var layer_type := str(layer.get("type", ""))
        if layer_type in ["particle", "mesh_particle"]:
            particles += int(layer.get("properties", {}).get("amount", 0))
            triangles += int(layer.get("properties", {}).get("amount", 0)) * (2 if layer_type == "particle" else 12)
        if layer_type == "light":
            lights += 1
        if layer_type in ["particle", "mesh_particle", "sprite", "light", "trail", "beam", "decal", "mesh_effect"]:
            draws += 1
            triangles += 2 if layer_type in ["sprite", "trail", "beam", "decal"] else (24 if layer_type == "mesh_effect" else 0)
    var summary := str(model.data.get("layers", []).size()) + " layers  •  ~" + str(particles) + " particles  •  " + str(lights) + " lights  •  ~" + str(draws) + " draws  •  ~" + str(triangles) + " tris"
    metrics_label.text = "  " + summary
    if is_instance_valid(performance_label):
        performance_label.text = "PERFORMANCE\n" + summary.replace("  •  ", "\n") + "\ntexture memory: project assets (approx.)"
    playback_time_label.text = "0.000s / " + "%.3f" % float(model.data.get("duration", 1.0)) + "  "


func _on_model_changed() -> void:
    project_title.text = str(model.data.get("name", "Untitled Effect"))
    _refresh_hierarchy()
    _refresh_inspector()
    _refresh_runtime()
    timeline.set_document(model.data)
    _update_metrics()


func _on_dirty_changed(value: bool) -> void:
    dirty_label.text = "  UNSAVED  " if value else "  SAVED  "
    dirty_label.add_theme_color_override("font_color", Color("#F6C760") if value else Color("#73D29B"))


func _on_runtime_time(time: float, duration: float) -> void:
    timeline.set_time(time)
    playback_time_label.text = "%.3fs / %.3fs  " % [time, duration]


func _on_runtime_warning(message: String) -> void:
    status_label.text = "Preview warning: " + message
    status_label.add_theme_color_override("font_color", Color("#F6C760"))


func _on_scrubbed(time: float) -> void:
    if runtime != null:
        runtime.seek(time)


func _on_layer_timing_changed(layer_id: String, start: float, duration: float) -> void:
    var before := model.data.duplicate(true)
    var after_model := VFXDocumentScript.from_dictionary(before)
    after_model.set_path("layers." + layer_id + ".start", start, false)
    after_model.set_path("layers." + layer_id + ".duration", duration, false)
    _apply_snapshot_action(before, after_model.data, "Edit layer timing")


func _on_play_pressed() -> void:
    runtime.play()


func _on_pause_pressed() -> void:
    runtime.pause()


func _on_stop_pressed() -> void:
    runtime.stop()


func _on_camera_selected(index: int) -> void:
    _set_camera(["mmo", "front", "side", "top"][index])


func _on_reset_view_pressed() -> void:
    if preview_view == null:
        return
    preview_view.reset_view()
    camera_menu.select(0)
    _set_camera("mmo")


func _set_camera(name: String) -> void:
    if preview_camera == null:
        return
    match name:
        "front":
            preview_camera.position = Vector3(0.0, 1.3, 5.5)
            preview_camera.look_at(Vector3(0.0, 0.8, 0.0))
        "side":
            preview_camera.position = Vector3(5.5, 1.3, 0.0)
            preview_camera.look_at(Vector3(0.0, 0.8, 0.0))
        "top":
            preview_camera.position = Vector3(0.0, 7.0, 0.01)
            preview_camera.look_at(Vector3.ZERO, Vector3.FORWARD)
        _:
            preview_camera.position = Vector3(4.5, 3.6, 5.5)
            preview_camera.look_at(Vector3(0.0, 0.8, 0.0))
    if preview_view != null:
        preview_view.sync_from_camera()


func _on_background_selected(index: int) -> void:
    if preview_environment == null or preview_environment.environment == null:
        return
    var backgrounds := [Color("#0B1220"), Color("#DCE1E8"), Color("#050812"), Color("#182033")]
    preview_environment.environment.background_color = backgrounds[index]
    preview_environment.environment.ambient_light_color = backgrounds[index].lightened(0.38)


func _on_open_pressed() -> void:
    file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
    file_dialog.popup_centered_ratio(0.72)


func _on_save_pressed() -> void:
    if source_path.is_empty():
        file_dialog.file_mode = FileDialog.FILE_MODE_SAVE_FILE
        file_dialog.current_file = str(model.data.get("id", "effect")) + ".vfx.json"
        file_dialog.popup_centered_ratio(0.72)
    else:
        if model.save_atomic(source_path):
            status_label.text = "Saved " + source_path
        else:
            status_label.text = "Save blocked by validation; inspect the document"


func _on_file_selected(path: String) -> void:
    if file_dialog.file_mode == FileDialog.FILE_MODE_SAVE_FILE:
        source_path = path
        model.source_path = path
        if model.save_atomic(path):
            status_label.text = "Saved " + path
        else:
            status_label.text = "Save blocked by validation; inspect the document"
    else:
        model = VFXDocumentScript.load_file(path)
        source_path = path
        undo_redo.clear_history()
        model.changed.connect(_on_model_changed)
        model.dirty_changed.connect(_on_dirty_changed)
        selected_layer_id = ""
        _refresh_all()
        if not model.load_error.is_empty():
            status_label.text = str(model.load_error.get("code", "LOAD_ERROR")) + ": " + str(model.load_error.get("message", "Could not load document."))
            status_label.add_theme_color_override("font_color", Color("#F6C760"))


func _on_autosave() -> void:
    if model != null and model.is_dirty and not source_path.is_empty():
        if model.autosave():
            status_label.text = "Autosaved recovery copy"


func _unhandled_key_input(event: InputEvent) -> void:
    if event is InputEventKey and event.pressed:
        if event.ctrl_pressed and event.keycode == KEY_S:
            _on_save_pressed()
            get_viewport().set_input_as_handled()
        elif event.ctrl_pressed and event.keycode == KEY_Z:
            undo_redo.undo()
            get_viewport().set_input_as_handled()
        elif event.ctrl_pressed and event.keycode == KEY_Y:
            undo_redo.redo()
            get_viewport().set_input_as_handled()
        elif event.keycode == KEY_SPACE:
            if runtime.is_playing:
                runtime.pause()
            else:
                runtime.play()
            get_viewport().set_input_as_handled()
