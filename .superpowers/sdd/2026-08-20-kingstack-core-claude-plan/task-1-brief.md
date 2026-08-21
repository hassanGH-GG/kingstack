### Core Task 1: Define the adapter contract and capability matrix

Implement exactly Task 1 in `docs/superpowers/plans/2026-08-20-kingstack-core-claude-plan.md` from base `639fc04`.

Non-negotiable requirements:

1. TDD with exact RED and GREEN evidence.
2. Adapter declaration has exactly these top-level fields and no others: `id`, `contract_version`, `render_module`, `native_home`, `owned_paths`, `model_tiers`, `capability_matrix`.
3. Reject unknown keys, duplicate/absolute/root-owned paths, missing evidence for every non-native status, unknown capability/status/tier, invalid render module, and unmapped tiers.
4. Capability status is exactly `native|emulated|degraded|unsupported`; strict parity must be derived honestly and every non-native entry must explain impact.
5. The synthetic example adapter must validate without importing Claude or Codex implementation modules or containing either vendor name in its render module.
6. Claude/Codex declarations are declarations only; do not render, activate, link, or alter native homes.
7. CLI contract checks must work for `--adapter claude`, `--adapter codex`, and `--adapter-path tests/fixtures/adapters/example` with mutually coherent argument validation.
8. JSON schemas and Python validation must agree; tests must exercise both, not merely file presence.
9. Run focused tests, full current suite, all three CLI checks, py_compile, `git diff --check`, and explicit native/protected-state checks.
10. Commit only Task 1 scope as `feat: define the agent adapter contract`; do not push.
11. Append unabridged RED/GREEN/CLI/full/no-live-change evidence to `task-1-report.md`.
