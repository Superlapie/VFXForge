# Contributing to VFX Forge

VFX Forge is a **community-built** tool. It started as production infrastructure for **Enigma**, a Godot 3D MMO game, and is now maintained in the open so other Godot teams can author, validate, preview, and export real-time VFX at scale.

Pull requests that improve reliability, layer behavior, documentation, CLI ergonomics, or machine-facing workflows are welcome. I review good PRs promptly and would rather merge thoughtful community work than keep this as a solo project.

## Licensing and contributions

By contributing to this repository, you agree that:

1. Your contributions are licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE).
2. You grant Superlapie the right to use, sublicense, and commercially license your contributions as part of VFX Forge under separate commercial license terms offered to paying customers.

You keep copyright in your contributions, but you may not contribute code you do not have the right to license under these terms.

Commercial use of VFX Forge itself still requires a separate commercial license. See [COMMERCIAL.md](COMMERCIAL.md).

## Before you open a PR

1. Read [AGENTS.md](AGENTS.md) for the canonical architecture and safe editing rules.
2. Run the quality gate locally:

   ```bash
   ./scripts/quality-gate
   ```

3. Keep changes focused. Prefer extending shared schema/model/runtime paths over one-off GUI or CLI shortcuts.
4. Never edit generated export artifacts or `.tscn` output as if they were the canonical source.
5. Use `--json` for any CLI changes that affect machine workflows.

## Great first contributions

- Documentation fixes, examples, and clearer validation errors.
- New or improved example `.vfx.json` projects under `examples/`.
- Deterministic renderer or export smoke-test coverage.
- Inspector controls and preview behavior for existing layer types.
- Bug fixes with a reproducible fixture or E2E case.

## Pull request checklist

- [ ] `./scripts/quality-gate` passes (or you explain why a subset is sufficient).
- [ ] CLI JSON output remains stable for existing commands, or the change is documented.
- [ ] New layer types follow the checklist in [AGENTS.md](AGENTS.md).
- [ ] No secrets, credentials, or proprietary assets are added.

## Code of conduct

Be direct, be kind, and optimize for maintainability. Disagreement is fine; harassment is not.

## Questions

Open a [Discussion](https://github.com/Superlapie/VFXForgeEnigma/discussions) for design questions, layer ideas, or integration help. Use [Issues](https://github.com/Superlapie/VFXForgeEnigma/issues) for reproducible bugs and feature requests.
