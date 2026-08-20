### Core Task 3: Replace vendor model names with portable capability tiers

Implement exactly Task 3 in `docs/superpowers/plans/2026-08-20-kingstack-core-claude-plan.md` from base `8ad1306`.

Non-negotiable requirements:

1. TDD with exact RED and GREEN evidence; do not write production code before the failing routing tests.
2. Shared `core/routing/policy.json` contains work classes and only portable tiers/effort: waiting→none/none, mechanical→economical/low, precise→balanced/medium, judgment→frontier/high. It must contain no vendor/model names.
3. Claude and Codex model maps remain adapter-owned and must match the declarations' `model_tiers`; reject missing/extra tiers, unknown work classes, malformed models/effort, duplicate or non-adjacent fallback edges, cycles, and ambiguous availability overrides.
4. `resolve()` returns the selected model, effort, tier, work class, and evidence/reason. `fallback()` moves exactly one adjacent tier, returns the chosen tier and reason, and fails visibly when no valid adjacent tier exists. Availability overrides live only in injected private runtime state, never shared policy or checked-in adapter maps.
5. Make `core/instructions/40-model-and-context.md` vendor-neutral. Move Claude-specific model names and `/model` behavior into the Claude appendix. Codex guidance must contain no Haiku/Sonnet/Opus/Fable names; Claude guidance must contain no `gpt-5.6-sol|terra|luna` names.
6. Preserve the meaning of the current routing rules: explicit model and effort on every spawn, report both to the parent/user, cheapest suitable tier first, one adjacent fallback only on availability failure, no blanket override, main-thread effort default medium, context/compaction rules unchanged.
7. Keep render bundles pure/read-only. Do not recreate `.staging`, destination writers, release materialization, live links, native-home writes, schedule changes, or activation.
8. Prove routing for Claude, Codex, and a synthetic/in-memory availability override. Include negative/adversarial tests for schema/type/unknown key/path-independent data, unavailable tiers, and deterministic fallback behavior.
9. Run focused routing and render/contract regressions, the full suite, both foreign-name scans, all relevant CLI checks, py_compile, JSON parsing, `git diff --check`, repo cleanliness, and explicit native hash/type/link evidence.
10. Append unabridged RED/GREEN/full/CLI/no-live-change evidence to `task-3-report.md`, commit only Task 3 scope as `feat: route work through portable capability tiers`, and do not push.
