# Agent-neutral kingstack migration handoff

Status date: 2026-08-20

This document is the durable continuation and review entry point for another
Claude or Codex session. Do not rely on the originating conversation.

## Repository state

- Canonical repository: `/Users/mac/Desktop/Work/kingstack`
- GitHub origin: `https://github.com/hassanGH-GG/kingstack.git`
- Working branch: `feat/agent-neutral-kingstack`
- Current Task 4 implementation head: `c53ae8752a0c8b3ca533b94cb38d2792bacb5b44`
- The branch is intentionally unfinished. Do not merge it to `main`, tag a
  release, or activate it merely because it is available remotely.
- Detailed append-only evidence lives in
  `.superpowers/sdd/2026-08-20-kingstack-core-claude-plan/task-*-report.md`.
- The task ledger and implementer briefs live beside those reports. They are
  normally ignored but are intentionally committed on the unfinished handoff
  branch so another agent can continue without this session.

## User requirements that remain binding

1. Preserve every Claude and Codex native file, memory, inbox entry, skill,
   pstack source, authentication token, session, cache, and schedule.
2. Native `~/.claude` and `~/.codex` remain real directories. Never replace an
   entire native home with a symlink.
3. No live adapter link or activation may occur until the prepared releases,
   rollback, health, and no-loss proofs pass and Hassan receives a complete
   pre-link briefing and explicitly approves it.
4. Keep the design agent-neutral: Claude, Codex, and a synthetic third adapter
   must use the same core contract without first-party branching in core.
5. Pstack stays upstream-owned at revision `63d938c`; never hand-edit generated
   pstack skills.
6. Renderers are pure functions returning immutable `relative path -> bytes`
   bundles. Do not recreate mutable `.staging` publication.
7. Do not push directly to `main`. The feature branch may be pushed as an
   explicitly unfinished handoff.
8. At final completion, safely disable Superpowers only after replacement
   parity, delete the six specifically requested plan files, review exact final
   commits/tag, and push only after verification.

## Architecture established so far

- A seven-field adapter declaration defines identity, contract version, render
  provider, native home, granular owned paths, model tiers, and capability
  matrix.
- The neutral renderer loads a declaration-selected provider and returns an
  immutable, sorted bundle. It has no destination writer.
- Portable routing uses work classes `waiting`, `mechanical`, `precise`, and
  `judgment`, mapped through adapter-owned economical/balanced/frontier model
  tiers and explicit effort.
- Availability overrides are injected private runtime data; checked-in shared
  policy never contains account availability.
- Skills have one ownership catalog: `kingstack`, `pstack`, `adopted`, or
  `plugin-manager`. Plugin-managed skills are accounted for but never bundled.
- Future materialization belongs only to uniquely named immutable releases.
  Activation and rollback are not implemented or authorized yet.

## Approved completed work

### Foundation

- Acceptance commit: `639fc04`
- Frozen public baseline SHA-256:
  `8d943deaa440a279452e3af79400c6651722306936d2d90922692810722ddf27`
- Counts: Claude 587 entries, Codex 434 entries, 14 memory banks.
- Native homes and all historical snapshot/archive roots remained intact.

### Core Task 1 — adapter contract

- Final approved commit: `fa7a2fc`
- Final review: APPROVE, no findings.
- Focused 27/27 and full 58/58 at approval.

### Core Task 2 — immutable instruction bundles

- Architecture replacement: `bf906ff`
- Pure-bundle implementation: `be12312`
- Portable rendered-path fix: `8ad1306`
- Final review: APPROVE, no findings.
- Exact pre-routing Claude guidance baseline: 9,525 bytes, SHA-256
  `7a6f34e0ff3777279053bb63713dfc109761d508f18fef0316279e9a74fdab2e`.

### Core Task 3 — portable routing

- Implementation: `8ce2975`
- Boundary fixes: `a4f4dc9`, `9d5e48b`
- Final review: APPROVE, no findings.
- All 49 malformed mapping-key combinations return stable `RoutingError`.
- Foreign-model scans are clean in both rendered adapters.

## Core Task 4 — current closure work

Committed implementation:

- `190587c` — single-source skills and pure pstack integration
- `07cd989` — source, parity, clobber, ownership, and Codex accounting safety

Last committed green evidence before the final closure batch:

- Focused skills: 18/18
- Full suite: 102/102
- Claude accounting: 53 bundled, 12 plugin-managed, 0 unsupported
- Codex accounting: 41 bundled, 11 plugin-managed, 13 unsupported
- Pstack revision: `63d938c`
- Protected native hashes/types unchanged; adapter `current` links absent

Five independently reproduced Important gaps were closed in `c53ae87`:

1. Descriptor cleanup must own both root and upstream descriptors from the
   first successful open, including second-open and every early-validation
   failure. The old code leaked one or two descriptors on early failure.
2. `model`, `tool`, `path`, and `host` transform kinds must constrain token
   shapes and context. A whole instruction paragraph must not be accepted as a
   declared `path` replacement, and independent parity must still catch body
   destruction.
3. Codex unsupported status must propagate through catalog dependencies. Known
   hard edges:
   - `architect -> how, why, arena, interrogate`
   - `blast-radius -> how, why, arena`
   - `teach -> how, why`
   - `figure-it-out -> poteto-mode, show-me-your-work, architect`
   Optional/reference edge: `principle-prove-it-works -> show-me-your-work`.
4. Frontmatter must accept only the observed baseline-compatible string forms:
   52 exact stable names plus explicit legacy display name `Poteto Mode`; and
   nonempty double-quoted, plain, or folded `>-` descriptions. Reject empty,
   comment-only, null, boolean, collection, control-containing, ambiguous, and
   all-caps alias values.
5. Adapter discovery must use the held repository descriptor and reject
   symlinked or swapped adapter declaration directories. A symlinked
   `adapters/example` previously admitted an external declaration.

The Task 4 closure commit is:

```text
c53ae8752a0c8b3ca533b94cb38d2792bacb5b44
fix: close skill validation and dependency gaps
```

Closure evidence recorded by the implementer:

- Grouped five-class closure suite: 5/5
- Complete focused skill suite: 23/23
- Full repository suite: 107/107
- Claude accounting: 53 bundled, 12 plugin-managed, 0 unsupported
- Codex dependency-closed accounting: 36 bundled, 11 plugin-managed,
  18 unsupported
- Frontmatter corpus: 52 exact stable names plus explicit `Poteto Mode`;
  descriptions 39 double-quoted, 12 nonempty plain, 2 folded `>-`
- Semantic parity: no errors for Claude or Codex
- Pstack: frozen and clean at `63d938c`
- Python/JSON/shell/diff checks: clean
- Protected native hashes/types unchanged; adapter `current` links absent

Task 4 implementation is complete. An independent closure review of the exact
range below is still required before Task 5 consumes this layer.

## Required Task 4 closure review

Review the range `07cd989..c53ae8752a0c8b3ca533b94cb38d2792bacb5b44`
read-only. At minimum replay:

```bash
cd /Users/mac/Desktop/Work/kingstack
PYTHONPATH=lib python3 -m unittest tests.test_skills -v
PYTHONPATH=lib python3 -m unittest discover -s tests -v
./scripts/kingstack sync-upstream pstack --check
./scripts/kingstack sync-upstream pstack --adapter claude --bundle-manifest
./scripts/kingstack sync-upstream pstack --adapter codex --bundle-manifest
./scripts/kingstack render --adapter claude --manifest
./scripts/kingstack render --adapter codex --manifest
git diff 07cd989..c53ae8752a0c8b3ca533b94cb38d2792bacb5b44 --check
git status --short --branch
```

Also independently fault every descriptor acquisition/validation exit, replay
the paragraph-as-path transform exploit, validate the baseline frontmatter
corpus plus invalid scalar corpus, verify dependency-closed Codex accounting,
and replay symlinked/swapped adapter discovery. Do not edit during review.

## Remaining migration after Task 4

1. Portable lifecycle hooks plus rendered-bundle syntax validation.
2. Rendered Claude behavioral parity proof.
3. Shared curated memory and inbox across Claude and Codex while native memory
   remains separate.
4. Complete Codex adapter and behavioral parity.
5. Immutable releases, health, activation, rollback, fault injection, and
   schedule migration.
6. Rewrite/classify authored Markdown; add `VERSION`, `CHANGELOG.md`, and
   `docs/ROADMAP.md` with enforced maintenance rules.
7. Build and verify final Claude and Codex releases.
8. Mandatory pre-link briefing and explicit Hassan approval.
9. Live activation, rollback proof, reactivation, cross-agent behavior proof,
   final no-loss audit, safe Superpowers disablement, six-plan deletion, final
   release review, tag, and push.

## Current safety state

- `~/.claude`, `~/.codex`, and `~/.kingstack` are real directories.
- No adapter `current` symlink exists.
- No activation, rollback, schedule migration, or Superpowers disablement has
  occurred.
- The six requested plan files still exist.
- All historical snapshots and archives remain preservation-only and untouched.
- The feature branch is unfinished by design.
