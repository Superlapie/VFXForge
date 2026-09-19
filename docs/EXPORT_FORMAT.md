# Export format

vfxforge export effect.vfx.json --output build/Effect creates a clean, self-contained Godot directory:

~~~
Effect/
├── effect.tscn
├── effect.gd
├── vfx_runtime.gd
├── godot/runtime/vfx_trail.gd
├── document.vfx.json
├── metadata.json
├── export_manifest.json
├── project.godot
├── materials/README.md
├── shaders/vfx_unlit.gdshader
├── effects/                 (when child effects are referenced)
├── textures/
└── meshes/                  (when imported 3D models are referenced)
~~~

The scene is ordinary Godot content. effect.gd embeds the normalized document so the effect can be instantiated without VFX Forge at runtime. The runtime uses native GPUParticles3D, ParticleProcessMaterial, MeshInstance3D, OmniLight3D, materials, and generated immediate meshes.

Texture dependencies are copied into textures/ and mesh dependencies into meshes/, with relative references rewritten in the exported document. Child effect documents are copied into effects/ and their stable references are rewritten to relative paths. The manifest records every generated file, byte count, SHA-256, entry scene, VFX Forge version, schema version, validation result, copied textures, copied meshes, and smoke-test result.

When Godot 4 is available, export first opens the generated directory as a clean Godot project so model assets are imported, then creates a temporary smoke script, loads effect.tscn, instantiates it, waits two frames, and rejects nonzero exits, parse/compile errors, resource-loader errors, or runtime errors. Temporary smoke/cache files are not part of the export manifest. If Godot is not installed, the manifest reports skipped with an actionable reason.
