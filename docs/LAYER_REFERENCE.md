# Layer reference

All layers have stable IDs, name, enabled, start, duration, material settings, curves, and a gradient. The current registry contains:

| Type | Native/runtime role | Important fields |
| --- | --- | --- |
| particle | GPUParticles3D + ParticleProcessMaterial | amount, one_shot, lifetime, explosiveness, randomness, emission shape, velocity, gravity, damping, radial/tangential acceleration, scale, rotation |
| mesh_particle | GPUParticles3D with a primitive or imported custom mesh | amount, lifetime, mesh, mesh_asset (.obj/.glb/.gltf), size, spread, velocity, gravity |
| sprite | billboard QuadMesh | texture, size, flipbook columns/rows/frames/FPS, billboard |
| light | OmniLight3D | color, energy, range, shadow, energy curve |
| trail | ribbon mesh with history and width falloff | width, lifetime, segments, color, alpha, UV mode |
| beam | segmented deterministic ribbon | source, target, thickness, segments, noise, scroll speed, fade, color |
| decal | ground PlaneMesh | texture, size, color, height, fade, rotation |
| mesh_effect | primitive or imported custom MeshInstance3D | mesh, mesh_asset (.obj/.glb/.gltf), size, rotation, rotation speed, dissolve/pulse, tint |
| audio_marker | timing metadata | event ID, trigger time, volume, pitch, variation |
| event_marker | external game event metadata | event ID, trigger time, payload |
| child_effect | nested VFX runtime or scene | effect ID/path, trigger, offset, transform inheritance, max instances |

Particle emission shapes are point, box, sphere, sphere surface, ring, disc, line, and cone in the canonical format. Godot-native mappings use the closest safe process-material primitive where Godot does not expose a direct shape.

Material controls are blend mode, unshaded, billboard, depth behavior, texture, tint, UV scroll, distortion, dissolve, fresnel, and emissive intensity. The runtime intentionally avoids an unrestricted shader graph.

## Curves

Curves use normalized x coordinates from 0 to 1 and arbitrary finite y values:

~~~
{"interpolation":"linear","points":[{"x":0,"y":0},{"x":0.2,"y":1},{"x":1,"y":0}]}
~~~

The GUI curve widget supports click-to-add, drag, and right-click removal. Numeric JSON editing and CLI path mutation provide precise control.
