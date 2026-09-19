extends SceneTree

const DocumentScript = preload("res://godot/model/vfx_document.gd")


func _argument_value(args: PackedStringArray, key: String, default_value: String = "") -> String:
    var index := args.find(key)
    if index >= 0 and index + 1 < args.size():
        return args[index + 1]
    return default_value


func _fail(message: String) -> void:
    push_error(message)
    quit(5)


func _initialize() -> void:
    var args := OS.get_cmdline_user_args()
    var screenshot_path := _argument_value(args, "--screenshot", "docs/assets/vfx-forge-ui.png")

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
    main.runtime.seek(0.85)
    main._on_reset_view_pressed()
    await process_frame
    await process_frame
    await process_frame

    var absolute_path := ProjectSettings.globalize_path(screenshot_path)
    var directory := absolute_path.get_base_dir()
    var dir_error := DirAccess.make_dir_recursive_absolute(directory)
    if dir_error != OK:
        _fail("Could not create screenshot directory: %s" % directory)
        return

    var image := get_root().get_texture().get_image()
    var save_error := image.save_png(absolute_path)
    if save_error != OK:
        _fail("Could not save screenshot to %s (error %d)" % [absolute_path, save_error])
        return

    print("GUI_SCREENSHOT_PASS path=%s size=%dx%d" % [absolute_path, image.get_width(), image.get_height()])
    quit(0)
