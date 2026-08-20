# Agent-neutral Kingstack Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move kingstack to a neutral canonical checkout, establish a reusable adapter contract, and ship Claude Code and Codex as the first native parity-tested adapters without losing existing capability or private state.

**Architecture:** Execute five gated phase plans in order. The core contains portable meaning; versioned adapters implement a behavioral contract and publish explicit capability matrices. Renderers return pure in-memory bundles; only the release builder materializes those bundles into uniquely named immutable private releases. Each phase commits its own tests and artifacts, and no manifest-owned link is created until the canonical clone, both prepared adapter releases, shared memory, no-loss proof, and Hassan's pre-link review are complete. The current `~/.claude` installation remains authoritative until cutover.

**Tech Stack:** Python 3 standard library, POSIX shell, JSON, TOML, Markdown, launchd, Claude Code hooks, Codex hooks, Git.

**Spec:** `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md`

## Global Constraints

- Never delete, move, replace, or link an entire `~/.claude`, `~/.codex`, or future agent home, nor touch its auth, transcripts, caches, native memory stores, plugins, or project data.
- Use inventory -> pure rendered bundle -> immutable adapter release -> verify -> atomically rename owned original -> link -> switch. A failed pre-link gate leaves live profiles untouched.
- Every live managed-path change requires a private dated original, an ownership manifest, a release hash, and an exercised rollback path.
- Preserve unrelated Codex settings byte-for-byte. The config merger may only own the explicitly named kingstack keys.
- Do not push any migration commit until the phase verification passes and Hassan reviews the phase summary.
- Keep raw memories and transcripts agent-native. Only human-approved curated memory is shared.
- Keep the original `~/.claude` repository and all existing private snapshot/archive directories untouched. Kingstack creates no new recursive backup artifact and never depends on those historical artifacts for rollback.
- Never track `.kingstack` runtime state, generated adapters, reports containing machine paths, or secret-shaped values.
- Expose no production archive, snapshot, or file-by-file restore command. Whole-home disaster recovery remains outside kingstack and requires a separate human-approved machine-backup procedure.
- Treat Claude and Codex as initial adapters only; every shared interface must admit a third adapter without copying either first-party implementation.

---

## Phase order

1. [Foundation and lossless inventory](2026-08-20-kingstack-foundation-plan.md)
2. [Adapter contract, portable core, and Claude parity adapter](2026-08-20-kingstack-core-claude-plan.md)
3. [Shared curated memory](2026-08-20-kingstack-shared-memory-plan.md)
4. [Codex native adapter](2026-08-20-kingstack-codex-adapter-plan.md)
5. [Versioned activation, schedulers, rollback, documentation, and final acceptance](2026-08-20-kingstack-cutover-plan.md)

## Cross-phase gate

After every phase run the full test suite and that phase's explicit acceptance
command from its own plan:

```bash
python3 -m unittest discover -s tests -v
git status --short
```

Foundation uses inventory/no-loss verification; Core and Shared Memory use
their focused rendered/parity checks; Codex uses isolated-home verification.
`kingstack check --all --mode staged` becomes a gate only after Cutover Task 3
implements it and every required release, memory, and schedule input exists.

The implementing agent records the exact command outputs in the phase's commit
message or handoff. A phase may not start if the preceding plan has unchecked
tasks or an unresolved parity exception. Execution stops after all immutable-release and
clone proofs and before the first live symbolic link so Hassan can review the
exact owned paths, capability matrices, dated originals, commands, and rollback
behavior.
