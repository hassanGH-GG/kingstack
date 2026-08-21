### Core Task 2: Split shared guidance into ordered deterministic fragments

Implement exactly Task 2 in `docs/superpowers/plans/2026-08-20-kingstack-core-claude-plan.md` from base `fa7a2fc`.

Non-negotiable requirements:

1. Freeze the exact tracked root `CLAUDE.md` as the golden fixture with its SHA-256 recorded; use `apply_patch`, not shell redirection.
2. Extract only at existing semantic heading boundaries; do not rewrite, normalize, rewrap, or “improve” prose in this task.
3. `order.json` lists every fragment exactly once and no non-fragment; renderer rejects duplicate/missing/unknown entries, invalid UTF-8, and wrong trailing-newline discipline.
4. Empty Claude appendix must be represented in a deterministic way that preserves byte identity; Codex appendix may be empty at this phase and must not leak foreign guidance.
5. `render_instructions(adapter, root)` must confine adapter selection/path traversal and consume a validated adapter declaration or stable adapter ID.
6. Eliminate `write_staged_instructions`, `--output`, and all mutable staging publication code/tests. The renderer returns an immutable ordered mapping of validated relative path to bytes and performs zero filesystem writes.
7. CLI render is read-only: `--manifest`, `--print-file`, and `--check-file ... --equals ...`; reject conflicting selectors and traversal. Never write or link `~/.claude`, `~/.codex`, or `.staging`.
8. Prove the in-memory rendered `CLAUDE.md` byte-equals both golden fixture and live `~/.claude/CLAUDE.md`; if tracked/live differ, stop and report rather than choosing silently.
9. Run focused/full tests, CLI render, exact `cmp`, py_compile, JSON parse, diff-check, and no-live/hash/link evidence.
10. Preserve descriptor/no-follow source reads and exact fragment-set revalidation, but remove all destination filesystem transaction code.
11. Commit the cross-plan architecture rewrite separately, then commit scoped Task 2 replacement and force-add only append-only `task-2-report.md`; do not push.
