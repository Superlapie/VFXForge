class_name VFXRuntime
extends Node3D

signal playback_changed(is_playing: bool)
signal time_changed(time: float, duration: float)
signal runtime_warning(message: String)
signal event_triggered(event_id: String, time: float)

var document: Dictionary = {}
var elapsed: float = 0.0
var playback_speed: float = 1.0
var is_playing: bool = false
var child_depth: int = 0
var asset_root: String = "res://"
var runtime_script_path: String = "res://vfx_runtime.gd"
var trail_script_path: String = "res://godot/runtime/vfx_trail.gd"
var generated_nodes: Array[Node] = []
var beam_nodes: Array[MeshInstance3D] = []
var editor_solo_layer_id: String = ""
var editor_selected_layer_id: String = ""
var _fired_events: Dictionary = {}


func set_document(value: Dictionary, asset_base: String = "") -> void:
    document = value.duplicate(true)
    asset_root = asset_base if not asset_base.is_empty() else "res://"
    rebuild()


func get_document() -> Dictionary:
    return document.duplicate(true)


func rebuild() -> void:
    for node in generated_nodes:
        if is_instance_valid(node):
            # Rebuilds happen during authoring edits. Free synchronously so the
            # replacement keeps the canonical layer ID instead of receiving a
            # temporary Godot-generated suffix while the old node is queued.
            node.free()
    generated_nodes.clear()
    beam_nodes.clear()
    if not document.has("layers") or not document["layers"] is Array:
        return
    for layer_variant in document["layers"]:
        if not layer_variant is Dictionary:
            continue
        var layer: Dictionary = layer_variant
        if not bool(layer.get("enabled", true)):
            continue
        var created: Node = _create_layer(layer)
        if created != null:
            created.set_meta("vfx_layer", layer)
            add_child(created)
            generated_nodes.append(created)
            if layer.get("type", "") == "beam":
                beam_nodes.append(created as MeshInstance3D)
    _update_runtime(0.0)


func play() -> void:
    is_playing = true
    playback_changed.emit(true)


func pause() -> void:
    is_playing = false
    playback_changed.emit(false)


func stop() -> void:
    is_playing = false
    elapsed = 0.0
    _fired_events.clear()
    _update_runtime(elapsed)
    playback_changed.emit(false)
    time_changed.emit(elapsed, _duration())


func restart() -> void:
    elapsed = 0.0
    _fired_events.clear()
    is_playing = true
    _update_runtime(elapsed)
    playback_changed.emit(true)


func seek(time: float) -> void:
    elapsed = clamp(time, 0.0, _duration())
    _fired_events.clear()
    _update_runtime(elapsed)
    time_changed.emit(elapsed, _duration())


func set_editor_selection(layer_id: String) -> void:
    editor_selected_layer_id = layer_id
    _apply_editor_selection()


func set_editor_solo(layer_id: String) -> void:
    editor_solo_layer_id = layer_id
    _update_runtime(elapsed)


func _apply_editor_selection() -> void:
    for node in generated_nodes:
        if not is_instance_valid(node):
            continue
        var layer_variant: Variant = node.get_meta("vfx_layer", {})
        if not layer_variant is Dictionary:
            continue
        var layer_id := str(layer_variant.get("id", ""))
        var selected: bool = layer_id == editor_selected_layer_id and not editor_selected_layer_id.is_empty()
        if node is MeshInstance3D:
            var mesh_instance := node as MeshInstance3D
            mesh_instance.set_meta("editor_selected", selected)
    _update_runtime(elapsed)


func _process(delta: float) -> void:
    if is_playing:
        elapsed += delta * playback_speed
        var duration := _duration()
        if elapsed >= duration:
            if bool(document.get("loop", false)):
                elapsed = fmod(elapsed, duration)
                _fired_events.clear()
            else:
                elapsed = duration
                is_playing = false
                playback_changed.emit(false)
        _update_runtime(elapsed)
        time_changed.emit(elapsed, duration)


func _duration() -> float:
    var value: Variant = document.get("duration", 1.0)
    return maxf(0.001, float(value) if value is float or value is int else 1.0)


func _emit_timeline_events(time: float) -> void:
    var timeline: Variant = document.get("timeline", {})
    if not timeline is Dictionary:
        return
    var events: Variant = timeline.get("events", [])
    if not events is Array:
        return
    for event_variant in events:
        if not event_variant is Dictionary:
            continue
        var event: Dictionary = event_variant
        var stable_id := str(event.get("id", event.get("event_id", "")))
        var event_id := str(event.get("event_id", stable_id))
        if stable_id.is_empty() or _fired_events.get(stable_id, false):
            continue
        if time + 0.0001 >= float(event.get("time", 0.0)):
            _fired_events[stable_id] = true
            event_triggered.emit(event_id, time)
    for node in generated_nodes:
        if not is_instance_valid(node):
            continue
        var layer_variant: Variant = node.get_meta("vfx_layer", {})
        if not layer_variant is Dictionary:
            continue
        var layer: Dictionary = layer_variant
        if str(layer.get("type", "")) != "event_marker":
            continue
        var marker_id := str(_properties(layer).get("event_id", layer.get("id", "")))
        if marker_id.is_empty() or _fired_events.get(marker_id, false):
            continue
        if time + 0.0001 >= float(layer.get("start", 0.0)):
            _fired_events[marker_id] = true
            event_triggered.emit(marker_id, time)


func _create_layer(layer: Dictionary) -> Node:
    var layer_type := str(layer.get("type", ""))
    match layer_type:
        "particle":
            return _create_particle(layer, false)
        "mesh_particle":
            return _create_particle(layer, true)
        "sprite":
            return _create_card(layer)
        "light":
            return _create_light(layer)
        "trail":
            return _create_trail(layer)
        "beam":
            return _create_beam(layer)
        "decal":
            return _create_decal(layer)
        "mesh_effect":
            return _create_mesh_effect(layer)
        "child_effect":
            return _create_child_effect(layer)
        "audio_marker", "event_marker":
            return _create_marker(layer)
        _:
            runtime_warning.emit("Unsupported layer type: " + layer_type)
            return null


func _properties(layer: Dictionary) -> Dictionary:
    var value: Variant = layer.get("properties", {})
    return value if value is Dictionary else {}


func _create_particle(layer: Dictionary, use_mesh: bool) -> GPUParticles3D:
    var properties := _properties(layer)
    var particles := GPUParticles3D.new()
    particles.name = str(layer.get("id", "particle"))
    particles.amount = max(0, int(properties.get("amount", 32)))
    particles.lifetime = max(0.02, float(properties.get("lifetime", 0.8)))
    particles.one_shot = bool(properties.get("one_shot", true))
    particles.explosiveness = clamp(float(properties.get("explosiveness", 0.0)), 0.0, 1.0)
    particles.randomness = clamp(float(properties.get("randomness", 0.0)), 0.0, 1.0)
    particles.local_coords = bool(properties.get("local_coords", false))
    var fixed_fps := int(properties.get("fixed_fps", 0))
    if fixed_fps > 0:
        particles.fixed_fps = fixed_fps
    particles.visibility_aabb = AABB(Vector3(-20, -20, -20), Vector3(40, 40, 40))
    var process_material := ParticleProcessMaterial.new()
    var shape := str(properties.get("emission_shape", "point"))
    var shape_mapping := _resolve_particle_emission_shape(shape, properties)
    if int(shape_mapping.get("code", -1)) < 0:
        runtime_warning.emit("Unsupported particle emission shape: " + shape)
        return null
    process_material.set("emission_shape", int(shape_mapping["code"]))
    if shape_mapping.has("extents"):
        process_material.set("emission_box_extents", shape_mapping["extents"])
    else:
        process_material.set("emission_box_extents", _vec3(properties.get("emission_box_extents", [0.25, 0.25, 0.25])))
    process_material.set("emission_sphere_radius", float(shape_mapping.get("radius", properties.get("emission_radius", 0.5))))
    process_material.set("emission_ring_radius", float(shape_mapping.get("radius", properties.get("emission_radius", 0.5))))
    process_material.set("emission_ring_height", float(shape_mapping.get("height", properties.get("emission_height", 0.1))))
    process_material.set("direction", _vec3(shape_mapping.get("direction", properties.get("direction", [0.0, 1.0, 0.0]))))
    var spread := float(properties.get("spread", 35.0))
    if shape_mapping.get("spread_boost", false):
        spread = max(spread, 55.0)
    process_material.set("spread", spread)
    process_material.set("initial_velocity_min", float(properties.get("initial_velocity_min", properties.get("initial_velocity", 1.0))))
    process_material.set("initial_velocity_max", float(properties.get("initial_velocity_max", properties.get("initial_velocity", 1.0))))
    process_material.set("gravity", _vec3(properties.get("gravity", [0.0, -2.0, 0.0])))
    process_material.set("damping_min", float(properties.get("damping", 0.0)))
    process_material.set("damping_max", float(properties.get("damping", 0.0)))
    process_material.set("radial_accel_min", float(properties.get("radial_accel", 0.0)))
    process_material.set("radial_accel_max", float(properties.get("radial_accel", 0.0)))
    process_material.set("tangential_accel_min", float(properties.get("tangential_accel", 0.0)))
    process_material.set("tangential_accel_max", float(properties.get("tangential_accel", 0.0)))
    process_material.set("scale_min", float(properties.get("scale_min", 0.08)))
    process_material.set("scale_max", float(properties.get("scale_max", 0.16)))
    process_material.set("angle_min", float(properties.get("rotation_min", 0.0)))
    process_material.set("angle_max", float(properties.get("rotation_max", 360.0)))
    process_material.set("angular_velocity_min", float(properties.get("angular_velocity_min", -90.0)))
    process_material.set("angular_velocity_max", float(properties.get("angular_velocity_max", 90.0)))
    process_material.set("anim_offset_min", float(properties.get("flipbook_start_frame", 0)) / max(1.0, float(properties.get("flipbook_frames", 1))))
    process_material.set("anim_offset_max", float(properties.get("flipbook_start_frame", 0)) / max(1.0, float(properties.get("flipbook_frames", 1))))
    process_material.set("anim_speed_min", float(properties.get("flipbook_fps", 12.0)))
    process_material.set("anim_speed_max", float(properties.get("flipbook_fps", 12.0)))
    process_material.set("anim_loop", bool(properties.get("flipbook_loop", false)))
    var layer_curves: Variant = layer.get("curves", {})
    if layer_curves is Dictionary:
        var scale_curve: Variant = layer_curves.get("scale", {})
        if scale_curve is Dictionary and scale_curve.get("points", []) is Array and not scale_curve.get("points", []).is_empty():
            process_material.scale_curve = _curve_texture(scale_curve)
        var alpha_curve: Variant = layer_curves.get("alpha", {})
        if alpha_curve is Dictionary and alpha_curve.get("points", []) is Array and not alpha_curve.get("points", []).is_empty():
            process_material.color_ramp = _alpha_curve_texture(alpha_curve)
        else:
            process_material.set("color_ramp", _gradient_texture(layer.get("gradient", [])))
        var velocity_curve: Variant = layer_curves.get("velocity", {})
        if velocity_curve is Dictionary and velocity_curve.get("points", []) is Array and not velocity_curve.get("points", []).is_empty():
            var velocity_scale := _curve_value(velocity_curve, 0.5, 1.0)
            process_material.set("initial_velocity_min", float(properties.get("initial_velocity_min", properties.get("initial_velocity", 1.0))) * velocity_scale)
            process_material.set("initial_velocity_max", float(properties.get("initial_velocity_max", properties.get("initial_velocity", 1.0))) * velocity_scale)
    else:
        process_material.set("color_ramp", _gradient_texture(layer.get("gradient", [])))
    particles.process_material = process_material
    var particle_material := _material(layer)
    if use_mesh:
        var custom_mesh := _load_mesh(str(properties.get("mesh_asset", "")))
        if custom_mesh != null:
            particles.draw_pass_1 = custom_mesh
            if custom_mesh is ArrayMesh:
                var array_mesh := custom_mesh as ArrayMesh
                for surface_index in range(array_mesh.get_surface_count()):
                    array_mesh.surface_set_material(surface_index, particle_material)
        else:
            var size := _vec3(properties.get("size", [0.15, 0.15, 0.15]))
            var box := BoxMesh.new()
            box.size = size
            box.material = particle_material
            particles.draw_pass_1 = box
    else:
        var quad := QuadMesh.new()
        var size2 := _vec2(properties.get("size", [0.16, 0.16]))
        quad.size = size2
        quad.material = particle_material
        particles.draw_pass_1 = quad
    return particles


func _resolve_billboard_mode(layer: Dictionary) -> int:
    var settings: Dictionary = layer.get("material", {}) if layer.get("material", {}) is Dictionary else {}
    var mode := str(settings.get("billboard", "enabled"))
    return {
        "disabled": BaseMaterial3D.BILLBOARD_DISABLED,
        "enabled": BaseMaterial3D.BILLBOARD_ENABLED,
        "y_billboard": BaseMaterial3D.BILLBOARD_FIXED_Y,
        "particle": BaseMaterial3D.BILLBOARD_PARTICLES,
    }.get(mode, BaseMaterial3D.BILLBOARD_ENABLED)


func _create_card(layer: Dictionary) -> Node:
    var properties := _properties(layer)
    var texture_ref := str(properties.get("texture", ""))
    var texture := _load_texture(texture_ref) if not texture_ref.is_empty() else null
    if texture != null:
        var sprite := Sprite3D.new()
        sprite.name = str(layer.get("id", "sprite"))
        sprite.texture = texture
        var sprite_material := _material(layer)
        sprite_material.vertex_color_use_as_albedo = true
        sprite.billboard = _resolve_billboard_mode(layer)
        sprite.material_override = sprite_material
        var size := _vec2(properties.get("size", [1.0, 1.0]))
        var texture_size := texture.get_size()
        sprite.pixel_size = size.x / max(1.0, texture_size.x)
        var height_scale: float = size.y / maxf(0.001, texture_size.y * sprite.pixel_size)
        sprite.set_meta("vfx_base_scale", Vector3(1.0, height_scale, 1.0))
        var frame_count: int = max(1, int(properties.get("flipbook_frames", 1)))
        if frame_count > 1:
            var columns: int = max(1, int(properties.get("flipbook_columns", 1)))
            var rows: int = max(1, int(properties.get("flipbook_rows", 1)))
            sprite.region_enabled = true
            sprite.region_rect = Rect2(0, 0, texture_size.x / columns, texture_size.y / rows)
            sprite.set_meta("flipbook_columns", columns)
            sprite.set_meta("flipbook_rows", rows)
            sprite.set_meta("flipbook_frames", frame_count)
            sprite.set_meta("flipbook_fps", float(properties.get("flipbook_fps", 12.0)))
            sprite.set_meta("flipbook_loop", bool(properties.get("flipbook_loop", false)))
            sprite.set_meta("flipbook_start_frame", int(properties.get("flipbook_start_frame", 0)))
        return sprite
    var card := MeshInstance3D.new()
    card.name = str(layer.get("id", "sprite"))
    var quad := QuadMesh.new()
    quad.size = _vec2(properties.get("size", [1.0, 1.0]))
    card.mesh = quad
    card.material_override = _material(layer)
    return card


func _create_light(layer: Dictionary) -> OmniLight3D:
    var properties := _properties(layer)
    var light := OmniLight3D.new()
    light.name = str(layer.get("id", "light"))
    light.light_color = _color(properties.get("color", "#8A7CFFFF"))
    light.omni_range = max(0.1, float(properties.get("range", 3.0)))
    light.light_energy = max(0.0, float(properties.get("energy", 1.0)))
    light.shadow_enabled = bool(properties.get("shadow_enabled", false))
    return light


func _create_trail(layer: Dictionary) -> Node:
    var trail_script := load(trail_script_path)
    if trail_script == null:
        runtime_warning.emit("Trail script is unavailable; layer will be skipped.")
        return null
    var trail: Node = trail_script.new()
    trail.name = str(layer.get("id", "trail"))
    var properties := _properties(layer)
    var width_curve: Dictionary = {}
    var layer_curves: Variant = layer.get("curves", {})
    if layer_curves is Dictionary:
        var authored_width: Variant = layer_curves.get("width", {})
        if authored_width is Dictionary:
            width_curve = authored_width
    trail.configure(
        float(properties.get("width", 0.18)),
        float(properties.get("lifetime", 0.35)),
        _color(properties.get("color", "#9C8CFFFF")),
        clampi(int(properties.get("segments", 20)), 2, 64),
        width_curve,
        float(properties.get("alpha", 1.0)),
    )
    var target_ref := str(properties.get("target", ""))
    trail.set("tracking_path", target_ref)
    trail.set("preview_motion", target_ref.is_empty())
    return trail


func _create_beam(layer: Dictionary) -> MeshInstance3D:
    var beam := MeshInstance3D.new()
    beam.name = str(layer.get("id", "beam"))
    beam.material_override = _material(layer)
    return beam


func _create_decal(layer: Dictionary) -> MeshInstance3D:
    var properties := _properties(layer)
    var decal := MeshInstance3D.new()
    decal.name = str(layer.get("id", "decal"))
    var plane := PlaneMesh.new()
    var size := _vec2(properties.get("size", [2.0, 2.0]))
    plane.size = size
    decal.mesh = plane
    decal.rotation_degrees = Vector3(-90.0, float(properties.get("rotate", 0.0)), 0.0)
    decal.position.y = float(properties.get("height", 0.0))
    decal.material_override = _material(layer)
    return decal


func _create_mesh_effect(layer: Dictionary) -> MeshInstance3D:
    var properties := _properties(layer)
    var mesh_instance := MeshInstance3D.new()
    mesh_instance.name = str(layer.get("id", "mesh_effect"))
    var authored_size := _vec3(properties.get("size", [1.0, 1.0, 1.0]))
    var custom_mesh := _load_mesh(str(properties.get("mesh_asset", "")))
    if custom_mesh != null:
        mesh_instance.mesh = custom_mesh
    var mesh_name := str(properties.get("mesh", "sphere"))
    if custom_mesh == null and mesh_name == "box":
        var box := BoxMesh.new()
        box.size = Vector3.ONE
        mesh_instance.mesh = box
    elif custom_mesh == null and mesh_name == "torus":
        var torus := TorusMesh.new()
        torus.inner_radius = 0.35
        torus.outer_radius = 0.8
        mesh_instance.mesh = torus
    elif custom_mesh == null:
        var sphere := SphereMesh.new()
        sphere.radius = 0.5
        sphere.height = 1.0
        mesh_instance.mesh = sphere
    mesh_instance.set_meta("vfx_base_scale", authored_size)
    mesh_instance.material_override = _material(layer)
    return mesh_instance


func _create_child_effect(layer: Dictionary) -> Node:
    var properties := _properties(layer)
    var reference := str(properties.get("effect_id", ""))
    if reference.is_empty():
        runtime_warning.emit("Child effect layer has no effect_id.")
        return Node3D.new()
    if child_depth >= 8:
        runtime_warning.emit("Child effect depth limit reached; possible recursive dependency: " + reference)
        return Node3D.new()
    var path := _asset_path(reference)
    if path.ends_with(".vfx.json"):
        var file := FileAccess.open(path, FileAccess.READ)
        if file == null:
            runtime_warning.emit("Child effect document is missing: " + reference)
            return Node3D.new()
        var parsed: Variant = JSON.parse_string(file.get_as_text())
        var runtime_node := Node3D.new()
        runtime_node.set_script(load(runtime_script_path))
        runtime_node.set("child_depth", child_depth + 1)
        runtime_node.set("runtime_script_path", runtime_script_path)
        runtime_node.set("trail_script_path", trail_script_path)
        if parsed is Dictionary:
            runtime_node.call("set_document", parsed, asset_root)
        return runtime_node
    var packed := load(path)
    if packed is PackedScene:
        return packed.instantiate()
    runtime_warning.emit("Child effect resource is not a scene: " + reference)
    return Node3D.new()


func _create_marker(layer: Dictionary) -> Node3D:
    var marker := Node3D.new()
    marker.name = str(layer.get("id", "marker"))
    if str(layer.get("type", "")) == "event_marker":
        var payload: Variant = _properties(layer).get("payload", {})
        if payload is Dictionary:
            marker.set_meta("event_payload", payload.duplicate(true))
    return marker


func _update_runtime(time: float) -> void:
    var duration := _duration()
    _emit_timeline_events(time)
    for node in generated_nodes:
        if not is_instance_valid(node):
            continue
        var layer_variant: Variant = node.get_meta("vfx_layer", {})
        if not layer_variant is Dictionary:
            continue
        var layer: Dictionary = layer_variant
        var layer_id := str(layer.get("id", ""))
        var start: float = float(layer.get("start", 0.0))
        var layer_duration: float = maxf(0.001, float(layer.get("duration", duration)))
        var local: float = time - start
        var active: bool = local + 0.0001 >= 0.0 and local <= layer_duration + 0.0001
        var solo_ok: bool = editor_solo_layer_id.is_empty() or editor_solo_layer_id == layer_id
        node.visible = active and solo_ok
        if not active:
            continue
        var normalized: float = clamp(local / layer_duration, 0.0, 1.0)
        var properties := _properties(layer)
        if node is OmniLight3D:
            var light := node as OmniLight3D
            var energy_curve: Variant = layer.get("curves", {}).get("energy", {})
            var energy: float = float(properties.get("energy", 1.0)) * _curve_value(energy_curve, normalized, 1.0)
            if bool(properties.get("fade", false)):
                energy *= min(normalized * 4.0, (1.0 - normalized) * 4.0, 1.0)
            light.light_energy = energy
        elif node is Sprite3D:
            var sprite := node as Sprite3D
            var scale_curve: Variant = layer.get("curves", {}).get("scale", {})
            var sprite_scale: float = _curve_value(scale_curve, normalized, 1.0)
            var base_scale_value: Variant = sprite.get_meta("vfx_base_scale", Vector3.ONE)
            var base_scale: Vector3 = base_scale_value if base_scale_value is Vector3 else Vector3.ONE
            sprite.scale = base_scale * sprite_scale
            var sprite_alpha: float = _curve_value(layer.get("curves", {}).get("alpha", {}), normalized, 1.0)
            var sprite_color := _color(properties.get("color", layer.get("material", {}).get("tint", "#FFFFFFFF")))
            sprite_color.a *= sprite_alpha
            sprite.modulate = sprite_color
            if sprite.region_enabled:
                var columns: int = int(sprite.get_meta("flipbook_columns", 1))
                var rows: int = int(sprite.get_meta("flipbook_rows", 1))
                var frames: int = int(sprite.get_meta("flipbook_frames", 1))
                var fps: float = float(sprite.get_meta("flipbook_fps", 12.0))
                var frame: int = int(floor(local * fps)) + int(sprite.get_meta("flipbook_start_frame", 0))
                if bool(sprite.get_meta("flipbook_loop", false)):
                    frame = frame % frames
                else:
                    frame = min(frame, frames - 1)
                var texture_size := sprite.texture.get_size()
                var frame_size := Vector2(texture_size.x / columns, texture_size.y / rows)
                sprite.region_rect = Rect2(Vector2(float(frame % columns) * frame_size.x, float(frame / columns) * frame_size.y), frame_size)
        elif node is MeshInstance3D:
            var mesh_instance := node as MeshInstance3D
            var scale_curve: Variant = layer.get("curves", {}).get("scale", {})
            var scale_value: float = _curve_value(scale_curve, normalized, 1.0)
            var base_scale_value: Variant = mesh_instance.get_meta("vfx_base_scale", Vector3.ONE)
            var base_scale: Vector3 = base_scale_value if base_scale_value is Vector3 else Vector3.ONE
            var selection_scale: float = 1.04 if layer_id == editor_selected_layer_id and not editor_selected_layer_id.is_empty() else 1.0
            mesh_instance.scale = base_scale * scale_value * selection_scale
            if layer.get("type", "") == "mesh_effect":
                var rotation_speed := _vec3(properties.get("rotation_speed", [0.0, 45.0, 0.0]))
                mesh_instance.rotation_degrees = _vec3(properties.get("rotation", [0.0, 0.0, 0.0])) + rotation_speed * local
                var pulse := maxf(0.0, float(properties.get("pulse", 0.0)))
                if pulse > 0.0:
                    var pulse_scale := 1.0 + sin(local * TAU) * pulse
                    mesh_instance.scale *= Vector3.ONE * pulse_scale
            if mesh_instance.material_override is StandardMaterial3D:
                var material := mesh_instance.material_override as StandardMaterial3D
                var alpha: float = _curve_value(layer.get("curves", {}).get("alpha", {}), normalized, 1.0)
                if layer.get("type", "") == "decal" and bool(properties.get("fade", false)):
                    alpha *= min(normalized * 4.0, (1.0 - normalized) * 4.0, 1.0)
                var color := _color(properties.get("color", layer.get("material", {}).get("tint", "#FFFFFFFF")))
                color.a *= alpha
                material.albedo_color = color
                material.emission = Color(color.r, color.g, color.b, 1.0)
        if layer.get("type", "") == "beam" and node is MeshInstance3D:
            _update_beam(node as MeshInstance3D, layer, normalized)


func _update_beam(node: MeshInstance3D, layer: Dictionary, normalized: float) -> void:
    var properties := _properties(layer)
    var source: Vector3 = _vec3(properties.get("source", [0.0, 0.0, 0.0]))
    var target: Vector3 = _vec3(properties.get("target", [0.0, 0.0, -4.0]))
    var segments: int = clamp(int(properties.get("segments", 12)), 2, 64)
    var thickness: float = max(0.01, float(properties.get("thickness", 0.12))) * _curve_value(layer.get("curves", {}).get("width", {}), normalized, 1.0)
    var noise: float = float(properties.get("noise", 0.08))
    var fade: float = clampf(float(properties.get("fade", 0.0)), 0.0, 1.0)
    var scroll_speed: float = float(properties.get("scroll_speed", 0.0))
    var random := RandomNumberGenerator.new()
    random.seed = int(document.get("seed", 0)) + str(layer.get("id", "beam")).hash()
    var mesh := ImmediateMesh.new()
    var material := node.material_override as Material
    if material == null:
        material = _material(layer)
    if material is StandardMaterial3D and scroll_speed != 0.0:
        (material as StandardMaterial3D).uv1_offset = Vector3(normalized * scroll_speed, 0.0, 0.0)
    mesh.surface_begin(Mesh.PRIMITIVE_TRIANGLE_STRIP, material)
    for index in range(segments + 1):
        var ratio := float(index) / float(segments)
        var point := source.lerp(target, ratio)
        var offset := sin(ratio * PI) * noise
        point += Vector3(random.randf_range(-offset, offset), random.randf_range(-offset, offset), random.randf_range(-offset, offset))
        var tangent := (target - source).normalized()
        var side := tangent.cross(Vector3.UP).normalized()
        if side.length_squared() < 0.001:
            side = tangent.cross(Vector3.RIGHT).normalized()
        var edge_fade := 1.0
        if fade > 0.0:
            edge_fade = min(ratio * (1.0 + fade), (1.0 - ratio) * (1.0 + fade), 1.0)
        mesh.surface_set_color(Color(1.0, 1.0, 1.0, edge_fade))
        mesh.surface_set_uv(Vector2(ratio, 0.0))
        mesh.surface_add_vertex(point - side * thickness)
        mesh.surface_set_color(Color(1.0, 1.0, 1.0, edge_fade))
        mesh.surface_set_uv(Vector2(ratio, 1.0))
        mesh.surface_add_vertex(point + side * thickness)
    mesh.surface_end()
    node.mesh = mesh


func _material(layer: Dictionary) -> StandardMaterial3D:
    var settings: Dictionary = layer.get("material", {}) if layer.get("material", {}) is Dictionary else {}
    var material := StandardMaterial3D.new()
    material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED if bool(settings.get("unshaded", true)) else BaseMaterial3D.SHADING_MODE_PER_PIXEL
    material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
    var blend := str(settings.get("blend_mode", "additive"))
    material.blend_mode = {
        "additive": BaseMaterial3D.BLEND_MODE_ADD,
        "alpha": BaseMaterial3D.BLEND_MODE_MIX,
        "premultiplied": BaseMaterial3D.BLEND_MODE_PREMULT_ALPHA,
        "multiply": BaseMaterial3D.BLEND_MODE_MUL
    }.get(blend, BaseMaterial3D.BLEND_MODE_ADD)
    material.billboard_mode = _resolve_billboard_mode(layer)
    if str(layer.get("type", "")) in ["particle", "mesh_particle"]:
        material.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
        material.vertex_color_use_as_albedo = true
    elif str(layer.get("type", "")) == "beam":
        material.vertex_color_use_as_albedo = true
    material.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_ALWAYS
    var property_color: Variant = _properties(layer).get("color", "")
    var tint_reference: Variant = property_color if property_color is String and not str(property_color).is_empty() else settings.get("tint", "#FFFFFFFF")
    var tint := _color(tint_reference)
    material.albedo_color = tint
    material.emission_enabled = true
    material.emission = Color(tint.r, tint.g, tint.b, 1.0)
    material.emission_energy_multiplier = max(0.0, float(settings.get("emissive_intensity", 1.0)))
    var texture_ref := str(settings.get("texture", ""))
    if texture_ref.is_empty():
        texture_ref = str(_properties(layer).get("texture", ""))
    if not texture_ref.is_empty():
        var texture := _load_texture(texture_ref)
        if texture != null:
            material.albedo_texture = texture
    elif str(layer.get("type", "")) in ["sprite", "particle"]:
        material.albedo_texture = _radial_glow_texture(tint)
    return material


func _radial_glow_texture(tint: Color) -> GradientTexture2D:
    var gradient := Gradient.new()
    gradient.set_color(0, Color(tint.r, tint.g, tint.b, 1.0))
    gradient.set_color(1, Color(tint.r, tint.g, tint.b, 0.0))
    var texture := GradientTexture2D.new()
    texture.gradient = gradient
    texture.width = 128
    texture.height = 128
    texture.fill = GradientTexture2D.FILL_RADIAL
    texture.fill_from = Vector2(0.5, 0.5)
    texture.fill_to = Vector2(1.0, 0.5)
    return texture


func _load_texture(reference: String) -> Texture2D:
    var path := _asset_path(reference)
    var resource: Variant = load(path)
    if resource is Texture2D:
        return resource
    var image := Image.new()
    var filesystem_path := ProjectSettings.globalize_path(path)
    if image.load(filesystem_path) == OK:
        return ImageTexture.create_from_image(image)
    return null


func _load_mesh(reference: String) -> Mesh:
    if reference.is_empty():
        return null
    var path := _asset_path(reference)
    var resource: Resource = load(path)
    if resource == null:
        runtime_warning.emit("Mesh asset could not be loaded: " + reference)
        return null
    if resource is Mesh:
        return resource.duplicate() as Mesh
    if resource is PackedScene:
        var instance: Node = (resource as PackedScene).instantiate()
        if instance is MeshInstance3D and (instance as MeshInstance3D).mesh != null:
            var root_mesh := (instance as MeshInstance3D).mesh.duplicate() as Mesh
            instance.free()
            return root_mesh
        var candidates := instance.find_children("*", "MeshInstance3D", true, false)
        for candidate_variant in candidates:
            if candidate_variant is MeshInstance3D:
                var candidate := candidate_variant as MeshInstance3D
                if candidate.mesh != null:
                    var child_mesh := candidate.mesh.duplicate() as Mesh
                    instance.free()
                    return child_mesh
        instance.free()
    runtime_warning.emit("Mesh asset contains no MeshInstance3D: " + reference)
    return null


func _asset_path(reference: String) -> String:
    if reference.begins_with("res://"):
        return reference
    var base := asset_root if not asset_root.is_empty() else "res://"
    if not base.ends_with("/"):
        base += "/"
    return base + reference.trim_prefix("/")


func _resolve_particle_emission_shape(shape: String, properties: Dictionary) -> Dictionary:
    match shape:
        "point":
            return {"code": 0}
        "sphere":
            return {"code": 1, "radius": float(properties.get("emission_radius", 0.5))}
        "sphere_surface":
            return {"code": 2, "radius": float(properties.get("emission_radius", 0.5))}
        "box":
            return {"code": 3, "extents": _vec3(properties.get("emission_box_extents", [0.25, 0.25, 0.25]))}
        "ring":
            return {
                "code": 6,
                "radius": float(properties.get("emission_radius", 0.5)),
                "height": float(properties.get("emission_height", 0.1)),
            }
        "line":
            var line_extents := _vec3(properties.get("emission_box_extents", [0.5, 0.01, 0.01]))
            return {
                "code": 3,
                "extents": Vector3(maxf(line_extents.x, 0.05), 0.01, 0.01),
            }
        "cone":
            return {
                "code": 1,
                "radius": maxf(0.05, float(properties.get("emission_radius", 0.35))),
                "direction": _vec3(properties.get("direction", [0.0, 1.0, 0.0])),
                "spread_boost": true,
            }
        "disc":
            return {
                "code": 6,
                "radius": maxf(0.05, float(properties.get("emission_radius", 0.5))),
                "height": 0.01,
            }
        _:
            return {"code": -1}


func _alpha_curve_texture(value: Variant) -> GradientTexture1D:
    var gradient := Gradient.new()
    if value is Dictionary:
        var points_variant: Variant = value.get("points", [])
        if points_variant is Array:
            var parsed: Array[Vector2] = []
            for point_variant in points_variant:
                if point_variant is Dictionary:
                    parsed.append(Vector2(float(point_variant.get("x", 0.0)), float(point_variant.get("y", 0.0))))
            parsed.sort_custom(func(a: Vector2, b: Vector2) -> bool: return a.x < b.x)
            for point in parsed:
                gradient.add_point(point.x, Color(1.0, 1.0, 1.0, clampf(point.y, 0.0, 1.0)))
    if gradient.get_point_count() == 0:
        gradient.set_color(0, Color(1, 1, 1, 1))
        gradient.set_color(1, Color(1, 1, 1, 0))
    var texture := GradientTexture1D.new()
    texture.gradient = gradient
    return texture


func _curve_texture(value: Variant) -> CurveTexture:
    var curve := Curve.new()
    if value is Dictionary:
        var points_variant: Variant = value.get("points", [])
        if points_variant is Array:
            var parsed: Array[Vector2] = []
            for point_variant in points_variant:
                if point_variant is Dictionary:
                    parsed.append(Vector2(float(point_variant.get("x", 0.0)), float(point_variant.get("y", 0.0))))
            parsed.sort_custom(func(a: Vector2, b: Vector2) -> bool: return a.x < b.x)
            for point in parsed:
                curve.add_point(point)
    if curve.get_point_count() == 0:
        curve.add_point(Vector2(0.0, 1.0))
        curve.add_point(Vector2(1.0, 1.0))
    var texture := CurveTexture.new()
    texture.width = 256
    texture.curve = curve
    return texture


func _gradient_texture(value: Variant) -> GradientTexture1D:
    var gradient := Gradient.new()
    if value is Array and not value.is_empty():
        gradient.offsets = PackedFloat32Array()
        gradient.colors = PackedColorArray()
        for stop_variant in value:
            if not stop_variant is Dictionary:
                continue
            var stop: Dictionary = stop_variant
            gradient.add_point(float(stop.get("position", 0.0)), _color(stop.get("color", "#FFFFFFFF")))
    else:
        gradient.set_color(0, Color.WHITE)
        gradient.set_color(1, Color(1, 1, 1, 0))
    var texture := GradientTexture1D.new()
    texture.gradient = gradient
    return texture


func _curve_value(value: Variant, position: float, fallback: float) -> float:
    if not value is Dictionary:
        return fallback
    var points_variant: Variant = value.get("points", [])
    if not points_variant is Array or points_variant.is_empty():
        return fallback
    var points: Array = points_variant
    var parsed: Array[Vector2] = []
    for point_variant in points:
        if point_variant is Dictionary:
            parsed.append(Vector2(float(point_variant.get("x", 0.0)), float(point_variant.get("y", 0.0))))
    if parsed.is_empty():
        return fallback
    parsed.sort_custom(func(a: Vector2, b: Vector2) -> bool: return a.x < b.x)
    if position <= parsed[0].x:
        return parsed[0].y
    if position >= parsed[-1].x:
        return parsed[-1].y
    for index in range(parsed.size() - 1):
        var first := parsed[index]
        var second := parsed[index + 1]
        if position >= first.x and position <= second.x:
            return lerpf(first.y, second.y, inverse_lerp(first.x, second.x, position))
    return fallback


func _vec2(value: Variant) -> Vector2:
    if value is Array and value.size() >= 2:
        return Vector2(float(value[0]), float(value[1]))
    return Vector2.ONE


func _vec3(value: Variant) -> Vector3:
    if value is Array and value.size() >= 3:
        return Vector3(float(value[0]), float(value[1]), float(value[2]))
    return Vector3.ZERO


func _color(value: Variant) -> Color:
    if value is Color:
        return value
    if value is String:
        return Color.from_string(value, Color.WHITE)
    return Color.WHITE
