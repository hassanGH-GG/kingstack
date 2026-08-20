### Core Task 4: Make the skill catalog single-source and pstack-safe

Implement exactly Task 4 in `docs/superpowers/plans/2026-08-20-kingstack-core-claude-plan.md` from base `9d5e48b`.

Non-negotiable requirements:

1. Strict TDD with exact RED/GREEN evidence. Freeze and prove the complete 65-name Claude baseline before moving or transforming any source.
2. One catalog is authoritative. Every entry declares `name`, owner (`kingstack|pstack|adopted|plugin-manager`), source, targets, dependencies, and optional transform. Reject unknown keys/owners/targets, duplicate or Unicode/casefold-colliding names/paths, missing source/SKILL.md, invalid frontmatter, dependency cycles/missing dependencies, unsafe paths/symlinks, and owner/source contradictions.
3. Move only kingstack-authored `king-mode` and `memory-review` into `core/skills/authored/` using apply_patch-safe edits. Pstack remains upstream-owned at frozen revision `63d938c`; do not hand-edit its generated skills. Plugin-managed skills are cataloged for parity but never copied into bundles.
4. Refactor pstack sync behind one adapter-aware pure entry point. It returns/prints immutable bundle-manifest data and performs no native-home or mutable staging publication. Preserve clobber-manifest detection: reject an installed/generated file whose hash differs, and never overwrite authored or plugin-managed content.
5. Adapter transforms may change only documented host tokens/frontmatter/model/tool/path fields. Fail if forbidden foreign-host terms remain. Prove normalized headings, instruction paragraphs, referenced resource names, and script hashes preserve meaning for every portable skill.
6. Claude bundle must expose at least and exactly the expected 65 baseline skill names according to ownership semantics. Codex bundle must contain the portable eligible subset plus explicit unsupported/plugin-managed accounting; it must not silently claim unavailable skills.
7. The synthetic third-adapter/provider extension must remain independent of Claude/Codex implementation modules; do not hardcode a first-party-only skill filename map in core.
8. Preserve pure immutable rendering. Do not recreate `.staging`, destination writers, release materialization, live links, native-home writes, schedule changes, activation, or Superpowers disablement.
9. Run focused skill tests, routing/render/contract regressions, full suite, both adapter manifests/catalog checks, pstack check, normalized semantic comparisons, py_compile/JSON/shell syntax/diff checks, and explicit native hashes/types/no-current-links/no-loss evidence.
10. Append unabridged RED/GREEN/full/CLI/no-live evidence to `task-4-report.md`; explicit-path stage only; commit scoped Task 4 as `refactor: make skills and pstack adapter-neutral`; no push.
