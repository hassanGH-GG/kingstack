# Agent-neutral Kingstack Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move kingstack to a neutral canonical checkout and give Claude Code and Codex native, parity-tested adapters without losing any existing capability or private state.

**Architecture:** Execute five gated phase plans in order. Each phase commits its own tests and artifacts, does not mutate the next phase's live paths, and ends with a rollback or no-loss proof. The current `~/.claude` installation remains authoritative until the final cutover plan.

**Tech Stack:** Python 3 standard library, POSIX shell, JSON, TOML, Markdown, launchd, Claude Code hooks, Codex hooks, Git.

**Spec:** `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md`

## Global Constraints

- Never delete, move, or replace `~/.claude`, `~/.codex`, their auth files, transcripts, caches, native memory stores, or project data.
- Use copy -> stage -> verify -> switch. A failed gate leaves the live profiles untouched.
- Every live-file write requires a private dated backup, an ownership manifest, and an exercised rollback path.
- Preserve unrelated Codex settings byte-for-byte. The config merger may only own the explicitly named kingstack keys.
- Do not push any migration commit until the phase verification passes and Hassan reviews the phase summary.
- Keep raw memories and transcripts agent-native. Only human-approved curated memory is shared.
- Keep the original `~/.claude` repository and a dated snapshot until Hassan separately authorizes deletion.
- Never track `.kingstack` runtime state, generated adapters, reports containing machine paths, or secret-shaped values.

---

## Phase order

1. [Foundation and lossless inventory](2026-08-20-kingstack-foundation-plan.md)
2. [Portable core and Claude parity adapter](2026-08-20-kingstack-core-claude-plan.md)
3. [Shared curated memory](2026-08-20-kingstack-shared-memory-plan.md)
4. [Codex native adapter](2026-08-20-kingstack-codex-adapter-plan.md)
5. [Cutover, schedulers, rollback, and final acceptance](2026-08-20-kingstack-cutover-plan.md)

## Cross-phase gate

After every phase run:

```bash
python3 -m unittest discover -s tests -v
./scripts/kingstack check --staged
git status --short
```

The implementing agent records the exact command outputs in the phase's commit
message or handoff. A phase may not start if the preceding plan has unchecked
tasks or an unresolved parity exception.
