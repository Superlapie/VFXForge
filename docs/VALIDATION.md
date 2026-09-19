# Validation and budgets

Validation is used by inspect, validate, save mutation, export, and the GUI basic model checks. Python validation returns errors and warnings without crashing on malformed documents.

## Errors

Examples include invalid root/schema, missing or duplicate IDs, unknown layer types, invalid numbers/vectors, invalid curve or gradient ordering, unsupported blend modes, missing textures or meshes, unsupported model formats, dependencies escaping the project, and child-effect cycles.

## Warnings

Warnings cover zero-particle emitters, layers extending past effect duration, long effects, estimated particle/draw/light/layer budget overruns, unknown profiles, and transparent-layer overdraw risk. Estimates are labeled estimates; they are not GPU profiler readings.

## Budgets

Built-in profiles are Mobile, Low, Medium, High, Boss, and Cinematic. Each sets maximum estimated particles, lights, draw calls, and layer count. The document selects a profile at budgets.profile; a CLI --budget selection is useful for review without mutating the project.

~~~
vfxforge validate effect.vfx.json --budget Mobile --json
~~~

Errors block mutation commits and export. Warnings remain visible and do not block a deliberate export.
