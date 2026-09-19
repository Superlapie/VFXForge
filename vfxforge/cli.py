"""VFX Forge deterministic command-line interface."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

from .diffing import format_change, semantic_diff
from .errors import DocumentError, ExportError, VFXForgeError
from .exporter import export_file
from .model import add_layer, get_path, migrate_document, parse_value, read_document, remove_layer, set_path, write_document
from .presets import list_presets, make_preset
from .renderer import render_preview
from .schema import LAYER_TYPES, MESH_ASSET_EXTENSIONS, schema_description, default_document
from .service.capabilities import _policy_capability, _recipe_capability, capabilities
from .service.gates import engine_gate_result
from .service.pipeline import forge, plan
from .service.policy import list_policies, load_policy, policy_ref
from .service.promotion import is_managed_document
from .service.result import exit_code_for
from .service.selector import list_recipes, load_recipe, recipe_ref
from .validation import iter_vfx_files, validate_document, validation_summary
from .version import GODOT_TARGET, SCHEMA_VERSION, TOOL_NAME, TOOL_VERSION


EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_USAGE = 2
EXIT_ARTIFACT = 3


class CLIParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise VFXForgeError(message, "ARGUMENT_ERROR")


def _parser() -> CLIParser:
    parser = CLIParser(prog="vfxforge", description="AI-first Godot VFX authoring CLI.")
    parser.add_argument("--version", action="store_true", help="Print the VFX Forge version.")
    sub = parser.add_subparsers(dest="command")

    create = sub.add_parser("create", help="Create a canonical VFX document.")
    create.add_argument("path")
    create.add_argument("--id", default=None)
    create.add_argument("--name", default=None)
    create.add_argument("--duration", type=float, default=None)
    create.add_argument("--loop", action="store_true")
    create.add_argument("--seed", type=int, default=None)
    create.add_argument("--preset", choices=list_presets())
    create.add_argument("--force", action="store_true")
    create.add_argument("--unsafe-direct-edit", action="store_true", help="Allow mutation of service-managed production documents.")

    inspect = sub.add_parser("inspect", help="Inspect a document or directory.")
    inspect.add_argument("target")
    inspect.add_argument("--recursive", action="store_true")

    validate = sub.add_parser("validate", help="Validate a document or directory.")
    validate.add_argument("target")
    validate.add_argument("--budget", choices=["Mobile", "Low", "Medium", "High", "Boss", "Cinematic"])
    validate.add_argument("--recursive", action="store_true")

    layers = sub.add_parser("list-layers", help="List ordered layers.")
    layers.add_argument("path")

    add = sub.add_parser("add-layer", help="Add a typed layer.")
    add.add_argument("path")
    add.add_argument("--type", required=True, choices=LAYER_TYPES)
    add.add_argument("--id", required=True)
    add.add_argument("--name", default=None)

    remove = sub.add_parser("remove-layer", help="Remove a layer by stable ID.")
    remove.add_argument("path")
    remove.add_argument("--id", required=True)

    update = sub.add_parser("update-layer", help="Update one layer using field=value assignments.")
    update.add_argument("path")
    update.add_argument("--id", required=True)
    update.add_argument("--set", dest="assignments", action="append", required=True, metavar="FIELD=VALUE")

    set_command = sub.add_parser("set", help="Set one or more canonical paths.")
    set_command.add_argument("path")
    set_command.add_argument("assignments", nargs="+", metavar="PATH=VALUE")

    texture = sub.add_parser("add-texture", help="Copy a texture into the project asset library.")
    texture.add_argument("path")
    texture.add_argument("--source", required=True)
    texture.add_argument("--ref", default=None, help="Optional canonical relative reference.")

    mesh = sub.add_parser("add-mesh", help="Copy a 3D model into the project asset library.")
    mesh.add_argument("path")
    mesh.add_argument("--source", required=True)
    mesh.add_argument("--ref", default=None, help="Optional canonical relative reference.")

    event = sub.add_parser("add-event", help="Append a timeline event marker.")
    event.add_argument("path")
    event.add_argument("--event-id", required=True)
    event.add_argument("--time", required=True, type=float)
    event.add_argument("--id", default=None)
    event.add_argument("--data", default="{}")

    render = sub.add_parser("render-preview", help="Render a deterministic PNG snapshot.")
    render.add_argument("target")
    render.add_argument("--time", type=float, default=0.0)
    render.add_argument("--camera", choices=["front", "side", "top", "mmo"], default="mmo")
    render.add_argument("--output", default=None)
    render.add_argument("--width", type=int, default=768)
    render.add_argument("--height", type=int, default=512)
    render.add_argument("--background", choices=["dark", "light", "night", "transparent"], default="dark")
    render.add_argument("--no-grid", action="store_true")
    render.add_argument("--recursive", action="store_true")

    export = sub.add_parser("export", help="Export normal Godot content.")
    export.add_argument("target")
    export.add_argument("--output", required=True)
    export.add_argument("--no-smoke-test", action="store_true")
    export.add_argument("--recursive", action="store_true")
    export.add_argument("--mode", choices=["standalone", "library"], default="standalone")
    export.add_argument("--resource-root", default=None)
    export.add_argument("--shared-runtime", default=None)

    migrate = sub.add_parser("migrate", help="Normalize documents to the current schema.")
    migrate.add_argument("target")
    migrate.add_argument("--in-place", action="store_true")
    migrate.add_argument("--recursive", action="store_true")
    migrate.add_argument("--unsafe-direct-edit", action="store_true", help="Allow mutation of service-managed production documents.")

    diff = sub.add_parser("diff", help="Produce a semantic diff keyed by layer IDs.")
    diff.add_argument("old")
    diff.add_argument("new")

    explain = sub.add_parser("explain", help="Describe commands, schema, or a layer type.")
    explain.add_argument("topic", nargs="?", default="overview")

    schema = sub.add_parser("schema", help="Print the self-describing canonical schema.")
    schema.add_argument("topic", nargs="?", default="schema")

    preset = sub.add_parser("preset", help="List or write one of the authored starter presets.")
    preset.add_argument("action", choices=["list", "create"])
    preset.add_argument("name", nargs="?")
    preset.add_argument("--output", default=None)
    preset.add_argument("--force", action="store_true")
    preset.add_argument("--unsafe-direct-edit", action="store_true", help="Allow mutation of service-managed production documents.")

    forge_cmd = sub.add_parser("forge", help="Generate production-ready VFX from a semantic request.")
    forge_cmd.add_argument("--request", required=True, help="Path to request JSON or '-' for stdin.")
    forge_cmd.add_argument("--policy", default="default")
    forge_cmd.add_argument("--workspace", default="build/service")
    forge_cmd.add_argument("--no-export", action="store_true")
    forge_cmd.add_argument("--export-mode", choices=["standalone", "library"], default=None)
    forge_cmd.add_argument("--resource-root", default=None)
    forge_cmd.add_argument("--shared-runtime", default=None, help="Shared runtime script path for library export.")
    forge_cmd.add_argument("--asset-root", default=None, help="Host/project asset root used for policy and generation identity.")
    forge_cmd.add_argument("--allow-replace", action="store_true")

    plan_cmd = sub.add_parser("plan", help="Resolve recipe and mappings without promoting assets.")
    plan_cmd.add_argument("--request", required=True)
    plan_cmd.add_argument("--policy", default="default")

    recipes = sub.add_parser("recipes", help="List or show data-only recipes.")
    recipes.add_argument("action", choices=["list", "show"])
    recipes.add_argument("name", nargs="?")

    policies = sub.add_parser("policies", help="List or show service policies.")
    policies.add_argument("action", choices=["list", "show"])
    policies.add_argument("name", nargs="?")

    capabilities_cmd = sub.add_parser("capabilities", help="Describe machine-facing recipe and policy capabilities.")
    capabilities_cmd.add_argument("--policy", default=None)

    for mutating in (add, remove, update, set_command, texture, mesh, event):
        mutating.add_argument("--unsafe-direct-edit", action="store_true", help="Allow mutation of service-managed production documents.")
    return parser


def _error(exc: Exception, default_code: str = "COMMAND_FAILED") -> dict[str, Any]:
    if isinstance(exc, VFXForgeError):
        result = {"severity": "error", "code": exc.code, "path": exc.path, "message": exc.message}
        return {key: value for key, value in result.items() if value is not None}
    return {"severity": "error", "code": default_code, "message": str(exc)}


def _envelope(command: str) -> dict[str, Any]:
    return {"success": True, "command": command, "errors": [], "warnings": [], "artifacts": []}


def _assignments(values: list[str]) -> list[tuple[str, Any]]:
    parsed = []
    for value in values:
        if "=" not in value:
            raise VFXForgeError(f"Assignment '{value}' must use PATH=VALUE.", "INVALID_ASSIGNMENT")
        path, raw_value = value.split("=", 1)
        if not path:
            raise VFXForgeError(f"Assignment '{value}' has an empty path.", "INVALID_ASSIGNMENT")
        parsed.append((path, parse_value(raw_value)))
    return parsed


def _assert_source_mutation_allowed(path: Path, unsafe_direct_edit: bool = False) -> None:
    if is_managed_document(path) and not unsafe_direct_edit:
        raise VFXForgeError(
            f"Refusing to mutate service-managed document: {path}. Use forge or --unsafe-direct-edit.",
            "MANAGED_DOCUMENT",
            str(path),
        )


def _commit(path: Path, document: dict[str, Any], unsafe_direct_edit: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    _assert_source_mutation_allowed(path, unsafe_direct_edit)
    validation = validate_document(document, path.parent)
    if not validation["valid"]:
        return validation, document
    write_document(path, document)
    return validation, document


def _single_validate(path: Path, budget: str | None = None) -> dict[str, Any]:
    try:
        document = read_document(path)
        result = validate_document(document, path.parent, budget)
        return {"path": str(path), "document_id": document.get("id"), **result}
    except Exception as exc:
        return {"path": str(path), "valid": False, "errors": [_error(exc)], "warnings": [], "metrics": {}, "budget": {}}


def _targets(target: str | Path) -> list[Path]:
    path = Path(target)
    if path.is_dir():
        return list(iter_vfx_files(path))
    return [path]


def _cmd_create(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path)
    _assert_source_mutation_allowed(path, args.unsafe_direct_edit)
    if path.exists() and not args.force:
        raise VFXForgeError(f"Refusing to overwrite existing file: {path}. Use --force if intentional.", "FILE_EXISTS", str(path))
    effect_id = args.id or path.name.removesuffix(".vfx.json").replace(" ", "_").lower()
    if args.preset:
        document = make_preset(args.preset)
        document["id"] = effect_id
        document["export"]["folder_name"] = effect_id
        if args.name:
            document["name"] = args.name
        if args.duration is not None:
            document["duration"] = args.duration
        document["loop"] = args.loop or document.get("loop", False)
        if args.seed is not None:
            document["seed"] = args.seed
    else:
        document = default_document(effect_id, args.name, args.duration or 1.0, args.loop, args.seed if args.seed is not None else 12345)
    validation, _ = _commit(path, document)
    result = _envelope("create")
    result["warnings"] = validation["warnings"]
    result["errors"] = validation["errors"]
    result["success"] = validation["valid"]
    if result["success"]:
        result["artifacts"].append(str(path))
        result["data"] = {"document": document, "validation": validation}
    return result


def _cmd_inspect(args: argparse.Namespace) -> dict[str, Any]:
    files = _targets(args.target)
    result = _envelope("inspect")
    items = []
    for path in files:
        try:
            document = read_document(path)
            validation = validate_document(document, path.parent)
            items.append({"path": str(path), "document": document, "validation": validation})
            result["warnings"].extend(validation["warnings"])
            result["errors"].extend(validation["errors"])
        except Exception as exc:
            result["errors"].append({**_error(exc), "path": str(path)})
    result["items"] = items
    result["success"] = not result["errors"]
    if len(files) == 1 and items:
        result["data"] = items[0]
    return result


def _cmd_validate(args: argparse.Namespace) -> dict[str, Any]:
    result = _envelope("validate")
    items = []
    for path in _targets(args.target):
        item = _single_validate(path, args.budget)
        items.append(item)
        result["errors"].extend([{**error, "file": str(path)} for error in item.get("errors", [])])
        result["warnings"].extend([{**warning, "file": str(path)} for warning in item.get("warnings", [])])
    result["items"] = items
    result["success"] = not result["errors"]
    return result


def _cmd_list_layers(args: argparse.Namespace) -> dict[str, Any]:
    document = read_document(args.path)
    result = _envelope("list-layers")
    result["data"] = {
        "document_id": document.get("id"),
        "layers": [
            {
                "index": index,
                "id": layer.get("id"),
                "type": layer.get("type"),
                "name": layer.get("name"),
                "enabled": layer.get("enabled"),
                "start": layer.get("start"),
                "duration": layer.get("duration"),
            }
            for index, layer in enumerate(document.get("layers", []))
            if isinstance(layer, dict)
        ],
    }
    return result


def _cmd_mutate(args: argparse.Namespace, mutation: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
    path = Path(args.path)
    document = read_document(path)
    mutation(document)
    validation, _ = _commit(path, document, getattr(args, "unsafe_direct_edit", False))
    result = _envelope(args.command)
    result["warnings"] = validation["warnings"]
    result["errors"] = validation["errors"]
    result["success"] = validation["valid"]
    if result["success"]:
        result["artifacts"].append(str(path))
        result["data"] = {"document_id": document.get("id"), "validation": validation}
    return result


def _cmd_add_layer(args: argparse.Namespace) -> dict[str, Any]:
    return _cmd_mutate(args, lambda document: add_layer(document, args.type, args.id, args.name))


def _cmd_remove_layer(args: argparse.Namespace) -> dict[str, Any]:
    return _cmd_mutate(args, lambda document: remove_layer(document, args.id))


def _cmd_update_layer(args: argparse.Namespace) -> dict[str, Any]:
    def mutate(document: dict[str, Any]) -> None:
        for field, value in _assignments(args.assignments):
            set_path(document, f"layers.{args.id}.{field}", value)
    return _cmd_mutate(args, mutate)


def _cmd_set(args: argparse.Namespace) -> dict[str, Any]:
    def mutate(document: dict[str, Any]) -> None:
        for path, value in _assignments(args.assignments):
            set_path(document, path, value)
    return _cmd_mutate(args, mutate)


def _cmd_add_texture(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path)
    source = Path(args.source).resolve()
    if not source.exists() or not source.is_file():
        raise VFXForgeError(f"Texture source does not exist: {source}", "TEXTURE_SOURCE_MISSING", str(source))
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise VFXForgeError("Supported textures are PNG, JPG/JPEG, and WebP.", "UNSUPPORTED_TEXTURE")
    document = read_document(path)
    _assert_source_mutation_allowed(path, getattr(args, "unsafe_direct_edit", False))
    asset_dir = path.parent / "assets" / "textures"
    asset_dir.mkdir(parents=True, exist_ok=True)
    target = asset_dir / source.name
    if target.exists() and target.read_bytes() != source.read_bytes():
        target = asset_dir / f"{source.stem}_{source.stat().st_size}{source.suffix}"
    shutil.copy2(source, target)
    reference = args.ref or target.relative_to(path.parent).as_posix()
    refs = document.setdefault("dependencies", {}).setdefault("textures", [])
    if reference not in refs:
        refs.append(reference)
    validation, _ = _commit(path, document, getattr(args, "unsafe_direct_edit", False))
    result = _envelope("add-texture")
    result["warnings"] = validation["warnings"]
    result["errors"] = validation["errors"]
    result["success"] = validation["valid"]
    if result["success"]:
        result["artifacts"] = [str(path), str(target)]
        result["data"] = {"reference": reference, "validation": validation}
    return result


def _cmd_add_mesh(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path)
    source = Path(args.source).resolve()
    if not source.exists() or not source.is_file():
        raise VFXForgeError(f"Mesh source does not exist: {source}", "MESH_SOURCE_MISSING", str(source))
    if source.suffix.lower() not in MESH_ASSET_EXTENSIONS:
        raise VFXForgeError(
            "Supported meshes are Wavefront OBJ, glTF, and binary glTF (GLB).",
            "UNSUPPORTED_MESH_FORMAT",
            str(source),
        )
    document = read_document(path)
    _assert_source_mutation_allowed(path, getattr(args, "unsafe_direct_edit", False))
    asset_dir = path.parent / "assets" / "models"
    asset_dir.mkdir(parents=True, exist_ok=True)
    target = asset_dir / source.name
    if target.exists() and target.read_bytes() != source.read_bytes():
        target = asset_dir / f"{source.stem}_{source.stat().st_size}{source.suffix}"
    shutil.copy2(source, target)
    reference = args.ref or target.relative_to(path.parent).as_posix()
    refs = document.setdefault("dependencies", {}).setdefault("meshes", [])
    if reference not in refs:
        refs.append(reference)
    validation, _ = _commit(path, document, getattr(args, "unsafe_direct_edit", False))
    result = _envelope("add-mesh")
    result["warnings"] = validation["warnings"]
    result["errors"] = validation["errors"]
    result["success"] = validation["valid"]
    if result["success"]:
        result["artifacts"] = [str(path), str(target)]
        result["data"] = {"reference": reference, "validation": validation}
    return result


def _cmd_add_event(args: argparse.Namespace) -> dict[str, Any]:
    data = parse_value(args.data)
    if not isinstance(data, dict):
        raise VFXForgeError("--data must be a JSON object.", "INVALID_EVENT_DATA")
    def mutate(document: dict[str, Any]) -> None:
        events = document.setdefault("timeline", {}).setdefault("events", [])
        event_id = args.id or f"{args.event_id}_{len(events) + 1}"
        events.append({"id": event_id, "event_id": args.event_id, "time": args.time, "data": data})
        events.sort(key=lambda item: float(item.get("time", 0.0)))
    return _cmd_mutate(args, mutate)


def _output_for(source: Path, output: str | None, suffix: str) -> Path:
    if output:
        return Path(output)
    stem = source.name.removesuffix(".vfx.json")
    return source.parent / f"{stem}{suffix}"


def _cmd_render(args: argparse.Namespace) -> dict[str, Any]:
    result = _envelope("render-preview")
    source_files = _targets(args.target)
    output_root = Path(args.output) if args.output else None
    batch_target = Path(args.target).is_dir()
    items = []
    for source in source_files:
        try:
            document = read_document(source)
            validation = validate_document(document, source.parent)
            if not validation["valid"]:
                item = {"path": str(source), "success": False, "errors": validation["errors"], "warnings": validation["warnings"]}
            else:
                output = output_root / f"{source.name.removesuffix('.vfx.json')}.png" if output_root and batch_target else (output_root or _output_for(source, None, ".preview.png"))
                preview = render_preview(document, output, args.time, args.camera, args.width, args.height, args.background, not args.no_grid)
                item = {"path": str(source), "success": True, "warnings": validation["warnings"], "artifacts": [str(output)], "preview": preview}
                result["artifacts"].append(str(output))
            items.append(item)
            result["warnings"].extend([{**warning, "file": str(source)} for warning in item.get("warnings", [])])
            result["errors"].extend([{**error, "file": str(source)} for error in item.get("errors", [])])
        except Exception as exc:
            result["errors"].append({**_error(exc), "file": str(source)})
    if output_root and batch_target:
        output_root.mkdir(parents=True, exist_ok=True)
    result["items"] = items
    result["success"] = not result["errors"]
    return result


def _cmd_export(args: argparse.Namespace) -> dict[str, Any]:
    result = _envelope("export")
    source_files = _targets(args.target)
    output_root = Path(args.output)
    batch_target = Path(args.target).is_dir()
    items = []
    for source in source_files:
        try:
            output = output_root / source.name.removesuffix(".vfx.json") if batch_target else output_root
            exported = export_file(
                source,
                output,
                run_smoke_test=not args.no_smoke_test,
                mode=args.mode,
                resource_root=args.resource_root,
                shared_runtime_path=args.shared_runtime,
            )
            smoke_passed, smoke_payload, smoke_code = engine_gate_result(args.mode, exported)
            item_success = smoke_passed or (
                not args.no_smoke_test and smoke_payload.get("status") == "skipped" and args.mode == "standalone"
            )
            if args.no_smoke_test:
                item_success = True
            item = {"path": str(source), "success": item_success, "export": exported}
            if not item_success:
                smoke_error = {
                    "severity": "error",
                    "code": smoke_code or "EXPORT_SMOKE_FAILED",
                    "path": str(output),
                    "message": "Godot export validation did not pass; inspect export_manifest.json.",
                    "runtime_validation": smoke_payload,
                }
                result["errors"].append({**smoke_error, "file": str(source)})
                item["errors"] = [smoke_error]
            items.append(item)
            result["artifacts"].append(exported["manifest"])
            result["warnings"].extend([{**warning, "file": str(source)} for warning in exported["validation"]["warnings"]])
        except Exception as exc:
            result["errors"].append({**_error(exc), "file": str(source)})
            items.append({"path": str(source), "success": False, "errors": [_error(exc)]})
    result["items"] = items
    result["success"] = not result["errors"]
    return result


def _cmd_migrate(args: argparse.Namespace) -> dict[str, Any]:
    result = _envelope("migrate")
    items = []
    for source in _targets(args.target):
        try:
            document = read_document(source)
            validation = validate_document(document, source.parent)
            item = {"path": str(source), "schema_version": document.get("schema_version"), "validation": validation, "written": False}
            if args.in_place:
                _assert_source_mutation_allowed(source, getattr(args, "unsafe_direct_edit", False))
                if not validation["valid"]:
                    result["errors"].extend([{**error, "file": str(source)} for error in validation["errors"]])
                else:
                    write_document(source, document)
                    item["written"] = True
                    result["artifacts"].append(str(source))
            items.append(item)
            result["warnings"].extend([{**warning, "file": str(source)} for warning in validation["warnings"]])
        except Exception as exc:
            result["errors"].append({**_error(exc), "file": str(source)})
    result["items"] = items
    result["success"] = not result["errors"]
    return result


def _cmd_diff(args: argparse.Namespace) -> dict[str, Any]:
    old = read_document(args.old)
    new = read_document(args.new)
    changes = semantic_diff(old, new)
    result = _envelope("diff")
    result["data"] = {"old": str(args.old), "new": str(args.new), "change_count": len(changes), "changes": changes}
    result["success"] = True
    return result


def _explain(topic: str) -> dict[str, Any]:
    if topic in {"schema", "project"}:
        return schema_description()
    if topic in LAYER_TYPES:
        description = schema_description()
        return {
            "topic": topic,
            "layer": description["layer_fields"][topic],
            "usage": [
                f"vfxforge add-layer effect.vfx.json --type {topic} --id layer_id",
                f"vfxforge update-layer effect.vfx.json --id layer_id --set amount=64",
            ],
        }
    if topic == "export":
        return {
            "topic": "export",
            "command": "vfxforge export effect.vfx.json --output build/Effect",
            "artifacts": ["effect.tscn", "effect.gd", "vfx_runtime.gd", "document.vfx.json", "metadata.json", "textures/", "meshes/", "export_manifest.json"],
            "validation": "Export is blocked by errors and reports a Godot smoke-test status in the manifest.",
        }
    if topic == "overview":
        return {
            "tool": TOOL_NAME,
            "version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "godot_target": GODOT_TARGET,
            "commands": [
                "create", "inspect", "validate", "list-layers", "add-layer", "remove-layer",
                "update-layer", "set", "add-texture", "add-mesh", "add-event", "render-preview", "export",
                "migrate", "diff", "explain", "schema",                 "forge", "plan", "recipes", "policies", "capabilities",
            ],
            "machine_mode": "Append --json to any command. Output uses success, command, errors, warnings, and artifacts.",
        }
    raise VFXForgeError(f"Unknown explain topic '{topic}'. Use explain, schema, or a layer type.", "UNKNOWN_TOPIC")


def _cmd_explain(args: argparse.Namespace) -> dict[str, Any]:
    result = _envelope("explain")
    result["data"] = _explain(args.topic)
    return result


def _load_request(path_value: str) -> dict[str, Any]:
    if path_value == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path_value).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise VFXForgeError("Request must be a JSON object.", "INVALID_REQUEST")
    return data


def _cmd_forge(args: argparse.Namespace) -> dict[str, Any]:
    request = _load_request(args.request)
    result = forge(
        request,
        policy_id=args.policy,
        workspace=args.workspace,
        export=not args.no_export,
        export_mode=args.export_mode,
        resource_root=args.resource_root,
        shared_runtime_path=args.shared_runtime,
        allow_replace=args.allow_replace,
        asset_root=args.asset_root,
    )
    envelope = _envelope("forge")
    envelope["success"] = result.get("production_ready", False)
    envelope["data"] = result
    if not envelope["success"]:
        envelope["errors"] = result.get("errors") or result.get("review_reasons") or []
    return envelope


def _cmd_plan(args: argparse.Namespace) -> dict[str, Any]:
    request = _load_request(args.request)
    data = plan(request, args.policy)
    envelope = _envelope("plan")
    envelope["data"] = data
    envelope["success"] = data.get("status") not in {"failed"}
    if data.get("review_reasons"):
        envelope["warnings"] = data["review_reasons"]
    return envelope


def _cmd_recipes(args: argparse.Namespace) -> dict[str, Any]:
    result = _envelope("recipes")
    if args.action == "list":
        result["data"] = {"recipes": list_recipes()}
        return result
    if not args.name:
        raise VFXForgeError("recipes show requires a recipe id.", "MISSING_RECIPE")
    recipe = load_recipe(args.name)
    result["data"] = {"recipe": _recipe_capability(recipe)}
    return result


def _cmd_policies(args: argparse.Namespace) -> dict[str, Any]:
    result = _envelope("policies")
    if args.action == "list":
        result["data"] = {"policies": list_policies()}
        return result
    if not args.name:
        raise VFXForgeError("policies show requires a policy id.", "MISSING_POLICY")
    policy = load_policy(args.name)
    result["data"] = {"policy": _policy_capability(policy)}
    return result


def _cmd_preset(args: argparse.Namespace) -> dict[str, Any]:
    result = _envelope("preset")
    if args.action == "list":
        result["data"] = {"presets": list_presets()}
        return result
    if not args.name:
        raise VFXForgeError("preset create requires a preset name.", "MISSING_PRESET")
    if not args.output:
        raise VFXForgeError("preset create requires --output.", "MISSING_OUTPUT")
    path = Path(args.output)
    _assert_source_mutation_allowed(path, getattr(args, "unsafe_direct_edit", False))
    if path.exists() and not args.force:
        raise VFXForgeError(f"Refusing to overwrite existing file: {path}. Use --force.", "FILE_EXISTS", str(path))
    document = make_preset(args.name)
    validation = validate_document(document, path.parent)
    result["success"] = validation["valid"]
    result["errors"] = validation["errors"]
    result["warnings"] = validation["warnings"]
    if result["success"]:
        write_document(path, document)
        result["artifacts"].append(str(path))
    result["data"] = {"document_id": document["id"], "validation": validation}
    return result


def _cmd_capabilities(args: argparse.Namespace) -> dict[str, Any]:
    result = _envelope("capabilities")
    result["data"] = capabilities(args.policy)
    return result


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    commands = {
        "create": _cmd_create,
        "inspect": _cmd_inspect,
        "validate": _cmd_validate,
        "list-layers": _cmd_list_layers,
        "add-layer": _cmd_add_layer,
        "remove-layer": _cmd_remove_layer,
        "update-layer": _cmd_update_layer,
        "set": _cmd_set,
        "add-texture": _cmd_add_texture,
        "add-mesh": _cmd_add_mesh,
        "add-event": _cmd_add_event,
        "render-preview": _cmd_render,
        "export": _cmd_export,
        "migrate": _cmd_migrate,
        "diff": _cmd_diff,
        "explain": _cmd_explain,
        "schema": _cmd_explain,
        "preset": _cmd_preset,
        "forge": _cmd_forge,
        "plan": _cmd_plan,
        "recipes": _cmd_recipes,
        "policies": _cmd_policies,
        "capabilities": _cmd_capabilities,
    }
    if not args.command:
        raise VFXForgeError("A command is required. Use vfxforge explain for the command map.", "MISSING_COMMAND")
    return commands[args.command](args)


def _human(result: dict[str, Any]) -> None:
    state = "PASS" if result.get("success") else "FAIL"
    print(f"{state}  {result.get('command', 'vfxforge')}")
    for error in result.get("errors", []):
        location = f" [{error.get('file') or error.get('path')}]" if error.get("file") or error.get("path") else ""
        print(f"ERROR {error.get('code', 'ERROR')}{location}: {error.get('message', error)}")
        if error.get("suggestion"):
            print(f"      Suggestion: {error['suggestion']}")
    for warning in result.get("warnings", []):
        location = f" [{warning.get('file') or warning.get('path')}]" if warning.get("file") or warning.get("path") else ""
        print(f"WARN  {warning.get('code', 'WARNING')}{location}: {warning.get('message', warning)}")
    for artifact in result.get("artifacts", []):
        print(f"ARTIFACT {artifact}")
    if result.get("items") and len(result["items"]) > 1:
        for item in result["items"]:
            print(f"  {item.get('path')}: {'PASS' if item.get('success', item.get('valid', True)) else 'FAIL'}")
    data = result.get("data")
    if data is not None and result.get("command") in {"inspect", "list-layers", "diff", "explain", "schema", "preset", "recipes", "policies", "capabilities"}:
        print(json.dumps(data, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    machine = "--json" in raw_args
    raw_args = [value for value in raw_args if value != "--json"]
    if "--version" in raw_args and len(raw_args) == 1:
        version_data = {
            "tool": TOOL_NAME,
            "version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "godot_target": GODOT_TARGET,
        }
        if machine:
            print(json.dumps({"success": True, "command": "version", "errors": [], "warnings": [], "artifacts": [], "data": version_data}, sort_keys=True))
        else:
            print(f"{TOOL_NAME} {TOOL_VERSION} (schema {SCHEMA_VERSION}, Godot {GODOT_TARGET})")
        return EXIT_OK
    try:
        args = _parser().parse_args(raw_args)
        result = _dispatch(args)
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        command = raw_args[0] if raw_args else "vfxforge"
        result = {"success": False, "command": command, "errors": [_error(exc)], "warnings": [], "artifacts": []}
    if machine:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _human(result)
    if result.get("success"):
        return EXIT_OK
    command = result.get("command")
    data = result.get("data")
    if command == "forge" and isinstance(data, dict):
        return exit_code_for(data)
    error_codes = {str(error.get("code", "")) for error in result.get("errors", []) if isinstance(error, dict)}
    usage_codes = {
        "ARGUMENT_ERROR", "MISSING_COMMAND", "MISSING_OUTPUT", "MISSING_PRESET", "INVALID_ASSIGNMENT",
        "FILE_READ", "INVALID_JSON", "INVALID_ROOT", "FUTURE_SCHEMA", "MIGRATION_FAILED", "TEXTURE_SOURCE_MISSING",
        "MESH_SOURCE_MISSING",
    }
    if error_codes & usage_codes:
        return EXIT_USAGE
    return EXIT_ARTIFACT if command in {"export", "render-preview"} else EXIT_VALIDATION


if __name__ == "__main__":
    raise SystemExit(main())
