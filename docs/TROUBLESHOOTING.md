# Troubleshooting

## Godot is not found

The CLI model, validation, diff, and Pillow PNG renderer work without Godot. Install Godot 4.x or set VFXFORGE_GODOT=/absolute/path/to/godot for native export smoke tests. The verified workspace binary was 4.7.2.stable.official.ed1daf0bf.

## Export reports missing texture

References are relative to the source document. Import files first:

~~~
vfxforge add-texture effect.vfx.json --source art/impact.png --json
~~~

Then inspect dependencies.textures and layer properties.texture/material.texture references. Export never silently drops a missing dependency.

## Export reports missing mesh

Model references are relative to the source document and must use `.obj`, `.glb`, or `.gltf`. Import a model into the project first:

~~~
vfxforge add-mesh effect.vfx.json --source art/forge_totem.obj --json
~~~

Then set the mesh layer's `properties.mesh_asset` to the returned project-relative reference. Inspect `dependencies.meshes`; export copies the model to `meshes/` and reports it in `export_manifest.json`.

## The GUI opens an empty effect

Open a *.vfx.json file with the Open button, or launch Godot with a document path as an argument:

~~~
godot --path . --editor -- examples/fire_impact.vfx.json
~~~

The editor otherwise opens examples/arcane_impact.vfx.json when present.

## A project will not save

Check the status label and filesystem permissions. The model writes a temporary file, flushes it, preserves a .bak, and replaces the destination. A validation error prevents mutation saves so the last good file remains intact.

## Visual differences

Use the same document, asset files, tool version, and seed. The CLI PNG renderer is deterministic and intentionally approximates the 3D stage. Godot runtime rendering is authoritative for final appearance and can vary with renderer, GPU, and engine settings.
