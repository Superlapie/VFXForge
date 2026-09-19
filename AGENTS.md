# VFX Forge agent guide

VFX Forge is an offline Godot 4.x VFX authoring application. It is deliberately constrained to game-ready real-time effects rather than being a general-purpose DCC or shader IDE.

## Primary AI workflow (service)

For AI and content-generation agents, the **primary production workflow** is semantic intent through the service layer:

~~~
vfxforge plan --request content/effects/my_effect.vfxrequest.json --policy enigma --json
vfxforge forge --request content/effects/my_effect.vfxrequest.json --policy enigma --workspace build/service --json
~~~

Use `vfxforge capabilities --policy enigma --json` to discover supported recipes, required gameplay, and production gates. `vfxforge recipes show` and `vfxforge policies show` now return the same agent-facing fields. The service selects a recipe, compiles gameplay semantics (tile scale, tell timing, shape geometry), validates strictly, optionally autocorrects within policy bounds, renders a preview suite, exports when required, and promotes managed production output.

`--policy enigma` automatically uses library export and host-project smoke. Do not pass `--export-mode standalone` unless you intend `needs_review`. **Do not** hand-author `.vfx.json` layer graphs for normal production requests. **Do not** return `production_ready` when required semantics were ignored or verification was skipped.

Low-level document mutation (`set`, `add-layer`, `update-layer`, `add-event`) remains available for expert debugging, manual curation, and core development — not as the default agent workflow.

## Source of truth

For managed semantic production:

1. The `*.vfxrequest.json` request is the authoritative creative/gameplay intent.
2. The compiled `*.vfx.json` document is the canonical VFX intermediate representation.
3. Godot export (scenes, runtime, textures) is a derived backend artifact.

GUI state is not authoritative. Python model code normalizes/migrates documents, the CLI mutates them, and the Godot editor loads the same JSON through godot/model/vfx_document.gd.

Never edit a .tscn, generated shader, export manifest, or exported effect.gd as the source of an effect. Regenerate those artifacts with `vfxforge forge` or `vfxforge export`.

The current schema is version 1. The root requires schema_version, stable id, name, positive duration, boolean loop, integer seed, and an ordered layers array. Layer IDs are stable and are the addressable namespace for AI edits:

~~~
layers.sparks.amount=64
layers.sparks.properties.gravity=[0,-4,0]
~~~

For expert/manual document editing only, prefer vfxforge set, vfxforge add-layer, vfxforge update-layer, and vfxforge add-event. Do not use ad-hoc JSON text replacement.

Use `vfxforge add-texture` and `vfxforge add-mesh` to ingest project assets. Mesh references are project-relative `.obj`, `.glb`, or `.gltf` paths, normally stored in `dependencies.meshes` and on `mesh_particle`/`mesh_effect` as `properties.mesh_asset`.

## Safe mutation pattern

1. Read or create the canonical document.
2. Apply a deterministic, explicit mutation.
3. Run vfxforge validate file.vfx.json --json.
4. Save through the CLI/model atomic writer.
5. Render a preview when visual behavior changed.
6. Export only after validation passes.
7. Review vfxforge diff old.vfx.json new.vfx.json --json for AI-generated changes.

The writer creates a temporary file, flushes it, preserves a .bak recovery copy, then replaces the destination. A malformed parse must never overwrite a good project.

Unsafe patterns:

- editing generated Godot output as if it were the canonical source;
- inventing duplicate layer IDs or changing IDs to reorder layers;
- adding random behavior without exposing/setting a seed;
- ignoring validation errors before export;
- using absolute machine-specific asset paths;
- deleting a project or export tree when an overwrite or a new output directory is sufficient.

## Commands and tests

Use vfxforge explain, vfxforge explain particle, vfxforge explain export, and vfxforge schema --json for machine-discoverable syntax and fields.

~~~
python3 -m unittest discover -s tests -v
./scripts/quality-gate
~~~

The quality gate is the release check. Godot 4.7.2-stable was the verified binary in this workspace; set VFXFORGE_GODOT when using another Godot 4 executable.

## Adding a layer type

1. Add defaults and self-description in vfxforge/schema.py.
2. Add range/type validation in vfxforge/validation.py.
3. Add deterministic software preview behavior in vfxforge/renderer.py.
4. Add a native runtime constructor/update path in godot/runtime/vfx_runtime.gd.
5. Add inspector controls in godot/app/Main.gd.
6. Add the type to schema/vfx.schema.json.
7. Add a fixture/example and tests.
8. Update docs/LAYER_REFERENCE.md.

Keep layer creation and export data-driven. Do not scatter unrelated special cases across the GUI.

## Schema compatibility

Never silently reinterpret a field. Add a migration in vfxforge/model.py, increment SCHEMA_VERSION only when necessary, document the migration, and retain old fixtures. Documents with a newer schema must fail with a structured FUTURE_SCHEMA error.

## Export expectations

An export must be self-contained Godot content with relative resources, effect.tscn as entry scene, effect.gd, the standalone runtime, copied textures and meshes, document.vfx.json, metadata, and export_manifest.json. Successful JSON serialization is not enough: Godot must import referenced model assets and instantiate the scene without resource-loader, parse, compile, or runtime errors when Godot is available.
