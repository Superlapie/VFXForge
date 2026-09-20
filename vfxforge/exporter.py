"""Godot-native self-contained export and post-export validation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from .effect_refs import resolve_effect, resolve_effect_path
from .errors import ExportError
from .model import read_document, serialize_document, stamp_export_provenance
from .resources import godot_runtime_dir, host_smoke_dir
from .service.paths import validate_resource_path
from .validation import validate_document
from .version import GODOT_TARGET, TOOL_VERSION


def _godot_command() -> str | None:
    configured = os.environ.get("VFXFORGE_GODOT")
    if configured and Path(configured).exists():
        return configured
    for candidate in ("godot", "godot4"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _texture_refs(document: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    dependencies = document.get("dependencies", {})
    if isinstance(dependencies, dict):
        for reference in dependencies.get("textures", []):
            if isinstance(reference, str) and reference:
                refs.add(reference)
    for layer in document.get("layers", []):
        if not isinstance(layer, dict):
            continue
        for container in (layer.get("properties", {}), layer.get("material", {})):
            if isinstance(container, dict):
                reference = container.get("texture")
                if isinstance(reference, str) and reference:
                    refs.add(reference)
    return refs


def _mesh_refs(document: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    dependencies = document.get("dependencies", {})
    if isinstance(dependencies, dict):
        for reference in dependencies.get("meshes", []):
            if isinstance(reference, str) and reference:
                refs.add(reference)
    for layer in document.get("layers", []):
        if not isinstance(layer, dict):
            continue
        properties = layer.get("properties", {})
        if isinstance(properties, dict):
            reference = properties.get("mesh_asset")
            if isinstance(reference, str) and reference:
                refs.add(reference)
    return refs


def _effect_refs(document: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    dependencies = document.get("dependencies", {})
    if isinstance(dependencies, dict):
        for reference in dependencies.get("effects", []):
            if isinstance(reference, str) and reference:
                refs.add(reference)
    for layer in document.get("layers", []):
        if isinstance(layer, dict) and layer.get("type") == "child_effect":
            reference = layer.get("properties", {}).get("effect_id")
            if isinstance(reference, str) and reference:
                refs.add(reference)
    return refs


def _resolve_effect_source(reference: str, document_dir: Path, project_root: Path) -> Path:
    result = resolve_effect(reference, document_dir=document_dir, project_root=project_root)
    if result.error_code == "EFFECT_OUTSIDE_PROJECT":
        raise ExportError(result.error_message or reference, "EFFECT_OUTSIDE_PROJECT", reference)
    if result.error_code == "AMBIGUOUS_EFFECT_ID":
        raise ExportError(result.error_message or reference, "AMBIGUOUS_EFFECT_ID", reference)
    if result.path is None:
        raise ExportError(f"Child effect dependency is missing: {reference}", "MISSING_EFFECT", reference)
    return result.path


def _effect_base_name(source: Path) -> str:
    name = source.name
    if name.endswith(".vfx.json"):
        return name[: -len(".vfx.json")]
    return source.stem


def _effect_export_name(source: Path, project: Path, used: set[str]) -> str:
    relative = source.relative_to(project).as_posix()
    digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:8]
    base = _effect_base_name(source)
    candidate = f"{base}_{digest}.vfx.json"
    counter = 0
    while candidate in used:
        counter += 1
        candidate = f"{base}_{digest}_{counter}.vfx.json"
    used.add(candidate)
    return candidate


def _rewrite_document_effect_refs(
    document: dict[str, Any],
    document_dir: Path,
    project_root: Path,
    source_exports: dict[str, str],
) -> dict[str, Any]:
    rewritten = deepcopy(document)
    for layer in rewritten.get("layers", []):
        if not isinstance(layer, dict) or layer.get("type") != "child_effect":
            continue
        properties = layer.get("properties", {})
        if not isinstance(properties, dict):
            continue
        reference = properties.get("effect_id")
        if not isinstance(reference, str) or not reference:
            continue
        source = _resolve_effect_source(reference, document_dir, project_root)
        export_path = source_exports.get(str(source.resolve()))
        if export_path:
            properties["effect_id"] = export_path
    dependencies = rewritten.setdefault("dependencies", {})
    if isinstance(dependencies, dict):
        effects = dependencies.get("effects", [])
        if isinstance(effects, list):
            rewritten_effects: list[str] = []
            for reference in effects:
                if not isinstance(reference, str) or not reference:
                    continue
                source = _resolve_effect_source(reference, document_dir, project_root)
                export_path = source_exports.get(str(source.resolve()))
                rewritten_effects.append(export_path or reference)
            dependencies["effects"] = rewritten_effects
    return rewritten


def _enqueue_effect_refs(
    document: dict[str, Any],
    base_dir: Path,
    pending: list[tuple[str, Path]],
    seen: set[tuple[str, str]],
) -> None:
    for reference in sorted(_effect_refs(document)):
        token = (reference, str(base_dir.resolve()))
        if token in seen:
            continue
        seen.add(token)
        pending.append((reference, base_dir))


def _replace_refs(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_refs(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_refs(item, replacements) for item in value]
    if isinstance(value, str):
        return replacements.get(value, value)
    return value


def _escaped_document_string(document: dict[str, Any]) -> str:
    serialized = serialize_document(document, indent=None)
    return serialized.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def _write_generated_script(
    destination: Path,
    document: dict[str, Any],
    runtime_path: str = "res://vfx_runtime.gd",
    asset_root: str | None = None,
    trail_path: str | None = None,
) -> None:
    init_lines = [
        '    var parsed: Variant = JSON.parse_string(DOCUMENT_JSON)',
        "    if parsed is Dictionary:",
    ]
    if asset_root:
        init_lines.insert(0, f'    set("runtime_script_path", "{runtime_path}")')
        if trail_path:
            init_lines.insert(1, f'    set("trail_script_path", "{trail_path}")')
        init_lines.append(f'        set_document(parsed, "{asset_root}")')
    else:
        init_lines.append("        set_document(parsed)")
    init_lines.append("        play()")
    body = "\n".join(init_lines)
    script = f'''extends "{runtime_path}"

const DOCUMENT_JSON: String = "{_escaped_document_string(document)}"

func _ready() -> void:
{body}
'''
    destination.write_text(script, encoding="utf-8")


def _write_project_file(destination: Path) -> None:
    project = """[application]
config/name="VFX Forge Export Smoke"
run/main_scene="res://effect.tscn"

[display]
window/size/viewport_width=512
window/size/viewport_height=512
window/size/window_width_override=512
window/size/window_height_override=512

[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
environment/defaults/default_clear_color=Color(0.035, 0.045, 0.07, 1)
"""
    destination.write_text(project, encoding="utf-8")


def _write_tscn(destination: Path, script_path: str = "res://effect.gd") -> None:
    scene = f"""[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="{script_path}" id="1_effect"]

[node name="VFXEffect" type="Node3D"]
script = ExtResource("1_effect")
"""
    destination.write_text(scene, encoding="utf-8")


def _write_smoke_script(destination: Path) -> None:
    script = """extends SceneTree

func _fail(message: String) -> void:
    push_error(message)
    quit(4)

func _initialize() -> void:
    var scene: PackedScene = load("res://effect.tscn")
    if scene == null:
        push_error("VFX Forge export smoke test could not load effect.tscn")
        quit(2)
        return
    var instance: Node = scene.instantiate()
    root.add_child(instance)
    await process_frame
    await process_frame
    if not is_instance_valid(instance):
        quit(3)
        return

    var document_file := FileAccess.open("res://document.vfx.json", FileAccess.READ)
    if document_file != null:
        var parsed: Variant = JSON.parse_string(document_file.get_as_text())
        if parsed is Dictionary and parsed.get("layers", []) is Array:
            for layer_variant in parsed.get("layers", []):
                if not layer_variant is Dictionary:
                    continue
                var layer: Dictionary = layer_variant
                var properties: Dictionary = layer.get("properties", {}) if layer.get("properties", {}) is Dictionary else {}
                var mesh_reference := str(properties.get("mesh_asset", ""))
                if mesh_reference.is_empty():
                    continue
                var layer_node := instance.get_node_or_null(str(layer.get("id", "")))
                if layer_node == null:
                    _fail("Custom mesh layer node is missing: " + str(layer.get("id", "")))
                    return
                var mesh: Mesh = null
                if layer.get("type", "") == "mesh_particle" and layer_node is GPUParticles3D:
                    mesh = (layer_node as GPUParticles3D).draw_pass_1
                elif layer_node is MeshInstance3D:
                    mesh = (layer_node as MeshInstance3D).mesh
                if mesh == null or mesh.get_surface_count() == 0:
                    _fail("Custom mesh did not import or instantiate: " + mesh_reference)
                    return
        else:
            _fail("Exported document.vfx.json is not a valid dictionary")
            return
    quit(0)
"""
    destination.write_text(script, encoding="utf-8")


def _manifest(root: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in {"export_manifest.json", "smoke_test.gd"} or ".godot" in path.relative_to(root).parts:
            continue
        relative = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({"path": relative, "sha256": digest, "bytes": path.stat().st_size})
    return entries


def _run_godot_smoke(output: Path) -> dict[str, Any]:
    command = _godot_command()
    if command is None:
        return {
            "status": "skipped",
            "reason": "Godot 4.x was not found on PATH. Set VFXFORGE_GODOT to a Godot executable to run the clean-project smoke test.",
        }
    smoke_script = output / "smoke_test.gd"
    cache_directory = output / ".godot"
    had_cache = cache_directory.exists()
    existing_uids = {path for path in output.rglob("*.uid")}
    _write_smoke_script(smoke_script)
    try:
        import_result = subprocess.run(
            [command, "--headless", "--editor", "--path", str(output), "--quit"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        import_output = f"{import_result.stdout}\n{import_result.stderr}"
        if import_result.returncode != 0 or "SCRIPT ERROR" in import_output or "Parse Error" in import_output or "ERROR:" in import_output:
            return {
                "status": "failed",
                "phase": "asset_import",
                "returncode": import_result.returncode,
                "stdout": import_result.stdout[-4000:],
                "stderr": import_result.stderr[-4000:],
            }
        result = subprocess.run(
            [command, "--headless", "--path", str(output), "--script", "res://smoke_test.gd"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "reason": str(exc)}
    finally:
        smoke_script.unlink(missing_ok=True)
        smoke_uid = output / "smoke_test.gd.uid"
        if smoke_uid not in existing_uids:
            smoke_uid.unlink(missing_ok=True)
        for uid_path in output.rglob("*.uid"):
            if uid_path not in existing_uids:
                uid_path.unlink(missing_ok=True)
        if not had_cache and cache_directory.exists():
            shutil.rmtree(cache_directory, ignore_errors=True)
    combined_output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0 or "SCRIPT ERROR" in combined_output or "Compile Error" in combined_output or "Parse Error" in combined_output or "ERROR:" in combined_output or "No loader found" in combined_output:
        return {
            "status": "failed",
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
        }
    return {"status": "passed", "godot": command, "stdout": result.stdout[-1000:], "stderr": result.stderr[-1000:]}


def _lifecycle_checkpoints(document: dict[str, Any]) -> list[float]:
    duration = max(float(document.get("duration", 1.0)), 0.001)
    samples = {0.0, duration * 0.25, duration * 0.5, duration * 0.75, duration}
    timeline = document.get("timeline", {})
    if isinstance(timeline, dict):
        for event in timeline.get("events", []):
            if isinstance(event, dict) and isinstance(event.get("time"), (int, float)):
                samples.add(float(event["time"]))
    for layer in document.get("layers", []):
        if isinstance(layer, dict) and layer.get("type") == "event_marker" and isinstance(layer.get("start"), (int, float)):
            samples.add(float(layer["start"]))
    return sorted({min(max(0.0, value), duration) for value in samples})


def _run_host_library_smoke(output: Path, resource_root: str, shared_runtime_path: str | None) -> dict[str, Any]:
    command = _godot_command()
    if command is None:
        return {"status": "skipped", "reason": "Godot 4.x was not found on PATH for host library smoke."}
    fixture_root = host_smoke_dir()
    if fixture_root is None or not fixture_root.exists():
        return {"status": "skipped", "reason": "Host library fixture project is missing."}
    validate_resource_path(resource_root, "resource_root")
    if shared_runtime_path:
        validate_resource_path(shared_runtime_path, "shared_runtime_path")
    with tempfile.TemporaryDirectory(prefix="vfxforge-host-") as tmp:
        host = Path(tmp) / "host"
        shutil.copytree(fixture_root, host)
        bundle_target = host / resource_root.removeprefix("res://")
        bundle_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(output, bundle_target)
        runtime_source = godot_runtime_dir() / "vfx_runtime.gd"
        trail_source = godot_runtime_dir() / "vfx_trail.gd"
        if shared_runtime_path:
            shared_dir = host / shared_runtime_path.removeprefix("res://").rsplit("/", 1)[0]
            shared_dir.mkdir(parents=True, exist_ok=True)
            runtime_dst = shared_dir / "vfx_runtime.gd"
            trail_dst = shared_dir / "vfx_trail.gd"
            shutil.copy2(runtime_source, runtime_dst)
            shutil.copy2(trail_source, trail_dst)
            runtime_text = runtime_dst.read_text(encoding="utf-8").replace(
                'trail_script_path: String = "res://godot/runtime/vfx_trail.gd"',
                f'trail_script_path: String = "{shared_runtime_path.rsplit("/", 1)[0]}/vfx_trail.gd"',
            )
            runtime_dst.write_text(runtime_text, encoding="utf-8")
        document_payload = json.loads((output / "document.vfx.json").read_text(encoding="utf-8"))
        smoke_config = {
            "resource_root": resource_root,
            "duration": float(document_payload.get("duration", 1.0)),
            "loop": bool(document_payload.get("loop", False)),
            "checkpoints": _lifecycle_checkpoints(document_payload),
            "enabled_layers": [
                str(layer.get("id"))
                for layer in document_payload.get("layers", [])
                if isinstance(layer, dict) and layer.get("enabled", True) and layer.get("type") in {
                    "particle", "mesh_particle", "sprite", "light", "trail", "beam", "decal", "mesh_effect", "child_effect"
                }
            ],
        }
        (host / "smoke_config.json").write_text(json.dumps(smoke_config, indent=2) + "\n", encoding="utf-8")
        shutil.copy2(fixture_root / "host_smoke.gd", host / "host_smoke.gd")
        try:
            import_result = subprocess.run(
                [command, "--headless", "--editor", "--path", str(host), "--quit"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            import_output = f"{import_result.stdout}\n{import_result.stderr}"
            if import_result.returncode != 0 or "ERROR:" in import_output or "Parse Error" in import_output:
                return {
                    "status": "failed",
                    "phase": "host_import",
                    "returncode": import_result.returncode,
                    "stdout": import_result.stdout[-2000:],
                    "stderr": import_result.stderr[-2000:],
                }
            result = subprocess.run(
                [command, "--headless", "--path", str(host), "--script", "res://host_smoke.gd"],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"status": "failed", "reason": str(exc)}
        combined = f"{result.stdout}\n{result.stderr}"
        if result.returncode != 0 or "HOST_LIBRARY_SMOKE" in combined or "ERROR:" in combined:
            return {"status": "failed", "returncode": result.returncode, "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]}
        return {"status": "passed", "godot": command, "resource_root": resource_root, "checkpoints": smoke_config["checkpoints"]}


def _replace_directory(staging: Path, destination: Path) -> None:
    backup = destination.with_name(destination.name + ".export-bak")
    if backup.exists():
        shutil.rmtree(backup)
    had_destination = destination.exists()
    if had_destination:
        destination.rename(backup)
    try:
        staging.rename(destination)
    except OSError:
        try:
            shutil.move(str(staging), str(destination))
        except Exception:
            if had_destination and backup.exists() and not destination.exists():
                backup.rename(destination)
            raise
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)


def _resolve_project_root(source: Path, project_dir: Path | None) -> Path:
    if project_dir is not None:
        return Path(project_dir).resolve()
    start = source.parent.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "assets").is_dir():
            return candidate
        if (candidate / "effects").is_dir():
            return candidate
    return start


def export_document(
    document: dict[str, Any],
    source_path: str | Path,
    output: str | Path,
    run_smoke_test: bool = True,
    mode: str = "standalone",
    resource_root: str | None = None,
    shared_runtime_path: str | None = None,
    policy_ceilings: dict[str, Any] | None = None,
    project_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Export Godot content with relative dependencies and a manifest.

    mode:
      standalone - self-contained mini-project with project.godot
      library    - nested bundle for host projects without project.godot
    """
    source = Path(source_path).resolve()
    resolved_project = _resolve_project_root(source, Path(project_dir).resolve() if project_dir is not None else None)
    validation = validate_document(
        document,
        resolved_project,
        strict=policy_ceilings is not None,
        policy_ceilings=policy_ceilings,
        document_path=source,
    )
    if not validation["valid"]:
        raise ExportError(
            "Export blocked by validation errors. Fix the reported fields first.",
            "EXPORT_VALIDATION_FAILED",
            str(source),
        )
    final_destination = Path(output).resolve()
    staging = final_destination.parent / f".{final_destination.name}.export-staging-{uuid.uuid4().hex[:8]}"
    if staging.exists():
        shutil.rmtree(staging)
    destination = staging
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "materials").mkdir(exist_ok=True)
    (destination / "shaders").mkdir(exist_ok=True)
    (destination / "textures").mkdir(exist_ok=True)
    (destination / "meshes").mkdir(exist_ok=True)

    exported_document = deepcopy(document)
    copied_effects: list[str] = []
    source_exports: dict[str, str] = {}
    effect_documents: dict[str, tuple[dict[str, Any], Path]] = {}
    pending_effects: list[tuple[str, Path]] = []
    seen_pending: set[tuple[str, str]] = set()
    used_effect_names: set[str] = set()
    effect_dir = destination / "effects"
    effect_dir.mkdir(exist_ok=True)
    _enqueue_effect_refs(document, source_path.parent, pending_effects, seen_pending)
    while pending_effects:
        reference, base_dir = pending_effects.pop(0)
        effect_source = _resolve_effect_source(reference, base_dir, resolved_project)
        source_key = str(effect_source.resolve())
        if source_key in source_exports:
            continue
        target_name = _effect_export_name(effect_source, resolved_project, used_effect_names)
        relative = f"effects/{target_name}"
        source_exports[source_key] = relative
        child_document = read_document(effect_source)
        effect_documents[source_key] = (child_document, effect_source)
        copied_effects.append(relative)
        _enqueue_effect_refs(child_document, effect_source.parent, pending_effects, seen_pending)

    all_documents = [document, *(child for child, _source in effect_documents.values())]
    texture_replacements: dict[str, str] = {}
    mesh_replacements: dict[str, str] = {}
    copied_files: list[str] = []
    copied_meshes: list[str] = []

    def copy_asset(reference: str, folder: str, replacements: dict[str, str], copied: list[str], kind: str) -> None:
        source_asset = (resolved_project / reference.removeprefix("res://")).resolve()
        try:
            source_asset.relative_to(resolved_project)
        except ValueError as exc:
            raise ExportError(f"{kind} reference escapes the project: {reference}", f"{kind.upper()}_OUTSIDE_PROJECT") from exc
        if not source_asset.exists() or not source_asset.is_file():
            raise ExportError(f"{kind} dependency is missing: {reference}", f"MISSING_{kind.upper()}", reference)
        target_name = source_asset.name
        target = destination / folder / target_name
        if target.exists() and target.read_bytes() != source_asset.read_bytes():
            target_name = f"{source_asset.stem}_{hashlib.sha1(reference.encode()).hexdigest()[:8]}{source_asset.suffix}"
            target = destination / folder / target_name
        if not target.exists():
            shutil.copy2(source_asset, target)
        relative = f"{folder}/{target_name}"
        replacements[reference] = relative
        if relative not in copied:
            copied.append(relative)

    for reference in sorted({item for item in all_documents for item in _texture_refs(item)}):
        copy_asset(reference, "textures", texture_replacements, copied_files, "texture")
    for reference in sorted({item for item in all_documents for item in _mesh_refs(item)}):
        copy_asset(reference, "meshes", mesh_replacements, copied_meshes, "mesh")

    exported_document = _rewrite_document_effect_refs(exported_document, source.parent, resolved_project, source_exports)
    for source_key, (child_document, child_source) in effect_documents.items():
        rewritten_child = _rewrite_document_effect_refs(child_document, child_source.parent, resolved_project, source_exports)
        rewritten_child = _replace_refs(_replace_refs(rewritten_child, texture_replacements), mesh_replacements)
        rewritten_child = stamp_export_provenance(rewritten_child)
        target = destination / source_exports[source_key]
        target.write_text(serialize_document(rewritten_child), encoding="utf-8")
    exported_document = _replace_refs(_replace_refs(exported_document, texture_replacements), mesh_replacements)
    exported_document = stamp_export_provenance(exported_document)

    runtime_source = godot_runtime_dir() / "vfx_runtime.gd"
    trail_source = godot_runtime_dir() / "vfx_trail.gd"
    if not runtime_source.exists():
        raise ExportError("The Godot runtime source is missing from the installed VFX Forge data.", "RUNTIME_SOURCE_MISSING", str(runtime_source))
    if not trail_source.exists():
        raise ExportError("The Godot trail runtime source is missing from the repository.", "TRAIL_SOURCE_MISSING", str(trail_source))
    if mode not in {"standalone", "library"}:
        raise ExportError(f"Unsupported export mode '{mode}'.", "INVALID_EXPORT_MODE", mode)
    root_prefix = resource_root.rstrip("/") if resource_root else None
    if mode == "library":
        if not root_prefix:
            root_prefix = "res://generated/vfx/" + str(document.get("id", "effect"))
        validate_resource_path(root_prefix, "resource_root")
        if shared_runtime_path:
            validate_resource_path(shared_runtime_path, "shared_runtime_path")
    runtime_script = shared_runtime_path or (f"{root_prefix}/vfx_runtime.gd" if mode == "library" else "res://vfx_runtime.gd")
    trail_script = None
    if mode == "library":
        if shared_runtime_path:
            trail_script = shared_runtime_path.rsplit("/", 1)[0] + "/vfx_trail.gd"
        else:
            trail_script = f"{root_prefix}/godot/runtime/vfx_trail.gd"
    effect_script_path = f"{root_prefix}/effect.gd" if mode == "library" and root_prefix else "res://effect.gd"
    if mode == "standalone" or (mode == "library" and shared_runtime_path is None):
        shutil.copy2(runtime_source, destination / "vfx_runtime.gd")
    if mode == "standalone":
        trail_destination = destination / "godot" / "runtime"
        trail_destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(trail_source, trail_destination / "vfx_trail.gd")
    elif mode == "library" and shared_runtime_path is None:
        trail_destination = destination / "godot" / "runtime"
        trail_destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(trail_source, trail_destination / "vfx_trail.gd")
    _write_generated_script(
        destination / "effect.gd",
        exported_document,
        runtime_script,
        asset_root=root_prefix if mode == "library" else None,
        trail_path=trail_script,
    )
    _write_tscn(destination / "effect.tscn", effect_script_path)
    if mode == "standalone":
        _write_project_file(destination / "project.godot")
    (destination / "shaders" / "vfx_unlit.gdshader").write_text(
        """shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_always, blend_add;

uniform vec4 tint : source_color = vec4(1.0);
uniform float emissive_intensity = 1.0;

void fragment() {
    ALBEDO = tint.rgb;
    ALPHA = tint.a;
    EMISSION = tint.rgb * emissive_intensity;
}
""",
        encoding="utf-8",
    )
    (destination / "materials" / "README.md").write_text(
        "Generated VFX Forge material resources. The runtime applies constrained VFX material settings per layer.\n",
        encoding="utf-8",
    )
    if document.get("export", {}).get("include_metadata", True):
        (destination / "metadata.json").write_text(
            json.dumps(
                {
                    "vfxforge_version": TOOL_VERSION,
                    "schema_version": document.get("schema_version"),
                    "godot_target": GODOT_TARGET,
                    "source_document": source.name,
                    "document": exported_document,
                    "validation": validation,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    (destination / "document.vfx.json").write_text(serialize_document(exported_document), encoding="utf-8")
    smoke = {"status": "not_requested"}
    host_smoke: dict[str, Any] = {"status": "not_requested"}
    if run_smoke_test and mode == "standalone":
        smoke = _run_godot_smoke(destination)
    elif run_smoke_test and mode == "library":
        host_smoke = _run_host_library_smoke(destination, root_prefix or "", shared_runtime_path)
    files = _manifest(destination)
    manifest = {
        "manifest_version": 1,
        "vfxforge_version": TOOL_VERSION,
        "schema_version": document.get("schema_version"),
        "godot_target": GODOT_TARGET,
        "effect_id": document.get("id"),
        "entry_scene": "effect.tscn",
        "export_mode": mode,
        "resource_root": root_prefix,
        "runtime_script": runtime_script,
        "trail_script": trail_script,
        "files": files,
        "copied_textures": copied_files,
        "copied_meshes": copied_meshes,
        "copied_effects": copied_effects,
        "validation": validation,
        "smoke_test": smoke,
        "host_smoke_test": host_smoke,
    }
    (destination / "export_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _replace_directory(staging, final_destination)
    destination = final_destination
    return {
        "output": str(destination),
        "entry_scene": str(destination / "effect.tscn"),
        "manifest": str(destination / "export_manifest.json"),
        "export_mode": mode,
        "resource_root": root_prefix,
        "runtime_script": runtime_script,
        "trail_script": trail_script,
        "copied_textures": copied_files,
        "copied_meshes": copied_meshes,
        "copied_effects": copied_effects,
        "validation": validation,
        "smoke_test": smoke,
        "host_smoke_test": host_smoke,
        "files": files,
    }


def export_file(
    source: str | Path,
    output: str | Path,
    run_smoke_test: bool = True,
    mode: str = "standalone",
    resource_root: str | None = None,
    shared_runtime_path: str | None = None,
) -> dict[str, Any]:
    source_path = Path(source)
    document = read_document(source_path)
    return export_document(
        document,
        source_path,
        output,
        run_smoke_test=run_smoke_test,
        mode=mode,
        resource_root=resource_root,
        shared_runtime_path=shared_runtime_path,
    )
