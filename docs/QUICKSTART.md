# Quickstart

## Install and launch

The repository is self-contained. Python 3.10+ is required for the CLI and Pillow is used by the deterministic PNG renderer. Godot 4.x is required for the graphical editor and native runtime preview.

~~~
python3 -m venv .venv
.venv/bin/pip install -e .
. .venv/bin/activate
vfxforge --version
godot --path . --editor
~~~

The editor opens examples/arcane_impact.vfx.json by default. Use Open to load another document. The toolbar provides Save, undo/redo, layer creation, playback, speed, camera reset/presets, and stage background controls.

## First AI-authored effect

~~~
mkdir -p work
vfxforge create work/arcane_impact.vfx.json --name "Arcane Impact" --duration 1.5 --seed 18473
vfxforge add-layer work/arcane_impact.vfx.json --type particle --id sparks
vfxforge set work/arcane_impact.vfx.json \
  layers.sparks.amount=64 \
  layers.sparks.lifetime=0.75 \
  layers.sparks.properties.emission_shape=sphere \
  layers.sparks.properties.emission_radius=0.18 \
  layers.sparks.curves.alpha='{"interpolation":"linear","points":[{"x":0,"y":0},{"x":0.1,"y":1},{"x":1,"y":0}]}'
vfxforge validate work/arcane_impact.vfx.json --json
vfxforge render-preview work/arcane_impact.vfx.json --time 0.7 --camera mmo --output work/arcane_impact.png
vfxforge export work/arcane_impact.vfx.json --output work/ArcaneImpact
~~~

## Real 3D model workflow

The portal example includes a real project-relative OBJ model. To use the same workflow in a new effect:

~~~bash
vfxforge create work/totem.vfx.json --name "Totem Pulse" --duration 1.5
vfxforge add-mesh work/totem.vfx.json --source tests/fixtures/models/forge_totem.obj
vfxforge add-layer work/totem.vfx.json --type mesh_effect --id totem
vfxforge set work/totem.vfx.json layers.totem.properties.mesh_asset=assets/models/forge_totem.obj
vfxforge validate work/totem.vfx.json --json
vfxforge export work/totem.vfx.json --output work/TotemPulse
~~~

Godot imports the copied model during export smoke validation, and the manifest records it under `copied_meshes`.

## Preview controls

The 3D stage has orbit/pan/zoom camera interaction, front/side/top/MMO camera presets, a reset-view action, dark/light/night/checker stage modes, a scale dummy and ground plane, play/pause/stop, speed, timeline scrubbing, and a live approximate metric strip.

The timeline displays layer start/end bars and event markers. Curve and gradient widgets support direct manipulation; their numeric JSON fields are present beside the visual editors for precise AI-friendly entry.

## Recovery

Every successful save retains file.vfx.json.bak. The editor autosaves a recovery copy at file.vfx.json.autosave every 30 seconds while dirty. Inspect both before recovering a manually interrupted session.
