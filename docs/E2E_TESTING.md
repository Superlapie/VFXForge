# End-to-end testing

The user-facing E2E suite is `tests/test_user_e2e.py`. It drives the installed surface exactly as a human or coding agent would:

1. `bin/vfxforge create` creates a canonical project.
2. `add-mesh` ingests the real OBJ fixture at `tests/fixtures/models/forge_totem.obj`.
3. `add-layer`, `set`, `add-event`, `list-layers`, `inspect`, and `validate` edit and inspect the same document.
4. `render-preview` produces deterministic PNG output.
5. `export` produces standalone Godot content and a manifest with copied model assets.
6. Godot imports the exported OBJ and the test asserts real mesh surfaces for both `mesh_effect` and `mesh_particle`.
7. `gui_user_smoke.gd` loads `examples/portal.vfx.json` into the graphical editor, verifies the responsive hierarchy/preview/inspector/timeline layout, exercises reset-view and add-layer controls, edits a particle property through the inspector, undoes/redoes the edit, verifies future-schema rejection, and seeks the runtime preview.

Run only the user-facing suite:

~~~bash
python3 -m unittest tests.test_user_e2e -v
~~~

Run the release gate, which includes the focused unit suites, this E2E suite, batch operations, deterministic previews, Godot project startup, and clean export smoke tests:

~~~bash
./scripts/quality-gate
~~~

The GUI test is skipped when no Godot 4 executable is available. Set `VFXFORGE_GODOT=/absolute/path/to/godot` to select a specific binary. The verified workspace binary is Godot 4.7.2-stable.

The OBJ is intentionally a small, deterministic low-poly totem rather than a placeholder primitive. It has separate base, shaft, and crystal geometry and is suitable for testing project-relative model ingestion, Godot import, mesh instantiation, scaling, and live editor rebuilds without adding a large binary asset to the repository.
