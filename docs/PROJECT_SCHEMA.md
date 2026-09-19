# Project schema

Current schema version: 1.

~~~
{
  "schema_version": 1,
  "id": "arcane_impact",
  "name": "Arcane Impact",
  "duration": 1.5,
  "loop": false,
  "seed": 18473,
  "metadata": {},
  "tags": ["impact", "magic"],
  "layers": [],
  "dependencies": {"textures": [], "meshes": [], "effects": []},
  "timeline": {"events": [], "snap": 0.05},
  "camera_presets": {},
  "budgets": {"profile": "Medium", "custom": {}},
  "export": {
    "godot_version": "4.x",
    "folder_name": "arcane_impact",
    "include_metadata": true,
    "embed_document": true,
    "copy_textures": true,
    "copy_meshes": true
  }
}
~~~

The complete machine-readable shape is schema/vfx.schema.json. vfxforge schema --json includes defaults and enums.

## Layer shape

~~~
{
  "id": "sparks",
  "type": "particle",
  "name": "Sparks",
  "enabled": true,
  "start": 0.0,
  "duration": 1.0,
  "properties": {},
  "material": {},
  "curves": {},
  "gradient": []
}
~~~

properties is type-specific. material is the constrained VFX material surface. curves maps named controls to normalized point arrays. gradient is an ordered list of position and #RRGGBB/#RRGGBBAA stops. mesh_particle and mesh_effect accept an optional project-relative `properties.mesh_asset` reference to an `.obj`, `.glb`, or `.gltf` file; the same reference should also be listed in `dependencies.meshes` for explicit manifests and asset-library tooling.

## Migration

Documents with no schema version are interpreted as an early version 0 shape. If effects is present and layers is absent, it is renamed to layers; missing loop/seed fields receive safe defaults. Future schema versions are rejected with FUTURE_SCHEMA rather than guessed.
