extends Control

const VFXDocumentScript = preload("res://godot/model/vfx_document.gd")
const ThemeBuilder := preload("res://godot/ui/theme/theme_builder.gd")
const Tokens := preload("res://godot/ui/theme/tokens.gd")
const AppMenubarScript := preload("res://godot/ui/panels/app_menubar.gd")
const AppToolbarScript := preload("res://godot/ui/panels/app_toolbar.gd")
const OutlinerPanelScript := preload("res://godot/ui/panels/outliner_panel.gd")
const ViewportPanelScript := preload("res://godot/ui/panels/viewport_panel.gd")
const InspectorPanelScript := preload("res://godot/ui/panels/inspector_panel.gd")
const BottomWorkspaceScript := preload("res://godot/ui/panels/bottom_workspace.gd")
const StatusBarScript := preload("res://godot/ui/panels/status_bar.gd")
const EditorStateScript := preload("res://godot/ui/editor/editor_state.gd")
const PreviewStageScript := preload("res://godot/editor/preview_stage.gd")
const ViewportGizmosScript := preload("res://godot/editor/viewport_gizmos.gd")
const EffectBoundsScript := preload("res://godot/editor/effect_bounds.gd")
const CommandPaletteScript := preload("res://godot/ui/shell/command_palette.gd")
const PresetBrowserScript := preload("res://godot/ui/shell/preset_browser.gd")
const LayoutPersistenceScript := preload("res://godot/ui/editor/layout_persistence.gd")
const LayerPresetsScript := preload("res://godot/ui/data/layer_presets.gd")
const ExportRunnerScript := preload("res://godot/ui/editor/export_runner.gd")
const DocumentSessionScript := preload("res://godot/ui/editor/document_session.gd")
const DocumentTabsScript := preload("res://godot/ui/panels/document_tabs.gd")
const RenameDialogScript := preload("res://godot/ui/shell/rename_dialog.gd")

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
var preview_stage: VFXPreviewStage
var viewport_gizmos: VFXViewportGizmos
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
var hierarchy_menu: PopupMenu
var main_split: HSplitContainer
var content_split: HSplitContainer
var editor_split: VSplitContainer

var _menubar: VFXAppMenubar
var _toolbar: VFXAppToolbar
var _document_tabs: VFXDocumentTabs
var _outliner: VFXOutlinerPanel
var _viewport_panel: VFXViewportPanel
var _inspector_panel: VFXInspectorPanel
var _bottom: VFXBottomWorkspace
var _status_bar: VFXStatusBar
var _toast_label: Label
var _editor_state: VFXEditorState = EditorStateScript.new()
var _command_palette: VFXCommandPalette
var _preset_browser: VFXPresetBrowser
var _layout_state: Dictionary = {}
var _panel_visibility := {"outliner": true, "inspector": true, "bottom": true}
var _sessions: Array[VFXDocumentSession] = []
var _active_session_index := 0
var _rename_dialog: VFXRenameDialog
var _about_dialog: AcceptDialog
var _export_folder_dialog: FileDialog
var _pending_export_output := ""
var _show_bounds_overlay := false
var _should_auto_frame := true


func _ready() -> void:
	ThemeBuilder.apply(self)
	_build_interface()
	_build_preview()
	_connect_input()
	_load_startup_document()


func _exit_tree() -> void:
	_save_layout_state()
	for index in range(_sessions.size()):
		var session := _sessions[index]
		if session.undo_redo == undo_redo:
			continue
		if is_instance_valid(session.undo_redo):
			session.undo_redo.free()
	if is_instance_valid(undo_redo):
		undo_redo.free()


func _build_interface() -> void:
	var background := ColorRect.new()
	background.color = Tokens.APP_BG
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)

	var root := VBoxContainer.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_theme_constant_override("separation", 0)
	add_child(root)

	_menubar = AppMenubarScript.new()
	_menubar.menu_action.connect(_on_menu_action)
	_menubar.validate_requested.connect(_on_validate_pressed)
	_menubar.export_requested.connect(_on_export_pressed)
	_menubar.panel_visibility_changed.connect(_on_panel_visibility_changed)
	root.add_child(_menubar)
	project_title = _menubar.project_title
	dirty_label = _menubar.dirty_indicator

	_toolbar = AppToolbarScript.new()
	_toolbar.add_layer_selected.connect(_on_add_layer_selected)
	root.add_child(_toolbar)

	_document_tabs = DocumentTabsScript.new()
	_document_tabs.tab_selected.connect(_switch_document_tab)
	_document_tabs.tab_close_requested.connect(_close_document_tab)
	_document_tabs.new_tab_requested.connect(_open_new_document_tab)
	root.add_child(_document_tabs)

	_command_palette = CommandPaletteScript.new()
	_command_palette.command_invoked.connect(_on_command_invoked)
	add_child(_command_palette)

	_preset_browser = PresetBrowserScript.new()
	_preset_browser.preset_selected.connect(_on_preset_selected)
	add_child(_preset_browser)

	editor_split = VSplitContainer.new()
	editor_split.name = "EditorSplit"
	editor_split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_child(editor_split)

	main_split = HSplitContainer.new()
	main_split.name = "MainSplit"
	main_split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	editor_split.add_child(main_split)

	_outliner = OutlinerPanelScript.new()
	_outliner.layer_selected.connect(_select_layer)
	_outliner.duplicate_requested.connect(_on_duplicate_layer)
	_outliner.remove_requested.connect(_on_remove_layer)
	_outliner.rename_requested.connect(_on_rename_layer)
	_outliner.visibility_toggled.connect(_on_toggle_layer_enabled)
	_outliner.solo_toggled.connect(_on_toggle_layer_solo)
	_outliner.lock_toggled.connect(_on_toggle_layer_lock)
	_outliner.reorder_requested.connect(_on_reorder_layer)
	_outliner.filter_changed.connect(_on_outliner_filter_changed)
	_outliner.copy_id_requested.connect(_on_copy_layer_id)
	main_split.add_child(_outliner)
	hierarchy = _outliner.hierarchy
	hierarchy_menu = _outliner.hierarchy_menu

	content_split = HSplitContainer.new()
	content_split.name = "ContentSplit"
	content_split.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_viewport_panel = ViewportPanelScript.new()
	_viewport_panel.camera_selected.connect(_on_camera_selected)
	_viewport_panel.stage_preset_selected.connect(_on_stage_preset_selected)
	_viewport_panel.backdrop_selected.connect(_on_backdrop_selected)
	_viewport_panel.reset_view_requested.connect(_on_reset_view_pressed)
	_viewport_panel.grid_toggled.connect(_on_grid_toggled)
	_viewport_panel.bounds_toggled.connect(_on_bounds_toggled)
	_viewport_panel.frame_effect_requested.connect(_auto_frame_effect)
	content_split.add_child(_viewport_panel)
	preview_view = _viewport_panel.preview_view
	viewport_container = _viewport_panel.viewport_container
	metrics_label = _viewport_panel.metrics_label
	camera_menu = _viewport_panel.camera_menu
	background_menu = _viewport_panel.backdrop_menu

	_inspector_panel = InspectorPanelScript.new()
	_inspector_panel.edit_requested.connect(_edit_path)
	_inspector_panel.curve_edit_requested.connect(_on_inspector_curve_edit)
	_inspector_panel.gradient_edit_requested.connect(_on_inspector_gradient_edit)
	content_split.add_child(_inspector_panel)
	inspector = _inspector_panel.inspector
	inspector_scroll = _inspector_panel.inspector_scroll
	inspector_title = _inspector_panel.inspector_title

	main_split.add_child(content_split)

	_bottom = BottomWorkspaceScript.new()
	_bottom.scrubbed.connect(_on_scrubbed)
	_bottom.layer_timing_changed.connect(_on_layer_timing_changed)
	_bottom.play_requested.connect(_on_play_pressed)
	_bottom.pause_requested.connect(_on_pause_pressed)
	_bottom.stop_requested.connect(_on_stop_pressed)
	_bottom.speed_changed.connect(_on_speed_changed)
	_bottom.curve_edit_requested.connect(_edit_path)
	_bottom.curve_layer_selected.connect(_select_layer)
	_bottom.events_changed.connect(_on_events_changed)
	_bottom.event_scrub_requested.connect(_on_scrubbed)
	_bottom.diagnostics_navigate.connect(_on_diagnostics_navigate)
	_bottom.workspace_changed.connect(func(_index: int) -> void: _save_layout_state())
	editor_split.add_child(_bottom)
	timeline = _bottom.timeline
	timeline.layer_selected.connect(_select_layer)
	playback_time_label = _bottom.playback_time_label
	playback_slider = _bottom.playback_slider
	speed_menu = _bottom.speed_menu

	_status_bar = StatusBarScript.new()
	root.add_child(_status_bar)
	status_label = _status_bar.status_label

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

	_rename_dialog = RenameDialogScript.new()
	_rename_dialog.rename_confirmed.connect(_on_layer_renamed)
	add_child(_rename_dialog)

	_about_dialog = AcceptDialog.new()
	_about_dialog.title = "About VFX Forge"
	_about_dialog.dialog_text = "VFX Forge\nOffline Godot 4.x VFX authoring workstation.\nCanonical source: *.vfx.json"
	add_child(_about_dialog)

	_export_folder_dialog = FileDialog.new()
	_export_folder_dialog.access = FileDialog.ACCESS_FILESYSTEM
	_export_folder_dialog.file_mode = FileDialog.FILE_MODE_OPEN_DIR
	_export_folder_dialog.dir_selected.connect(_on_export_folder_selected)
	add_child(_export_folder_dialog)

	call_deferred("_configure_split_layout")
	_toolbar.command_palette_requested.connect(_command_palette.open_palette)
	_toolbar.preset_browser_requested.connect(_preset_browser.open_browser)


func _configure_split_layout() -> void:
	if not is_instance_valid(main_split) or not is_instance_valid(content_split) or not is_instance_valid(editor_split):
		return
	_layout_state = LayoutPersistenceScript.load_state()
	if _layout_state.is_empty():
		_layout_state = LayoutPersistenceScript.default_state()
	var panels: Variant = _layout_state.get("panels", {})
	if panels is Dictionary:
		_panel_visibility = {
			"outliner": bool(panels.get("outliner", true)),
			"inspector": bool(panels.get("inspector", true)),
			"bottom": bool(panels.get("bottom", true)),
		}
	_apply_panel_visibility()
	await get_tree().process_frame
	main_split.split_offset = int(_layout_state.get("main_split", 260))
	content_split.split_offsets = PackedInt32Array([int(_layout_state.get("content_split", 175))])
	editor_split.split_offset = int(_layout_state.get("editor_split", 520))
	_bottom.set_workspace_tab(int(_layout_state.get("workspace_tab", 0)))
	var stage_id := str(_layout_state.get("stage_preset", "mmo_combat"))
	var stage_index := PreviewStageScript.PRESET_IDS.find(stage_id)
	if stage_index >= 0 and is_instance_valid(_viewport_panel):
		_viewport_panel.stage_menu.select(stage_index)
	main_split.dragged.connect(func(_offset: int) -> void: _save_layout_state())
	content_split.dragged.connect(func(_offset: int) -> void: _save_layout_state())
	editor_split.dragged.connect(func(_offset: int) -> void: _save_layout_state())


func _build_preview() -> void:
	preview_viewport = SubViewport.new()
	preview_viewport.name = "PreviewViewport"
	preview_viewport.size = Vector2i(900, 580)
	preview_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	preview_viewport.transparent_bg = false
	_viewport_panel.attach_viewport(preview_viewport)

	var world := Node3D.new()
	world.name = "PreviewWorld"
	preview_viewport.add_child(world)

	preview_environment = WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Tokens.VIEWPORT_BG
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("#4A5060")
	environment.ambient_light_energy = 0.55
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

	preview_stage = PreviewStageScript.new()
	world.add_child(preview_stage)

	viewport_gizmos = ViewportGizmosScript.new()
	viewport_gizmos.gizmo_changed.connect(_on_gizmo_changed)
	world.add_child(viewport_gizmos)
	preview_view.set_gizmos(viewport_gizmos)

	runtime = VFXRuntime.new()
	runtime.name = "PreviewRuntime"
	runtime.time_changed.connect(_on_runtime_time)
	runtime.runtime_warning.connect(_on_runtime_warning)
	preview_viewport.add_child(runtime)
	_apply_viewport_layout_state()


func _apply_viewport_layout_state() -> void:
	if _layout_state.is_empty():
		return
	var stage_id := str(_layout_state.get("stage_preset", "mmo_combat"))
	if is_instance_valid(preview_stage):
		preview_stage.apply_preset(stage_id)
	var grid_visible := bool(_layout_state.get("grid_visible", true))
	_show_bounds_overlay = bool(_layout_state.get("bounds_visible", false))
	if is_instance_valid(_viewport_panel):
		_viewport_panel.grid_button.button_pressed = grid_visible
		_viewport_panel.bounds_button.button_pressed = _show_bounds_overlay
	if is_instance_valid(preview_stage):
		preview_stage.set_grid_visible(grid_visible)
	var backdrop_index := int(_layout_state.get("backdrop_index", 0))
	var camera_index := int(_layout_state.get("camera_index", 0))
	var speed_index := int(_layout_state.get("playback_speed_index", 2))
	if is_instance_valid(_viewport_panel):
		if backdrop_index >= 0 and backdrop_index < _viewport_panel.backdrop_menu.item_count:
			_viewport_panel.backdrop_menu.select(backdrop_index)
			_on_backdrop_selected(backdrop_index)
		if camera_index >= 0 and camera_index < _viewport_panel.camera_menu.item_count:
			_viewport_panel.camera_menu.select(camera_index)
			_on_camera_selected(camera_index)
	if is_instance_valid(speed_menu) and speed_index >= 0 and speed_index < speed_menu.item_count:
		speed_menu.select(speed_index)
		_on_speed_changed([0.25, 0.5, 1.0, 2.0][speed_index])
	_menubar.set_panel_visibility(_panel_visibility)


func _connect_input() -> void:
	if not InputMap.has_action("save_project"):
		InputMap.add_action("save_project")


func _load_startup_document() -> void:
	var requested := ""
	var recovered := false
	for argument in OS.get_cmdline_args():
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
	_sessions = [DocumentSessionScript.create(model, source_path)]
	if _sessions[0].undo_redo != undo_redo:
		_sessions[0].undo_redo.free()
	_sessions[0].undo_redo = undo_redo
	_active_session_index = 0
	_update_document_tabs()
	_inspector_panel.bind_model(model)
	_refresh_all()
	if not model.load_error.is_empty():
		status_label.text = str(model.load_error.get("code", "LOAD_ERROR")) + ": " + str(model.load_error.get("message", "Could not load document."))
		status_label.add_theme_color_override("font_color", Tokens.WARNING)
	elif recovered:
		status_label.text = "Recovered newer autosave; review before saving"


func _refresh_all() -> void:
	if model == null:
		return
	if not _sessions.is_empty():
		var session := _sessions[_active_session_index]
		session.model = model
		session.source_path = source_path
		session.selected_layer_id = selected_layer_id
		session.display_name = str(model.data.get("name", "Untitled Effect"))
		_update_document_tabs()
	_inspector_panel.bind_model(model)
	var effect_name := str(model.data.get("name", "Untitled Effect"))
	project_title.text = effect_name
	_menubar.set_document_name(effect_name, model.is_dirty)
	_outliner.set_editor_overlays(_editor_state.solo_layer_id, _editor_state.locked_layers)
	_outliner.populate(model.data, selected_layer_id)
	var summary := _metrics_summary()
	_inspector_panel.refresh(selected_layer_id, summary)
	performance_label = _inspector_panel.performance_label
	_refresh_runtime()
	_bottom.set_document(model.data, selected_layer_id)
	timeline.set_selected_layer(selected_layer_id)
	_refresh_diagnostics()
	_update_viewport_overlays()
	if _should_auto_frame:
		call_deferred("_auto_frame_effect")
		_should_auto_frame = false
	_update_metrics()


func _metrics_summary() -> String:
	if model == null:
		return ""
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
	return str(model.data.get("layers", []).size()) + " layers  •  ~" + str(particles) + " particles  •  " + str(lights) + " lights  •  ~" + str(draws) + " draws  •  ~" + str(triangles) + " tris"


func _select_layer(layer_id: String) -> void:
	if layer_id.is_empty() or selected_layer_id == layer_id:
		return
	selected_layer_id = layer_id
	_sync_selection_ui()


func _sync_runtime_editor_state() -> void:
	if runtime == null:
		return
	runtime.set_editor_selection(selected_layer_id)
	runtime.set_editor_solo(_editor_state.solo_layer_id)


func _on_copy_layer_id(layer_id: String) -> void:
	DisplayServer.clipboard_set(layer_id)
	status_label.text = "Copied layer ID"


func _on_outliner_filter_changed() -> void:
	if model == null:
		return
	_outliner.set_editor_overlays(_editor_state.solo_layer_id, _editor_state.locked_layers)
	_outliner.populate(model.data, selected_layer_id)


func _on_toggle_layer_enabled(layer_id: String) -> void:
	var layer := model.get_layer(layer_id)
	if layer.is_empty():
		return
	_edit_path("layers." + layer_id + ".enabled", not bool(layer.get("enabled", true)))


func _on_toggle_layer_solo(layer_id: String) -> void:
	_editor_state.toggle_solo(layer_id)
	_refresh_all()


func _on_toggle_layer_lock(layer_id: String) -> void:
	_editor_state.set_locked(layer_id, not _editor_state.is_locked(layer_id))
	_refresh_all()


func _on_reorder_layer(layer_id: String, target_index: int) -> void:
	if _editor_state.is_locked(layer_id):
		return
	var layers: Array = model.data.get("layers", [])
	var from_index := -1
	for index in range(layers.size()):
		if layers[index] is Dictionary and str(layers[index].get("id", "")) == layer_id:
			from_index = index
			break
	if from_index < 0:
		return
	var before := model.data.duplicate(true)
	var after_model := VFXDocumentScript.from_dictionary(before)
	var moved_layers: Array = after_model.data.get("layers", [])
	var layer: Dictionary = moved_layers[from_index]
	moved_layers.remove_at(from_index)
	var insert_at: int = clampi(target_index, 0, moved_layers.size())
	moved_layers.insert(insert_at, layer)
	after_model.data["layers"] = moved_layers
	_apply_snapshot_action(before, after_model.data, "Reorder layer")


func _on_rename_layer() -> void:
	if selected_layer_id.is_empty():
		return
	var layer := model.get_layer(selected_layer_id)
	if layer.is_empty():
		return
	_rename_dialog.open_rename(str(layer.get("name", selected_layer_id)))


func _on_layer_renamed(new_name: String) -> void:
	if selected_layer_id.is_empty() or new_name.is_empty():
		return
	_edit_path("layers." + selected_layer_id + ".name", new_name)


func _navigate_layer(offset: int) -> void:
	if model == null:
		return
	var ids: Array[String] = _outliner.layer_ids_in_order(model.data)
	if ids.is_empty():
		return
	var current_index := ids.find(selected_layer_id)
	if current_index < 0:
		_select_layer(ids[0])
		return
	var next_index: int = clampi(current_index + offset, 0, ids.size() - 1)
	_select_layer(ids[next_index])


func _move_selected_layer(offset: int) -> void:
	if selected_layer_id.is_empty() or _editor_state.is_locked(selected_layer_id):
		return
	var layers: Array = model.data.get("layers", [])
	var from_index := -1
	for index in range(layers.size()):
		if layers[index] is Dictionary and str(layers[index].get("id", "")) == selected_layer_id:
			from_index = index
			break
	if from_index < 0:
		return
	var target_index: int = clampi(from_index + offset, 0, layers.size() - 1)
	if target_index == from_index:
		return
	_on_reorder_layer(selected_layer_id, target_index)


func _edit_path(path: String, value: Variant) -> void:
	if _path_is_locked(path):
		status_label.text = "Layer is locked"
		return
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
	_sync_runtime_editor_state()


func _path_is_locked(path: String) -> bool:
	if not path.begins_with("layers."):
		return false
	var parts := path.split(".")
	if parts.size() < 2:
		return false
	return _editor_state.is_locked(parts[1])


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
	var summary := _metrics_summary()
	metrics_label.text = "  " + summary
	_viewport_panel.set_performance_text(_performance_overlay_text())
	if is_instance_valid(_status_bar) and is_instance_valid(_status_bar.gpu_label):
		_status_bar.gpu_label.text = _performance_overlay_text()
	if is_instance_valid(performance_label):
		performance_label.text = "PERFORMANCE\n" + summary.replace("  •  ", "\n")
	var duration := float(model.data.get("duration", 1.0))
	_bottom.set_time(0.0 if runtime == null else runtime.elapsed, duration)


func _performance_overlay_text() -> String:
	if model == null:
		return "GPU: GOOD"
	var particles := 0
	var draws := 0
	var lights := 0
	for layer_variant in model.data.get("layers", []):
		if not layer_variant is Dictionary or not layer_variant.get("enabled", true):
			continue
		var layer: Dictionary = layer_variant
		var layer_type := str(layer.get("type", ""))
		if layer_type in ["particle", "mesh_particle"]:
			particles += int(layer.get("properties", {}).get("amount", 0))
			draws += 1
		elif layer_type == "light":
			lights += 1
			draws += 1
		elif layer_type in ["sprite", "trail", "beam", "decal", "mesh_effect"]:
			draws += 1
	var budget := "GOOD" if particles <= 512 and draws <= 12 else "WARN"
	return "Particles %d  •  Draws %d  •  Lights %d  •  %s" % [particles, draws, lights, budget]


func _on_model_changed() -> void:
	var effect_name := str(model.data.get("name", "Untitled Effect"))
	project_title.text = effect_name
	_menubar.set_document_name(effect_name, model.is_dirty)
	_outliner.set_editor_overlays(_editor_state.solo_layer_id, _editor_state.locked_layers)
	_outliner.populate(model.data, selected_layer_id)
	_inspector_panel.refresh(selected_layer_id, _metrics_summary())
	performance_label = _inspector_panel.performance_label
	_refresh_runtime()
	_bottom.set_document(model.data, selected_layer_id)
	timeline.set_selected_layer(selected_layer_id)
	_refresh_diagnostics()
	_update_viewport_overlays()
	_update_metrics()


func _on_dirty_changed(value: bool) -> void:
	_menubar.set_document_name(str(model.data.get("name", "Untitled Effect")), value)
	dirty_label.text = ""
	_update_document_tabs()


func _show_toast(message: String) -> void:
	if _toast_label == null:
		_toast_label = Label.new()
		_toast_label.set_anchors_preset(Control.PRESET_CENTER_TOP)
		_toast_label.offset_top = 72
		_toast_label.add_theme_color_override("font_color", Tokens.TEXT_PRIMARY)
		_toast_label.add_theme_font_size_override("font_size", Tokens.FONT_SMALL)
		add_child(_toast_label)
	_toast_label.text = message
	_toast_label.visible = true
	var timer := get_tree().create_timer(1.4)
	timer.timeout.connect(func() -> void:
		if is_instance_valid(_toast_label):
			_toast_label.visible = false
	)


func _on_runtime_time(time: float, duration: float) -> void:
	_bottom.set_time(time, duration)


func _on_runtime_warning(message: String) -> void:
	status_label.text = "Preview warning: " + message
	status_label.add_theme_color_override("font_color", Tokens.WARNING)


func _on_scrubbed(time: float) -> void:
	if runtime != null:
		runtime.seek(time)


func _on_layer_timing_changed(layer_id: String, start: float, duration: float) -> void:
	if _editor_state.is_locked(layer_id):
		status_label.text = "Layer is locked"
		return
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


func _on_speed_changed(speed: float) -> void:
	runtime.playback_speed = speed
	_save_layout_state()


func _on_camera_selected(index: int) -> void:
	_set_camera(["mmo", "front", "side", "top"][index])
	_save_layout_state()


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


func _sync_selection_ui() -> void:
	_outliner.select_layer(selected_layer_id)
	timeline.set_selected_layer(selected_layer_id)
	_inspector_panel.refresh(selected_layer_id, _metrics_summary())
	performance_label = _inspector_panel.performance_label
	_bottom.set_document(model.data, selected_layer_id)
	if viewport_gizmos != null and model != null:
		viewport_gizmos.set_selection(selected_layer_id, model.get_layer(selected_layer_id))
	_sync_runtime_editor_state()
	_update_viewport_overlays()


func _update_viewport_overlays() -> void:
	if model == null or viewport_gizmos == null:
		return
	var bounds: AABB = EffectBoundsScript.from_document(model.data)
	viewport_gizmos.update_bounds_box(bounds, _show_bounds_overlay)


func _auto_frame_effect() -> void:
	if model == null or preview_view == null:
		return
	var bounds: AABB = EffectBoundsScript.from_document(model.data)
	preview_view.frame_aabb(bounds)


func _on_gizmo_changed(_layer_id: String, path: String, value: Variant) -> void:
	_edit_path(path, value)


func _on_stage_preset_selected(index: int) -> void:
	if preview_stage == null:
		return
	if index >= 0 and index < PreviewStageScript.PRESET_IDS.size():
		preview_stage.apply_preset(PreviewStageScript.PRESET_IDS[index])
	_save_layout_state()


func _on_grid_toggled(visible: bool) -> void:
	if preview_stage != null:
		preview_stage.set_grid_visible(visible)
	_save_layout_state()


func _on_bounds_toggled(visible: bool) -> void:
	_show_bounds_overlay = visible
	_update_viewport_overlays()
	_save_layout_state()


func _on_backdrop_selected(index: int) -> void:
	if preview_environment == null or preview_environment.environment == null:
		return
	var backgrounds := [Color("#0B0C0F"), Color("#DCE1E8"), Color("#050812"), Color("#182033")]
	preview_environment.environment.background_color = backgrounds[index]
	preview_environment.environment.ambient_light_color = backgrounds[index].lightened(0.38)
	_save_layout_state()


func _on_duplicate_layer() -> void:
	var layer := model.get_layer(selected_layer_id)
	if layer.is_empty():
		return
	var before := model.data.duplicate(true)
	var after_model := VFXDocumentScript.from_dictionary(before)
	var duplicate := layer.duplicate(true)
	var new_id := _unique_layer_id(str(layer.get("type", "layer")) + "_copy")
	duplicate["id"] = new_id
	duplicate["name"] = str(layer.get("name", new_id)) + " Copy"
	after_model.data["layers"].append(duplicate)
	selected_layer_id = new_id
	_apply_snapshot_action(before, after_model.data, "Duplicate layer")


func _on_remove_layer() -> void:
	var layer := model.get_layer(selected_layer_id)
	if layer.is_empty():
		return
	if _editor_state.is_locked(selected_layer_id):
		status_label.text = "Layer is locked"
		return
	var before := model.data.duplicate(true)
	var after_model := VFXDocumentScript.from_dictionary(before)
	after_model.remove_layer(selected_layer_id)
	if _editor_state.solo_layer_id == selected_layer_id:
		_editor_state.solo_layer_id = ""
	_editor_state.locked_layers.erase(selected_layer_id)
	selected_layer_id = ""
	_apply_snapshot_action(before, after_model.data, "Remove layer")


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
	_toolbar.add_layer_menu.select(0)


func _unique_layer_id(prefix: String) -> String:
	var index := 1
	while not model.get_layer(prefix + "_" + str(index)).is_empty():
		index += 1
	return prefix + "_" + str(index)


func _on_open_pressed() -> void:
	file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	file_dialog.popup_centered_ratio(0.72)


func _on_save_pressed() -> void:
	if source_path.is_empty():
		file_dialog.file_mode = FileDialog.FILE_MODE_SAVE_FILE
		file_dialog.current_file = str(model.data.get("id", "effect")) + ".vfx.json"
		file_dialog.popup_centered_ratio(0.72)
	elif model.save_atomic(source_path):
		_show_toast(str(model.data.get("name", "Effect")) + ".vfx saved")
		status_label.text = "Saved " + source_path
	else:
		status_label.text = "Save blocked by validation; inspect the document"


func _on_validate_pressed() -> void:
	var result := model.basic_validation()
	_refresh_diagnostics()
	if result.get("errors", []).is_empty():
		status_label.text = "Validation passed"
		status_label.add_theme_color_override("font_color", Tokens.SUCCESS)
	else:
		status_label.text = str(result.get("errors", []).size()) + " validation issue(s)"
		status_label.add_theme_color_override("font_color", Tokens.WARNING)
	_bottom.set_workspace_tab(4)


func _on_export_pressed() -> void:
	if model == null:
		return
	if model.is_dirty or source_path.is_empty():
		status_label.text = "Save the effect before exporting"
		status_label.add_theme_color_override("font_color", Tokens.WARNING)
		_on_save_pressed()
		return
	var validation := model.basic_validation()
	if not bool(validation.get("valid", false)):
		status_label.text = "Fix validation issues before exporting"
		status_label.add_theme_color_override("font_color", Tokens.WARNING)
		_on_validate_pressed()
		return
	_pending_export_output = ExportRunnerScript.default_output_dir(source_path, model.data)
	_export_folder_dialog.current_dir = _pending_export_output.get_base_dir()
	_export_folder_dialog.popup_centered_ratio(0.55)


func _on_export_folder_selected(output_dir: String) -> void:
	var result := ExportRunnerScript.run_export(source_path, output_dir)
	if bool(result.get("success", false)):
		status_label.text = str(result.get("message", "Export complete"))
		status_label.add_theme_color_override("font_color", Tokens.SUCCESS)
		_show_toast("Export complete")
	else:
		status_label.text = str(result.get("message", "Export failed"))
		status_label.add_theme_color_override("font_color", Tokens.WARNING)


func _on_menu_action(action: String) -> void:
	match action:
		"File:1":
			_on_open_pressed()
		"File:2", "File:3":
			_on_save_pressed()
		"File:4":
			_on_export_pressed()
		"Edit:10":
			undo_redo.undo()
		"Edit:11":
			undo_redo.redo()
		"View:20":
			timeline.frame_all()
		"View:21":
			_on_reset_view_pressed()
		"Effect:30":
			_on_validate_pressed()
		"Window:40":
			_command_palette.open_palette()
		"Help:50":
			_about_dialog.popup_centered(Vector2(420, 220))
		_:
			pass


func _on_file_selected(path: String) -> void:
	if file_dialog.file_mode == FileDialog.FILE_MODE_SAVE_FILE:
		source_path = path
		model.source_path = path
		if model.save_atomic(path):
			_show_toast(str(model.data.get("name", "Effect")) + ".vfx saved")
			status_label.text = "Saved " + path
		else:
			status_label.text = "Save blocked by validation; inspect the document"
	else:
		for index in range(_sessions.size()):
			if _sessions[index].source_path == path:
				_apply_session(index)
				return
		_persist_active_session()
		var opened := VFXDocumentScript.load_file(path)
		var session := DocumentSessionScript.create(opened, path)
		_sessions.append(session)
		_apply_session(_sessions.size() - 1)
		if not opened.load_error.is_empty():
			status_label.text = str(opened.load_error.get("code", "LOAD_ERROR")) + ": " + str(opened.load_error.get("message", "Could not load document."))
			status_label.add_theme_color_override("font_color", Tokens.WARNING)


func _on_autosave() -> void:
	if model != null and model.is_dirty and not source_path.is_empty():
		if model.autosave():
			status_label.text = "Autosaved recovery copy"


func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		if _text_input_has_focus():
			return
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
		elif event.keycode == KEY_UP:
			_navigate_layer(-1)
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_DOWN:
			_navigate_layer(1)
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_DELETE:
			_on_remove_layer()
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_F:
			if not selected_layer_id.is_empty():
				timeline.frame_layer(selected_layer_id)
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_HOME:
			timeline.frame_all()
			get_viewport().set_input_as_handled()
		elif event.ctrl_pressed and event.keycode == KEY_UP:
			_move_selected_layer(-1)
			get_viewport().set_input_as_handled()
		elif event.ctrl_pressed and event.keycode == KEY_DOWN:
			_move_selected_layer(1)
			get_viewport().set_input_as_handled()
		elif event.ctrl_pressed and event.keycode == KEY_K:
			_command_palette.open_palette()
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_F2:
			_on_rename_layer()
			get_viewport().set_input_as_handled()


func _text_input_has_focus() -> bool:
	var focus := get_viewport().gui_get_focus_owner()
	return focus is LineEdit or focus is TextEdit or focus is SpinBox


func _disconnect_model_signals() -> void:
	if model == null:
		return
	if model.changed.is_connected(_on_model_changed):
		model.changed.disconnect(_on_model_changed)
	if model.dirty_changed.is_connected(_on_dirty_changed):
		model.dirty_changed.disconnect(_on_dirty_changed)


func _connect_model_signals() -> void:
	if model == null:
		return
	if not model.changed.is_connected(_on_model_changed):
		model.changed.connect(_on_model_changed)
	if not model.dirty_changed.is_connected(_on_dirty_changed):
		model.dirty_changed.connect(_on_dirty_changed)


func _persist_active_session() -> void:
	if _sessions.is_empty() or model == null:
		return
	var session := _sessions[_active_session_index]
	session.model = model
	session.source_path = source_path
	session.selected_layer_id = selected_layer_id
	session.display_name = str(model.data.get("name", "Untitled Effect"))
	session.should_auto_frame = _should_auto_frame
	session.editor_state.solo_layer_id = _editor_state.solo_layer_id
	session.editor_state.locked_layers = _editor_state.locked_layers.duplicate()
	if session.undo_redo != undo_redo:
		session.undo_redo = undo_redo


func _apply_session(index: int) -> void:
	if index < 0 or index >= _sessions.size():
		return
	if not _sessions.is_empty() and index != _active_session_index:
		_persist_active_session()
	_disconnect_model_signals()
	_active_session_index = index
	var session := _sessions[index]
	model = session.model
	source_path = session.source_path
	selected_layer_id = session.selected_layer_id
	_should_auto_frame = session.should_auto_frame
	_editor_state.solo_layer_id = session.editor_state.solo_layer_id
	_editor_state.locked_layers = session.editor_state.locked_layers.duplicate()
	undo_redo = session.undo_redo
	_connect_model_signals()
	_inspector_panel.bind_model(model)
	_refresh_all()


func _switch_document_tab(index: int) -> void:
	_apply_session(index)


func _close_document_tab(index: int) -> void:
	if index < 0 or index >= _sessions.size():
		return
	if _sessions.size() <= 1:
		_show_toast("At least one effect tab must remain open")
		return
	var closing := _sessions[index]
	if index == _active_session_index:
		_persist_active_session()
	if closing.undo_redo != undo_redo and is_instance_valid(closing.undo_redo):
		closing.undo_redo.free()
	_sessions.remove_at(index)
	if _active_session_index >= _sessions.size():
		_active_session_index = max(0, _sessions.size() - 1)
	elif index < _active_session_index:
		_active_session_index -= 1
	_apply_session(_active_session_index)


func _open_new_document_tab() -> void:
	_persist_active_session()
	var new_model := VFXDocumentScript.create("untitled_effect_%d" % (_sessions.size() + 1), "Untitled Effect %d" % (_sessions.size() + 1))
	var session := DocumentSessionScript.create(new_model, "")
	_sessions.append(session)
	_apply_session(_sessions.size() - 1)


func _update_document_tabs() -> void:
	if _document_tabs == null or _sessions.is_empty():
		return
	var labels: PackedStringArray = []
	for session in _sessions:
		var dirty := session.model.is_dirty if session.model != null else false
		labels.append(session.tab_label(dirty))
	_document_tabs.set_tabs(labels, _active_session_index)


func _on_panel_visibility_changed(panel_id: String, visible: bool) -> void:
	_panel_visibility[panel_id] = visible
	_apply_panel_visibility()
	_save_layout_state()


func _apply_panel_visibility() -> void:
	if is_instance_valid(_outliner):
		_outliner.visible = bool(_panel_visibility.get("outliner", true))
	if is_instance_valid(_inspector_panel):
		_inspector_panel.visible = bool(_panel_visibility.get("inspector", true))
	if is_instance_valid(_bottom):
		_bottom.visible = bool(_panel_visibility.get("bottom", true))
	if is_instance_valid(_menubar):
		_menubar.set_panel_visibility(_panel_visibility)


func _on_inspector_curve_edit(layer_id: String, curve_key: String = "scale") -> void:
	if not layer_id.is_empty():
		_select_layer(layer_id)
	_bottom.focus_curve_workspace(layer_id if not layer_id.is_empty() else selected_layer_id, curve_key)


func _on_inspector_gradient_edit(layer_id: String) -> void:
	if not layer_id.is_empty():
		_select_layer(layer_id)
	_bottom.focus_gradient_workspace(layer_id if not layer_id.is_empty() else selected_layer_id)


func _on_events_changed(events: Array) -> void:
	var before := model.data.duplicate(true)
	var after_model := VFXDocumentScript.from_dictionary(before)
	var timeline_data: Dictionary = after_model.data.get("timeline", {})
	if not timeline_data is Dictionary:
		timeline_data = {}
	timeline_data["events"] = events.duplicate(true)
	after_model.data["timeline"] = timeline_data
	_apply_snapshot_action(before, after_model.data, "Edit timeline events")


func _on_diagnostics_navigate(layer_id: String, path: String) -> void:
	if not layer_id.is_empty():
		_select_layer(layer_id)
	if not path.is_empty():
		status_label.text = "Issue at " + path


func _on_command_invoked(command_id: String) -> void:
	match command_id:
		"file.open":
			_on_open_pressed()
		"file.save":
			_on_save_pressed()
		"file.validate":
			_on_validate_pressed()
		"file.export":
			_on_export_pressed()
		"edit.undo":
			undo_redo.undo()
		"edit.redo":
			undo_redo.redo()
		"layer.add_particle":
			_on_add_layer_selected(1)
		"layer.add_light":
			_on_add_layer_selected(4)
		"layer.add_mesh_effect":
			_on_add_layer_selected(8)
		"preset.browser":
			_preset_browser.open_browser()
		"view.frame_effect":
			_auto_frame_effect()
		"view.reset_camera":
			_on_reset_view_pressed()
		"workspace.timeline":
			_bottom.set_workspace_tab(0)
		"workspace.curves":
			_bottom.set_workspace_tab(1)
		"workspace.gradients":
			_bottom.set_workspace_tab(2)
		"workspace.events":
			_bottom.set_workspace_tab(3)
		"workspace.diagnostics":
			_bottom.set_workspace_tab(4)
		"raw.copy_layer_id":
			if not selected_layer_id.is_empty():
				_on_copy_layer_id(selected_layer_id)
		_:
			pass


func _on_preset_selected(preset_kind: String, preset_id: String) -> void:
	var source: Array = LayerPresetsScript.building_blocks() if preset_kind == "block" else LayerPresetsScript.effect_templates()
	var preset: Dictionary = {}
	for preset_variant in source:
		if preset_variant is Dictionary and str(preset_variant.get("id", "")) == preset_id:
			preset = preset_variant
			break
	if preset.is_empty():
		return
	var before := model.data.duplicate(true)
	var after_model := VFXDocumentScript.from_dictionary(before)
	var reserved: Dictionary = {}
	var first_layer_id := ""
	for spec_variant in preset.get("layers", []):
		if not spec_variant is Dictionary:
			continue
		var spec: Dictionary = spec_variant
		var prefix := str(spec.get("prefix", spec.get("type", "layer")))
		var layer_id := _next_layer_id(prefix, after_model, reserved)
		if first_layer_id.is_empty():
			first_layer_id = layer_id
		after_model.add_layer(str(spec.get("type", "particle")), layer_id)
		for override_path in spec.get("overrides", {}):
			after_model.set_path("layers." + layer_id + "." + str(override_path), spec["overrides"][override_path], false)
	if not first_layer_id.is_empty():
		selected_layer_id = first_layer_id
	_apply_snapshot_action(before, after_model.data, "Apply preset " + str(preset.get("label", preset_id)))
	_show_toast("Applied " + str(preset.get("label", preset_id)))


func _next_layer_id(prefix: String, document: VFXDocument, reserved: Dictionary) -> String:
	var index := 1
	while document.get_layer(prefix + "_" + str(index)).is_empty() == false or reserved.has(prefix + "_" + str(index)):
		index += 1
	var candidate := prefix + "_" + str(index)
	reserved[candidate] = true
	return candidate


func _refresh_diagnostics() -> void:
	if model == null or _bottom == null:
		return
	_bottom.set_diagnostics(_build_diagnostics_entries())


func _build_diagnostics_entries() -> Array:
	var entries: Array = []
	if model == null:
		return entries
	var validation := model.basic_validation()
	for error_variant in validation.get("errors", []):
		if not error_variant is Dictionary:
			continue
		var error: Dictionary = error_variant
		var path := str(error.get("path", ""))
		entries.append({
			"severity": "error",
			"title": str(error.get("code", "ERROR")),
			"message": str(error.get("message", "")),
			"path": path,
			"layer_id": _layer_id_from_path(path),
		})
	for warning_variant in validation.get("warnings", []):
		if not warning_variant is Dictionary:
			continue
		var warning: Dictionary = warning_variant
		var path := str(warning.get("path", ""))
		entries.append({
			"severity": "warning",
			"title": str(warning.get("code", "WARNING")),
			"message": str(warning.get("message", "")),
			"path": path,
			"layer_id": _layer_id_from_path(path),
		})
	var particles := 0
	var draws := 0
	for layer_variant in model.data.get("layers", []):
		if not layer_variant is Dictionary or not layer_variant.get("enabled", true):
			continue
		var layer: Dictionary = layer_variant
		var layer_type := str(layer.get("type", ""))
		if layer_type in ["particle", "mesh_particle"]:
			particles += int(layer.get("properties", {}).get("amount", 0))
			draws += 1
		elif layer_type in ["sprite", "light", "trail", "beam", "decal", "mesh_effect"]:
			draws += 1
	if particles > 512:
		entries.append({
			"severity": "warning",
			"title": "Particle budget",
			"message": "~%d particles exceeds the 512 particle soft budget." % particles,
			"path": "layers",
			"layer_id": "",
		})
	if draws > 12:
		entries.append({
			"severity": "warning",
			"title": "Draw budget",
			"message": "~%d draw calls exceeds the 12 draw soft budget." % draws,
			"path": "layers",
			"layer_id": "",
		})
	return entries


func _layer_id_from_path(path: String) -> String:
	if not path.begins_with("layers."):
		return ""
	var parts := path.split(".")
	return parts[1] if parts.size() >= 2 else ""


func _save_layout_state() -> void:
	if not is_instance_valid(main_split) or not is_instance_valid(content_split) or not is_instance_valid(editor_split) or not is_instance_valid(_bottom):
		return
	var stage_preset := "mmo_combat"
	var backdrop_index := 0
	var camera_index := 0
	var speed_index := 2
	if is_instance_valid(_viewport_panel):
		var stage_index := _viewport_panel.stage_menu.selected
		if stage_index >= 0 and stage_index < PreviewStageScript.PRESET_IDS.size():
			stage_preset = PreviewStageScript.PRESET_IDS[stage_index]
		backdrop_index = _viewport_panel.backdrop_menu.selected
		camera_index = _viewport_panel.camera_menu.selected
	if is_instance_valid(speed_menu):
		speed_index = speed_menu.selected
	LayoutPersistenceScript.save_state({
		"main_split": main_split.split_offset,
		"content_split": content_split.split_offsets[0] if content_split.split_offsets.size() > 0 else 175,
		"editor_split": editor_split.split_offset,
		"workspace_tab": _bottom.workspace_tabs.current_tab,
		"stage_preset": stage_preset,
		"grid_visible": _viewport_panel.grid_button.button_pressed if is_instance_valid(_viewport_panel) else true,
		"bounds_visible": _show_bounds_overlay,
		"backdrop_index": backdrop_index,
		"camera_index": camera_index,
		"playback_speed_index": speed_index,
		"panels": _panel_visibility.duplicate(),
	})
