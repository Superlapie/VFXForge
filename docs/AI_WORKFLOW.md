# AI workflow

VFX Forge is designed for deterministic agent workflows. For production effect generation, use the **semantic service path** first. Keep canonical JSON in version control and treat renders, exports, and manifests as derived review artifacts.

## Primary path: semantic forge

~~~
vfxforge capabilities --policy enigma --json
vfxforge plan --request examples/requests/fire_impact.vfxrequest.json --policy default --json
vfxforge forge --request examples/requests/fire_impact.vfxrequest.json --policy enigma --workspace build/service --json
vfxforge recipes list --json
vfxforge recipes show boss.line_sweep --json
vfxforge policies show enigma --json
~~~

The service accepts a versioned semantic request (`*.vfxrequest.json`), selects a recipe deterministically, compiles gameplay semantics into a canonical document, validates under policy ceilings, autocorrects only optional layers, renders previews, exports when the policy requires it, and promotes managed production output.

Use `--policy enigma` for Enigma-target effects. That policy requires library export and host-project engine validation before `production_ready=true`. Agents do not need to pass `--export-mode library`; the policy supplies it. `--no-export` and `--export-mode standalone` must not be treated as production-ready under Enigma policy.

## Discover first

~~~
vfxforge capabilities --policy enigma --json
vfxforge explain --json
vfxforge explain particle --json
vfxforge schema --json
~~~

The schema response describes layer types, default properties, enums, curves, gradients, and budget limits. Stable layer IDs are the preferred addressing mechanism for expert/manual edits.

## Expert path: inspect, edit, validate

Use this only for manual curation, debugging, or core tool development — not as the default AI production workflow.

~~~
vfxforge inspect effect.vfx.json --json > before.json
vfxforge update-layer effect.vfx.json --id sparks --set amount=96 --set lifetime=0.9
vfxforge add-event effect.vfx.json --event-id impact --time 0.08 --data '{"camera_shake":0.25}'
vfxforge add-mesh effect.vfx.json --source assets/models/forge_totem.obj
vfxforge set effect.vfx.json layers.totem.properties.mesh_asset=assets/models/forge_totem.obj
vfxforge validate effect.vfx.json --json
vfxforge render-preview effect.vfx.json --time 0.8 --camera mmo --output review.png --json
~~~

Do not scrape human output. --json is a stable envelope; errors have codes, paths, offending values where useful, and suggestions.

## Review changes

~~~
vfxforge diff before.vfx.json after.vfx.json --json
~~~

The diff is semantic and keys layer fields by IDs, so reordering a layer does not turn every field into a false change.

## Batch jobs

Directory targets are supported:

~~~
vfxforge validate examples --json
vfxforge inspect examples --json
vfxforge render-preview examples --output build/previews --time 0.6 --json
vfxforge export examples --output build/exports --json
vfxforge migrate examples --in-place --json
~~~

Batch items fail independently and retain per-file error paths. The top-level success is false if any item has errors.

## Determinism contract

Same canonical JSON, assets, tool version, and seed produce the same authored/exported structure and the same software preview PNG. Godot runtime particles use the document seed where Godot exposes deterministic particle settings; any remaining engine-level visual variance should be treated as runtime variance, not a reason to mutate the authored seed.

## Real asset workflow

Use `add-mesh` for model ingestion rather than copying an absolute path into JSON. Validation checks that the model remains inside the project and uses an importer-supported extension. Export rewrites the project-relative reference to `meshes/<filename>` and records it in `copied_meshes` in `export_manifest.json`. The `examples/portal.vfx.json` project exercises this with the real `examples/assets/models/forge_totem.obj` asset.
