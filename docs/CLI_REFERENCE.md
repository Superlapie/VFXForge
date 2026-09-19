# CLI reference

All commands accept --json anywhere in the argument list.

## Core commands

| Command | Purpose |
| --- | --- |
| create PATH | Create a complete document; supports --name, --duration, --loop, --seed, --preset, --force. |
| inspect TARGET | Print normalized document and validation data. Directories are batch targets. |
| validate TARGET | Validate one file or a directory. Supports --budget. |
| list-layers PATH | List ordered IDs, types, names, enabled state, and timing. |
| add-layer PATH --type TYPE --id ID | Append a typed layer from canonical defaults. |
| remove-layer PATH --id ID | Remove one layer by stable ID. |
| update-layer PATH --id ID --set FIELD=VALUE | Mutate fields relative to one layer. |
| set PATH PATH=VALUE ... | Mutate document paths or layers.ID.FIELD paths. Values parse as JSON first. |
| add-texture PATH --source FILE | Copy PNG/JPG/JPEG/WebP into assets/textures and add a dependency. |
| add-mesh PATH --source FILE | Copy OBJ/glTF/GLB into assets/models and add a `dependencies.meshes` entry. |
| add-event PATH --event-id ID --time SECONDS | Append a timeline event with optional JSON --data and --id. |
| render-preview TARGET | Produce deterministic PNG snapshots; supports --time, --camera, --output, --width, --height, --background. |
| export TARGET --output DIR | Emit standalone Godot content and manifest; directory targets export independently. |
| migrate TARGET --in-place | Normalize old documents and write current schema only when validation passes. |
| diff OLD NEW | Report semantic field-level changes. |
| explain TOPIC | Describe commands, schema, layer type, or export. |
| schema | Alias for explain schema. |
| preset list / preset create NAME --output PATH | List or write authored starter effects. |
| forge --request FILE --policy ID | Generate production VFX from a semantic request. Policy selects export mode and engine gate. |
| plan --request FILE --policy ID | Resolve recipe and review reasons without promoting. |
| recipes list / recipes show ID | List recipe IDs or show required/consumed gameplay. |
| policies list / policies show ID | List policies or show production gates and ceilings. |
| capabilities --policy ID | Agent discovery of recipes, required inputs, and production requirements. |

## Machine envelope

~~~
{
  "success": true,
  "command": "validate",
  "errors": [],
  "warnings": [],
  "artifacts": [],
  "items": []
}
~~~

Exit codes:

- 0: command completed successfully;
- 1: validation failed;
- 2: malformed arguments, missing files, or document read/migration failure;
- 3: preview/export artifact failure;
- 4: `forge` returned `needs_review` (not production-ready).

## Path examples

~~~
vfxforge set effect.vfx.json name='"Fire Impact"'
vfxforge set effect.vfx.json duration=1.35 loop=false seed=40391
vfxforge set effect.vfx.json layers.embers.properties.gravity='[0,-2,0]'
vfxforge set effect.vfx.json layers.bolt.curves.width='{"points":[{"x":0,"y":0},{"x":1,"y":1}]}'
vfxforge add-mesh effect.vfx.json --source assets/forge_totem.obj
vfxforge set effect.vfx.json layers.totem.properties.mesh_asset=assets/models/forge_totem.obj
~~~

Bare strings can omit JSON quoting. Use JSON quoting when a string contains spaces or must not be interpreted as a number/boolean.
