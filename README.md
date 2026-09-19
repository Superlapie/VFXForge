# VFX Forge

VFX Forge is a standalone, offline, AI-first real-time VFX authoring tool for Godot 4.x. The authoritative project is a versioned JSON document. The Godot editor, runtime preview, CLI, deterministic PNG renderer, validation engine, and exporter all consume that same document.

The first production slice includes:

- native Godot runtime layers for particles, mesh particles, sprites, lights, trails, beams, decals, mesh effects, markers, and child effects;
- stable layer IDs, schema migration, atomic saves, recovery backups, curves, gradients, dependencies, timelines, budgets, and validation;
- a professional Godot editor with hierarchy, 3D preview stage, inspector, curve/gradient widgets, timeline scrubbing, camera/background presets, undo/redo, autosave, and keyboard shortcuts;
- a deterministic CLI with structured JSON output, batch validation/export/render/migrate/inspect, semantic diff, self-describing schema help, and eight authored examples;
- self-contained Godot export with relative texture/model dependencies, manifest hashes, generated scoped shader, and a clean-project instantiate smoke test that verifies imported custom mesh geometry.

## Quick start

Godot 4.7.2-stable was used for the verified build. The application targets Godot 4.x and does not require cloud services.

~~~
python3 -m venv .venv
.venv/bin/pip install -e .
. .venv/bin/activate
vfxforge --version
vfxforge preset create arcane_impact --output /tmp/arcane_impact.vfx.json
vfxforge validate /tmp/arcane_impact.vfx.json --json
godot --path . --editor
~~~

Without installing the package, use ./bin/vfxforge in place of vfxforge.

## Useful commands

~~~
vfxforge create effects/arcane_impact.vfx.json --name "Arcane Impact" --duration 1.5
vfxforge add-layer effects/arcane_impact.vfx.json --type particle --id sparks
vfxforge set effects/arcane_impact.vfx.json layers.sparks.amount=64
vfxforge inspect effects/arcane_impact.vfx.json --json
vfxforge validate effects/arcane_impact.vfx.json --json
vfxforge render-preview effects/arcane_impact.vfx.json --time 0.8 --camera mmo --output preview.png
vfxforge export effects/arcane_impact.vfx.json --output build/ArcaneImpact
vfxforge diff old.json new.json --json
~~~

All commands accept --json. Machine output has stable success, command, errors, warnings, and artifacts keys. Exit code 0 means success, 1 validation failure, 2 usage/file failure, and 3 preview/export artifact failure.

## Verification

~~~
./scripts/quality-gate
~~~

The gate runs focused Python model/CLI/renderer tests, user-facing CLI + GUI E2E tests with a real OBJ model, validates and renders all examples, exports them, launches the Godot project headlessly, and runs Godot clean-project export smoke tests when Godot 4 is available. Generated output goes under ignored build/quality. See docs/E2E_TESTING.md.

Read docs/QUICKSTART.md, docs/AI_WORKFLOW.md, and AGENTS.md for the working contract.
