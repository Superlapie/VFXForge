# VFX Forge Service Architecture

Three-layer separation:

```
┌─────────────────────────────────────────┐
│ Enigma Adapter (Enigma repo only)       │
│ requests/, catalog, spawner, verify gates │
└───────────────────┬─────────────────────┘
                    │ semantic JSON + policy id
┌───────────────────▼─────────────────────┐
│ VFX Forge Service (this repo)           │
│ forge / plan / recipes / policies       │
└───────────────────┬─────────────────────┘
                    │ canonical .vfx.json
┌───────────────────▼─────────────────────┐
│ VFX Forge Core (existing)               │
│ model, validation, renderer, exporter   │
└─────────────────────────────────────────┘
```

## Service modules

| Module | Role |
|--------|------|
| `vfxforge/service/request.py` | Semantic request contract (`additionalProperties: false`) |
| `vfxforge/service/selector.py` | Deterministic recipe selection |
| `vfxforge/service/compiler.py` | Recipe + request → canonical document |
| `vfxforge/service/policy.py` | Environment ceilings (`policies/*.json`) |
| `vfxforge/service/autocorrect.py` | Bounded correction ledger |
| `vfxforge/service/pipeline.py` | `forge()` and `plan()` orchestration |
| `vfxforge/service/promotion.py` | Job workspaces + atomic promotion |
| `vfxforge/service/preview_suite.py` | Multi-time deterministic previews |
| `vfxforge/property_spec.py` | Strict property registry |

## Production readiness

`production_ready == true` only when:

- request validates
- recipe resolves unambiguously
- strict validation passes (after optional correction)
- export smoke passes when policy requires it (`policies/enigma.json`: `require_godot_smoke: true`)
- promotion succeeds without effect-id conflict

Statuses: `ready`, `ready_corrected`, `needs_review`, `failed`

## CLI

```bash
vfxforge forge --request examples/requests/fire_impact.vfxrequest.json --policy default --json
vfxforge plan --request examples/requests/fire_impact.vfxrequest.json --policy default --json
vfxforge recipes list --json
vfxforge policies show enigma --json
vfxforge export effect.vfx.json --output build/out --mode library --resource-root res://generated/vfx/my_effect
```

## Enigma integration path (adapter-owned)

1. Pin VFX Forge in Enigma `toolchain.lock.json`
2. Store semantic requests in `content/vfx/requests/*.vfxrequest.json`
3. Wrapper script calls `vfxforge forge --policy enigma`
4. Promoted bundles land in `client/generated/vfx/<effect_id>/`
5. Shared runtime at `client/generated/vfx/_runtime/vfx_runtime.gd`
6. `VfxCatalog` / `VfxSpawner` resolve effect IDs → `PackedScene`
7. Verify through existing `import-client.sh` / `verify-client-imports.sh` gates

VFX Forge does not import Enigma source. Enigma policy is data in `policies/enigma.json`.

## Enigma adapter (implemented)

Enigma owns the thin integration layer:

| Path | Purpose |
|------|---------|
| `scripts/vfxforge.sh` | Resolve sibling `VFXForgeEnigma`, run CLI |
| `scripts/generate-vfx.sh` | Safe forge + install to `client/generated/vfx/` |
| `scripts/verify-vfx.sh` | Import + headless catalog smoke |
| `content/vfx/requests/` | Semantic request fixtures |
| `content/vfx/catalog.json` | Effect ID → scene path registry |
| `client/generated/vfx/_runtime/` | Shared `vfx_runtime.gd` / `vfx_trail.gd` |
| `client/presentation/vfx/vfx_catalog.gd` | Catalog loader (`PackagedIo`) |
| `client/presentation/vfx/vfx_spawner.gd` | `VfxSpawner.spawn(effect_id, parent, transform)` |
| `client/tools/test_vfx_catalog.gd` | Headless host-project gate |
| `toolchain.lock.json` | Pinned VFX Forge commit + override env |
| `.cursor/rules/vfx-forge.mdc` | Agent workflow rule |

Example:

```bash
cd Enigma
scripts/generate-vfx.sh content/vfx/requests/fire_impact.vfxrequest.json
scripts/verify-vfx.sh combat_fire_impact
```
