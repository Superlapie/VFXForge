# Architecture

~~~
canonical JSON model
        ↓
Python normalization / validation / migration
        ↓
Godot VFXRuntime          deterministic software preview
        ↓                          ↓
Godot editor GUI              CLI / AI API
        ↓                          ↓
Godot exporter / manifest / clean smoke test
~~~

## Boundaries

- vfxforge/schema.py: defaults, registries, enums, budgets, self-description.
- vfxforge/model.py: migration, path addressing, atomic persistence.
- vfxforge/validation.py: structured errors, dependency safety, estimates, budgets.
- vfxforge/renderer.py: offline deterministic PNG review surface.
- vfxforge/cli.py: machine-facing command dispatcher and batch envelopes.
- godot/model/vfx_document.gd: GUI-side model adapter with the same document shape.
- godot/runtime/vfx_runtime.gd: native runtime layer construction and lifecycle.
- godot/app/Main.gd: editor layout, selection, inspector, undo/redo, autosave, preview wiring.
- godot/editor/*.gd: curve, gradient, and timeline widgets.
- vfxforge/exporter.py: standalone Godot output and post-export smoke test.

The GUI does not own a separate authoritative property graph. It selects stable IDs and invokes model path mutations. Undo/redo stores model mutations/snapshots. Export embeds a normalized document and copies only declared dependencies.

## Extension points

Layer defaults, validation, preview rendering, Godot runtime creation, GUI controls, schema description, presets, and tests are intentionally separate. Adding a type requires touching these explicit registries, not adding a hidden property in one screen.
