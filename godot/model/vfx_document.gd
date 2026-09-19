class_name VFXDocument
extends RefCounted

signal changed
signal dirty_changed(is_dirty: bool)

const CURRENT_SCHEMA: int = 1
var data: Dictionary = {}
var source_path: String = ""
var is_dirty: bool = false
var load_error: Dictionary = {}


static func create(effect_id: String, display_name: String, duration: float = 1.0, loop: bool = false, seed: int = 12345) -> VFXDocument:
    var model := VFXDocument.new()
    model.data = {
        "schema_version": CURRENT_SCHEMA,
        "id": effect_id,
        "name": display_name,
        "duration": duration,
        "loop": loop,
        "seed": seed,
        "metadata": {"author": "", "description": "", "created_with": "VFX Forge Godot editor", "notes": ""},
        "tags": [],
        "layers": [],
        "dependencies": {"textures": [], "meshes": [], "effects": []},
        "timeline": {"events": [], "snap": 0.05},
        "camera_presets": {
            "front": {"position": [0.0, 1.2, 5.0], "target": [0.0, 0.8, 0.0], "fov": 45.0},
            "mmo": {"position": [4.5, 4.0, 5.5], "target": [0.0, 0.7, 0.0], "fov": 50.0},
            "top": {"position": [0.0, 6.0, 0.0], "target": [0.0, 0.0, 0.0], "fov": 45.0}
        },
        "budgets": {"profile": "Medium", "custom": {}},
        "export": {"godot_version": "4.x", "folder_name": effect_id, "include_metadata": true, "embed_document": true, "copy_textures": true, "copy_meshes": true}
    }
    return model


static func from_dictionary(value: Dictionary, path: String = "") -> VFXDocument:
    var model := VFXDocument.new()
    model.data = _normalize(value)
    model.source_path = path
    return model


static func load_file(path: String) -> VFXDocument:
    if not FileAccess.file_exists(path):
        return create("untitled_effect", "Untitled Effect")
    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        var unreadable := VFXDocument.new()
        unreadable.source_path = path
        unreadable.load_error = {"code": "FILE_READ", "message": "Could not read the selected VFX document."}
        return unreadable
    var parsed: Variant = JSON.parse_string(file.get_as_text())
    if parsed == null:
        var malformed := VFXDocument.new()
        malformed.source_path = path
        malformed.load_error = {"code": "INVALID_JSON", "message": "The selected file is not valid JSON."}
        return malformed
    if not parsed is Dictionary:
        var invalid_root := VFXDocument.new()
        invalid_root.source_path = path
        invalid_root.load_error = {"code": "INVALID_ROOT", "message": "The VFX document root must be a JSON object."}
        return invalid_root
    var model := from_dictionary(parsed, path)
    var schema_value: Variant = parsed.get("schema_version", 0)
    if schema_value is int and not schema_value is bool and int(schema_value) > CURRENT_SCHEMA:
        model.load_error = {"code": "FUTURE_SCHEMA", "message": "This document uses a newer schema than this VFX Forge build supports."}
    return model


static func make_layer(layer_type: String, layer_id: String) -> Dictionary:
    var layer := {
        "id": layer_id,
        "type": layer_type,
        "name": layer_id.capitalize(),
        "enabled": true,
        "start": 0.0,
        "duration": 1.0,
        "properties": {},
        "material": {
            "blend_mode": "additive",
            "unshaded": true,
            "billboard": "enabled",
            "depth_draw": "always",
            "texture": "",
            "tint": "#FFFFFFFF",
            "uv_scroll": [0.0, 0.0],
            "distortion": 0.0,
            "dissolve": 0.0,
            "fresnel": 0.0,
            "emissive_intensity": 1.0
        },
        "curves": {},
        "gradient": [
            {"position": 0.0, "color": "#FFFFFFFF"},
            {"position": 1.0, "color": "#00000000"}
        ]
    }
    match layer_type:
        "particle":
            layer["properties"] = {
                "amount": 32, "one_shot": true, "lifetime": 0.8, "explosiveness": 0.8,
                "randomness": 0.15, "fixed_fps": 0, "local_coords": false, "emission_shape": "point",
                "emission_box_extents": [0.25, 0.25, 0.25], "emission_radius": 0.5, "emission_height": 0.1,
                "direction": [0.0, 1.0, 0.0], "spread": 35.0, "initial_velocity_min": 1.0,
                "initial_velocity_max": 2.0, "gravity": [0.0, -2.0, 0.0], "damping": 0.0,
                "radial_accel": 0.0, "tangential_accel": 0.0, "turbulence": 0.0,
                "attractor_strength": 0.0, "attractor_position": [0.0, 0.0, 0.0],
                "scale_min": 0.08, "scale_max": 0.16, "rotation_min": 0.0, "rotation_max": 360.0,
                "angular_velocity_min": -90.0, "angular_velocity_max": 90.0, "texture": ""
            }
            layer["curves"] = {
                "scale": {"interpolation": "linear", "points": [{"x": 0.0, "y": 0.35}, {"x": 0.15, "y": 1.0}, {"x": 1.0, "y": 0.0}]},
                "alpha": {"interpolation": "linear", "points": [{"x": 0.0, "y": 0.0}, {"x": 0.1, "y": 1.0}, {"x": 0.75, "y": 1.0}, {"x": 1.0, "y": 0.0}]}
            }
        "sprite":
            layer["properties"] = {"texture": "", "size": [1.0, 1.0], "flipbook_columns": 1, "flipbook_rows": 1, "flipbook_frames": 1, "flipbook_fps": 12.0, "flipbook_loop": false, "flipbook_start_frame": 0, "random_start": false, "billboard": "enabled"}
            layer["curves"] = {"scale": {"interpolation": "linear", "points": [{"x": 0.0, "y": 0.5}, {"x": 0.15, "y": 1.0}, {"x": 1.0, "y": 0.0}]}}
        "light":
            layer["properties"] = {"color": "#8A7CFFFF", "energy": 2.0, "range": 3.0, "shadow_enabled": false, "fade": true}
            layer["curves"] = {"energy": {"interpolation": "linear", "points": [{"x": 0.0, "y": 0.0}, {"x": 0.12, "y": 1.0}, {"x": 0.7, "y": 0.55}, {"x": 1.0, "y": 0.0}]}}
        "trail":
            layer["properties"] = {"width": 0.18, "lifetime": 0.35, "segments": 16, "color": "#9C8CFFFF", "alpha": 1.0, "uv_mode": "stretch", "texture": "", "target": "self"}
            layer["curves"] = {"width": {"interpolation": "linear", "points": [{"x": 0.0, "y": 1.0}, {"x": 1.0, "y": 0.0}]}}
        "beam":
            layer["properties"] = {"source": [0.0, 0.0, 0.0], "target": [0.0, 0.0, -4.0], "thickness": 0.12, "segments": 12, "noise": 0.08, "scroll_speed": 1.0, "fade": 1.0, "color": "#8FC8FFFF", "texture": ""}
            layer["curves"] = {"width": {"interpolation": "linear", "points": [{"x": 0.0, "y": 0.0}, {"x": 0.12, "y": 1.0}, {"x": 0.85, "y": 1.0}, {"x": 1.0, "y": 0.0}]}}
        "decal":
            layer["properties"] = {"texture": "", "size": [2.0, 2.0], "color": "#5D48B6B8", "height": 0.02, "fade": true, "rotate": 0.0}
            layer["curves"] = {"scale": {"interpolation": "linear", "points": [{"x": 0.0, "y": 0.0}, {"x": 0.2, "y": 1.0}, {"x": 1.0, "y": 0.8}]}}
        "mesh_effect":
            layer["properties"] = {"mesh": "sphere", "mesh_asset": "", "size": [1.0, 1.0, 1.0], "rotation": [0.0, 0.0, 0.0], "rotation_speed": [0.0, 45.0, 0.0], "dissolve": 0.0, "pulse": 0.0, "color": "#8E79FFFF"}
            layer["curves"] = {"scale": {"interpolation": "linear", "points": [{"x": 0.0, "y": 0.2}, {"x": 0.18, "y": 1.0}, {"x": 1.0, "y": 0.8}]}, "alpha": {"interpolation": "linear", "points": [{"x": 0.0, "y": 0.0}, {"x": 0.1, "y": 1.0}, {"x": 0.8, "y": 1.0}, {"x": 1.0, "y": 0.0}]}}
        "audio_marker":
            layer["properties"] = {"event_id": "vfx.impact", "volume": 1.0, "pitch": 1.0, "pitch_variation": 0.0}
        "event_marker":
            layer["properties"] = {"event_id": "impact", "payload": {}}
        "child_effect":
            layer["properties"] = {"effect_id": "", "trigger": "on_start", "offset": [0.0, 0.0, 0.0], "inherit_transform": true, "max_instances": 8}
        "mesh_particle":
            layer["properties"] = {"amount": 24, "one_shot": true, "lifetime": 1.0, "mesh": "quad", "mesh_asset": "", "emission_shape": "point", "size": [0.15, 0.15, 0.15], "spread": 25.0, "initial_velocity": 1.5, "gravity": [0.0, -1.5, 0.0], "rotation_speed": 90.0}
            layer["curves"] = {"scale": {"interpolation": "linear", "points": [{"x": 0.0, "y": 0.2}, {"x": 0.12, "y": 1.0}, {"x": 1.0, "y": 0.0}]}}
    return layer


func add_layer(layer_type: String, layer_id: String) -> void:
    var layers: Array = data.get("layers", [])
    layers.append(make_layer(layer_type, layer_id))
    data["layers"] = layers
    mark_dirty()


func remove_layer(layer_id: String) -> bool:
    var layers: Array = data.get("layers", [])
    for index in range(layers.size()):
        if layers[index] is Dictionary and layers[index].get("id", "") == layer_id:
            layers.remove_at(index)
            data["layers"] = layers
            mark_dirty()
            return true
    return false


func get_layer(layer_id: String) -> Dictionary:
    for layer_variant in data.get("layers", []):
        if layer_variant is Dictionary and layer_variant.get("id", "") == layer_id:
            return layer_variant
    return {}


func get_path(path: String) -> Variant:
    var tokens := path.split(".")
    if tokens.size() >= 2 and tokens[0] == "layers":
        var layer := get_layer(tokens[1])
        if layer.is_empty():
            return null
        var current: Variant = layer
        for index in range(2, tokens.size()):
            var token := tokens[index]
            if index == 2 and not current.has(token) and current.get("properties", {}).has(token):
                current = current["properties"]
            if current is Dictionary:
                current = current.get(token)
            else:
                return null
        return current
    var value: Variant = data
    for token in tokens:
        if value is Dictionary:
            value = value.get(token)
        else:
            return null
    return value


func set_path(path: String, value: Variant, mark: bool = true) -> bool:
    var tokens := path.split(".")
    if tokens.is_empty():
        return false
    var current: Variant = data
    if tokens.size() >= 3 and tokens[0] == "layers":
        current = get_layer(tokens[1])
        if current.is_empty():
            return false
        tokens = tokens.slice(2)
        if not current.has(tokens[0]) and current.get("properties", {}).has(tokens[0]):
            current = current["properties"]
    for index in range(tokens.size() - 1):
        var token := tokens[index]
        if current is Dictionary:
            if not current.has(token):
                current[token] = {}
            current = current[token]
        else:
            return false
    if current is Dictionary:
        current[tokens[tokens.size() - 1]] = value
        if mark:
            mark_dirty()
        return true
    return false


func mark_dirty() -> void:
    if not is_dirty:
        is_dirty = true
        dirty_changed.emit(true)
    changed.emit()


func clear_dirty() -> void:
    if is_dirty:
        is_dirty = false
        dirty_changed.emit(false)


func save_atomic(path: String = source_path) -> bool:
    if path.is_empty() or not load_error.is_empty():
        return false
    var validation := basic_validation()
    if not bool(validation.get("valid", false)):
        return false
    var resolved_path: String = ProjectSettings.globalize_path(path) if path.begins_with("res://") else path
    var directory := resolved_path.get_base_dir()
    DirAccess.make_dir_recursive_absolute(directory)
    var serialized := JSON.stringify(data, "\t") + "\n"
    var temporary := resolved_path + ".tmp"
    var file := FileAccess.open(temporary, FileAccess.WRITE)
    if file == null:
        return false
    file.store_string(serialized)
    file.flush()
    if FileAccess.file_exists(resolved_path):
        DirAccess.copy_absolute(resolved_path, resolved_path + ".bak")
    var renamed := DirAccess.rename_absolute(temporary, resolved_path) == OK
    if not renamed:
        # Never remove the last known-good document just to force a replace.
        DirAccess.remove_absolute(temporary)
        return false
    if renamed:
        source_path = path
        clear_dirty()
    return renamed


func autosave() -> bool:
    if source_path.is_empty():
        return false
    var original_path := source_path
    var was_dirty := is_dirty
    var success := save_atomic(original_path + ".autosave")
    source_path = original_path
    if was_dirty and success:
        is_dirty = true
        dirty_changed.emit(true)
    return success


func basic_validation() -> Dictionary:
    var errors: Array[Dictionary] = []
    var warnings: Array[Dictionary] = []
    var schema_value: Variant = data.get("schema_version", 0)
    if not schema_value is int or schema_value is bool:
        errors.append({"code": "INVALID_SCHEMA_VERSION", "path": "schema_version", "message": "schema_version must be an integer."})
    elif int(schema_value) > CURRENT_SCHEMA:
        errors.append({"code": "FUTURE_SCHEMA", "path": "schema_version", "message": "This document uses a newer schema than this VFX Forge build supports."})
    elif int(schema_value) != CURRENT_SCHEMA:
        errors.append({"code": "INVALID_SCHEMA_VERSION", "path": "schema_version", "message": "Unsupported schema version."})
    if str(data.get("id", "")).is_empty():
        errors.append({"code": "MISSING_ID", "path": "id", "message": "Effect ID is required."})
    if float(data.get("duration", 0.0)) <= 0.0:
        errors.append({"code": "INVALID_DURATION", "path": "duration", "message": "Duration must be greater than zero."})
    if not data.get("layers", []) is Array:
        errors.append({"code": "INVALID_LAYERS", "path": "layers", "message": "Layers must be an array."})
        return {"valid": false, "errors": errors, "warnings": warnings}
    var ids: Dictionary = {}
    for layer_variant in data.get("layers", []):
        if not layer_variant is Dictionary:
            errors.append({"code": "INVALID_LAYER", "path": "layers", "message": "Layer must be an object."})
            continue
        var layer: Dictionary = layer_variant
        var layer_id := str(layer.get("id", ""))
        if layer_id.is_empty():
            errors.append({"code": "INVALID_LAYER_ID", "path": "layers", "message": "Layer IDs are required."})
        elif ids.has(layer_id):
            errors.append({"code": "DUPLICATE_LAYER_ID", "path": "layers." + layer_id, "message": "Layer ID is duplicated."})
        ids[layer_id] = true
        if float(layer.get("duration", 0.0)) <= 0.0:
            errors.append({"code": "INVALID_LAYER_DURATION", "path": "layers." + layer_id + ".duration", "message": "Layer duration must be positive."})
        if float(layer.get("start", 0.0)) + float(layer.get("duration", 0.0)) > float(data.get("duration", 0.0)):
            warnings.append({"code": "LAYER_OUTSIDE_DURATION", "path": "layers." + layer_id, "message": "Layer ends after effect duration."})
    return {"valid": errors.is_empty(), "errors": errors, "warnings": warnings}


static func _normalize(value: Dictionary) -> Dictionary:
    var normalized := value.duplicate(true)
    var has_schema := value.has("schema_version")
    var schema_value: Variant = value.get("schema_version", 0)
    if has_schema and (not schema_value is int or schema_value is bool):
        return normalized
    if has_schema and int(schema_value) > CURRENT_SCHEMA:
        return normalized
    normalized["schema_version"] = CURRENT_SCHEMA
    if not normalized.has("metadata"):
        normalized["metadata"] = {}
    if not normalized.has("tags"):
        normalized["tags"] = []
    if not normalized.has("layers"):
        normalized["layers"] = []
    if not normalized.has("dependencies"):
        normalized["dependencies"] = {"textures": [], "meshes": [], "effects": []}
    elif normalized["dependencies"] is Dictionary and not normalized["dependencies"].has("meshes"):
        normalized["dependencies"]["meshes"] = []
    if not normalized.has("timeline"):
        normalized["timeline"] = {"events": [], "snap": 0.05}
    if not normalized.has("camera_presets"):
        normalized["camera_presets"] = {}
    if not normalized.has("budgets"):
        normalized["budgets"] = {"profile": "Medium", "custom": {}}
    if not normalized.has("export"):
        normalized["export"] = {"godot_version": "4.x", "folder_name": str(normalized.get("id", "effect")), "include_metadata": true, "embed_document": true, "copy_textures": true, "copy_meshes": true}
    elif normalized["export"] is Dictionary and not normalized["export"].has("copy_meshes"):
        normalized["export"]["copy_meshes"] = true
    return normalized
