# VFX Forge Service Layer Audit

Baseline captured before the intent-driven service implementation. Quality gate and all 18 Python
tests passed; Godot smoke tests passed when Godot 4.x is available.

## What is already right (keep)

| Area | State |
|------|-------|
| Canonical source | `.vfx.json` with stable layer IDs, schema v1, migrations, atomic writes + `.bak` |
| Low-level CLI | Structured `--json` envelopes; create/set/add-layer/validate/export/render-preview |
| Validation | Structured errors/warnings, dependency cycles, asset path safety, budget estimates |
| Presets | Eight authored Python presets compile to valid canonical documents |
| Renderer | Deterministic software PNG preview (single instant) |
| Exporter | Standalone Godot mini-project, manifest, optional headless smoke test |
| Godot runtime | Native layer construction for all layer types; defensive clamps |
| Tests | Model, CLI, renderer/export, user E2E including mesh export |

## Gaps the service layer must fill

| Area | Current | Required |
|------|---------|----------|
| Agent API | Low-level CLI only | High-level `forge` / `plan` semantic contract |
| Recipes | Hardcoded Python in `presets.py` | Versioned data-only JSON recipes + deterministic selector |
| Strict validation | Permissive (`additionalProperties: true`; unknown props ignored) | Service output rejects unknown fields; budgets block |
| Policies | Budget profiles in schema only | Data-only environment policies (e.g. `enigma.json`) |
| Auto-correction | None | Bounded deterministic correction with ledger |
| Result model | `success: bool` only | `ready`, `ready_corrected`, `needs_review`, `failed` + `production_ready` |
| Preview | Single PNG instant | Multi-time preview suite + Godot capture gate |
| Export | Standalone project only | Library/nested export for host games |
| Runtime pathing | `res://vfx_runtime.gd` at project root | Configurable shared runtime for nested bundles |
| Concurrency | Direct filesystem writes | Job workspaces, locks, atomic promotion |
| Enigma | Not integrated | Thin adapter: policy, catalog, spawner, import gates |

## Confirmed permissive behaviors (legacy OK, service NOT OK)

- `schema/vfx.schema.json`: `additionalProperties: true` on root and layers
- Python validation does not reject unknown layer property keys (typos survive)
- Budget breaches emit warnings, not errors
- Layer/event outside duration emits warnings
- Unknown budget profile silently falls back to Medium
- Export CLI treats `smoke_test.status == "skipped"` as success
- Godot runtime clamps values that strict validation should guarantee upstream

## Enigma integration surface (sibling repo)

- `AGENTS.md`: one-concern-per-file, Windows/PCK import discipline, `PackagedIo`
- `world_combat.gd`: combat events wired but no VFX implementation yet
- `BossTelegraphLibrary.cs`: authoritative boss telegraph semantics (server-side)
- VFX must consume gameplay values, never author damage/hit masks/resolution timing

## Architecture target

```
AI agent semantic request
        ↓
VFX Forge Service (recipes, policy, strict validation, correction, gates)
        ↓
Canonical .vfx.json + library export bundle
        ↓
Enigma adapter (catalog, spawner, packaging verification)
```

Core VFX Forge remains generic. Enigma-specific paths and combat wiring live in Enigma only.
