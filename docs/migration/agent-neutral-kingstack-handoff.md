# Agent-neutral kingstack: architecture, migration status, and handoff

Status date: 2026-08-21

Repository: `https://github.com/hassanGH-GG/kingstack`

Branch: `feat/agent-neutral-kingstack`

Implementation status: Phases A–E plus Cursor adapter implemented and committed; Phase F briefing written; Phase G live cutover not started
Live status: not activated; Claude, Codex, and Cursor native homes remain unchanged

This is the canonical continuation document for a new Claude or Codex session.
It explains what kingstack was, why the architecture changed, what has been
implemented and proven, what remains, and the exact gates that protect user
data. A continuing agent should read this document before the detailed plans or
task reports. Do not rely on the conversation that produced the branch.

## Executive summary

Kingstack began as a powerful Claude-specific setup whose source code and live
runtime were both `~/.claude`. It accumulated global guidance, hooks, skills,
pstack adaptations, memory capture, schedules, health checks, model routing,
and usage monitoring. That setup worked, but it had three structural limits:

1. The source of truth was also the live installation. Editing source changed
   future Claude sessions immediately, and sync scripts wrote directly into
   live skill directories.
2. Policy was expressed in Claude-specific concepts. Codex could not consume
   the same operating system without copying and gradually diverging from it.
3. There was no release boundary. Rendering, installation, activation, health,
   rollback, and preservation were not separate transactions with explicit
   ownership.

The migration replaces that shape with an agent-neutral shared core and small
native adapters. The repository renders immutable bundles in memory; a later
release builder will materialize content-addressed releases under private
runtime state. Native homes remain native. Only exact manifest-owned files will
eventually be linked or merged, after no-loss and rollback proofs and an
explicit user approval.

The first four core tasks are implemented:

- formal adapter and capability contracts;
- pure immutable instruction bundles;
- portable model/effort routing;
- a single-source, pstack-safe skill catalog with honest Claude/Codex
  capability accounting.

Nothing has been activated. Shared memory, the Codex bundle, the Cursor
adapter, and the release builder exist on this branch. Live cutover remains
blocked on `docs/migration/pre-link-briefing.md`.

## Start here when continuing

```bash
git clone https://github.com/hassanGH-GG/kingstack.git
cd kingstack
git switch feat/agent-neutral-kingstack
git status --short --branch
```

On the original machine the canonical checkout is:

```text
/Users/mac/Desktop/Work/kingstack
```

Task 4 closure review returned `APPROVE` on 2026-08-21. Phases A–E plus the
Cursor adapter are implemented on this branch. Live cutover is still stopped
on the pre-link briefing. Do not activate a native home.

## Why this architecture exists

The objective is not merely “make Claude configuration work in Codex.” The
objective is to make the user’s operating system for agents portable,
versioned, observable, recoverable, and extensible without erasing the useful
native behavior of any agent.

The key design choices are:

- **Shared intent, native execution.** Principles, routing classes, skill
  ownership, memory policy, and lifecycle intent belong to the neutral core.
  Claude and Codex adapters translate those intents into native surfaces.
- **Source is not installation.** Git-tracked source lives in the canonical
  checkout. Private manifests, availability, release state, and rollback
  records live under `~/.kingstack`. Native homes remain agent-owned.
- **Pure rendering before mutation.** Providers return immutable, ordered
  `relative path -> bytes` bundles. Render commands cannot write a staging or
  native directory.
- **Granular ownership.** An adapter owns exact generated paths, not a mixed
  directory such as all of `skills/`. Package-managed content stays outside
  kingstack ownership.
- **Capabilities are explicit.** Unsupported or degraded behavior is visible
  in a capability matrix and bundle manifest. The system must never claim
  parity merely because a native harness exposes a similarly named mechanism.
- **No-loss precedes convenience.** Activation, rollback, and cleanup are held
  until preservation has been demonstrated with hashes, manifests, fault
  injection, and a user-visible pre-link briefing.
- **Future agents use the same extension point.** A synthetic third adapter
  must work through declarations and providers without editing Claude/Codex
  branches into the core.

## Before, current, and target architecture

| Concern | Before migration | Current branch | Final target |
|---|---|---|---|
| Canonical source | Git repository physically inside live `~/.claude` | Dedicated checkout at `~/Desktop/Work/kingstack` | Same dedicated checkout, versioned and released |
| Claude home | Source and live runtime were interleaved | Original real directory, read-only during migration | Real native directory with only exact managed paths linked/merged |
| Codex home | Separate setup with no kingstack parity | Original real directory, inventoried and unchanged | Real native directory with its own adapter-managed paths |
| Shared policy | Claude-specific `CLAUDE.md`, model names, commands, and paths | Neutral instruction fragments plus adapter appendices | Same neutral core used by every adapter |
| Rendering | Live files and later a rejected mutable staging design | Pure immutable in-memory bundles | Bundle bytes materialized only into immutable releases |
| Skills | Legacy sync copied, transformed, pruned, and replaced live directories | 65-name ownership catalog; pstack source frozen; pure manifests | Release-owned portable skills plus explicit package-managed/unsupported accounting |
| Model routing | Haiku/Sonnet/Opus/Fable names embedded in shared prose | Mechanical/precise/judgment work classes mapped by adapter | Private availability chooses concrete models without changing shared policy |
| Memory | Claude project memory and inbox local to Claude workflows | Preserved and inventoried; not migrated | Curated shared memory plus separate native/private memory |
| Hooks | Claude shell hooks directly tied to Claude payloads | Portable handlers plus Claude normalizer rendered into the bundle; not activated | Same handlers plus Codex/Cursor normalizers after those adapters |
| Schedules | Claude/launchd jobs tied to current scripts | Preserved and unchanged | Adapter-aware scheduled tasks with equivalent cadence and evidence |
| Installation | Scripts could mutate live paths directly | No installation or activation exists | Immutable release, atomic exact-path activation, inverse rollback |
| Recovery | Git plus custom snapshots and manual knowledge | Git clone, frozen baseline, private manifest; historical archives preserved | Manifest-owned rollback with fault-injection proof; old archives non-production |
| New agents | Would require copying Claude conventions | Contract/provider extension proven synthetically | Add declaration, provider, transforms, capability evidence; no core fork |

## Architecture map

```text
                     Git-tracked canonical source
                 ~/Desktop/Work/kingstack
                              |
         +--------------------+--------------------+
         |                    |                    |
   shared core          adapter declarations    verification
 instructions           providers/models        tests/parity
 routing                native transforms       capability reports
 skills catalog         capability matrices     no-loss evidence
 hooks (planned)
 memory (planned)
         |
         | pure render: immutable {relative path -> bytes}
         v
              private kingstack runtime (planned)
      ~/.kingstack/adapters/<adapter>/releases/<content-hash>
                              |
          explicit activation + manifest + rollback only
                 after proof and user approval
                     /                     \
                    v                       v
            ~/.claude (real dir)     ~/.codex (real dir)
            Claude-native state      Codex-native state
            auth/sessions/cache      auth/sessions/cache
            remain agent-owned       remain agent-owned
```

The arrows stop before the native homes today. The release and activation
layers in the middle are still planned, not implemented.

## Preservation boundary

The migration treats preservation as an architectural boundary, not a cleanup
step.

### Always native and private

- authentication and account state;
- session transcripts and caches;
- agent-private memory;
- device-specific settings;
- private availability overrides;
- scheduler runtime state;
- historical snapshots and archives.

### Eligible for shared, versioned source

- operating principles and global guidance;
- portable work classes and effort policy;
- authored skills and upstream ownership metadata;
- portable lifecycle logic;
- curated memories approved for cross-agent use;
- adapter declarations, transforms, and capability evidence;
- health, release, activation, and rollback code.

### Activation rule

Kingstack may eventually own only exact manifest-listed native paths. Mixed
directories and unrelated keys remain native. A whole native home must never be
replaced by a symlink.

## Baseline and no-loss foundation

The foundation froze the existing machine before portable implementation.

- Foundation acceptance commit: `639fc04`
- Public baseline SHA-256:
  `8d943deaa440a279452e3af79400c6651722306936d2d90922692810722ddf27`
- Claude inventory: 587 entries
- Codex inventory: 434 entries
- Memory banks: 14
- Historical top-level snapshot/archive roots preserved: 10
- Native `~/.claude` and `~/.codex`: real directories, not symlinks
- Bootstrap private manifest mode: `0600`
- Private runtime/bootstrap directories: `0700`

The bootstrap created a true no-hardlink clone of reviewed source and a
redacted inventory. It did not activate adapters or modify protected live
files. Two pre-existing Claude health drifts were documented rather than
silently repaired: a stray `~/.claude/.claude.json` and the legacy live repo
being ahead of its old remote state.

Detailed evidence: `docs/migration/foundation-verification.md`.

## Completed implementation

### Core Task 1: adapter contract and capability matrices

Purpose: make “an agent adapter” a validated interface rather than an informal
folder convention.

Implemented:

- exact seven-field declarations: `id`, `contract_version`, `render_module`,
  `native_home`, `owned_paths`, `model_tiers`, `capability_matrix`;
- stable capability catalog covering guidance, skills, lifecycle events,
  routing, memory, schedules, health, activation, and rollback;
- explicit `native`, `emulated`, `degraded`, or `unsupported` status with
  evidence and strict-parity impact;
- Claude, Codex, and synthetic third-adapter declarations;
- portable path validation across POSIX, Windows aliases, Unicode NFC,
  case-fold collisions, controls, and reserved devices;
- safe selector handling and schema/runtime agreement.

Commits:

- `8896079` — initial contract
- `0f2da20` — contract validation hardening
- `27b92da` — portable semantics and honest Codex matrix
- `fa7a2fc` — Unicode ownership canonicalization

Review result: `APPROVE`, no findings. Final evidence at approval: focused
27/27, full 58/58.

### Core Task 2: pure immutable instruction bundles

Purpose: separate deterministic rendering from filesystem publication.

The first implementation introduced mutable `.staging/<adapter>` output. Its
review exposed repeated namespace and cleanup races. Instead of continuing to
patch publication, the architecture removed publication from the renderer
entirely.

Implemented:

- exact guidance split at existing heading boundaries;
- provider dispatch through the adapter declaration;
- immutable sorted mappings of portable relative paths to bytes;
- read-only CLI selectors: manifest, print one file, compare one file;
- descriptor-confined, no-follow source reads;
- shared portable output-path validation;
- synthetic provider producing `GUIDANCE.md` without first-party core changes;
- categorical removal of `write_staged_instructions`, render `--output`, and
  production `.staging` references.

Commits:

- `f363592` — initial extracted instruction core
- `5ca29bb` — hardening of the retired staging design
- `bf906ff` — architectural rewrite to pure bundles
- `be12312` — immutable provider bundles
- `8ad1306` — portable rendered-path enforcement

Review result: `APPROVE`, no findings. Pre-routing Claude guidance remained
exactly 9,525 bytes with SHA-256
`7a6f34e0ff3777279053bb63713dfc109761d508f18fef0316279e9a74fdab2e`.

### Core Task 3: portable model and effort routing

Purpose: express work requirements independently of a vendor’s model names.

Implemented shared work classes:

| Work class | Portable tier | Effort |
|---|---|---|
| `waiting` | none | none |
| `mechanical` | economical | low |
| `precise` | balanced | medium |
| `judgment` | frontier | high |

Adapter maps select native models. Availability overrides are injected private
records; a model availability problem moves exactly one adjacent tier for that
spawn and never causes a blanket global override.

Implemented:

- immutable, explainable routing decisions;
- adapter-owned model maps;
- deterministic adjacent fallback;
- explicit model and effort reporting;
- stable `RoutingError` boundaries for malformed input;
- vendor-neutral shared prose and adapter-specific appendices;
- cross-vendor model-name leakage checks.

Commits:

- `8ce2975` — portable routing
- `a4f4dc9` — stable validation boundaries
- `9d5e48b` — validation at every mapping boundary

Review result: `APPROVE`, no findings. Final evidence: focused 53/53, full
84/84, all 49 malformed mapping-key combinations safely rejected.

### Core Task 4: single-source skills and pstack safety

Purpose: preserve the complete skill surface without letting upstream sync,
adapter transforms, or later activation overwrite content they do not own.

Frozen Claude baseline:

- 65 total skill names;
- 43 pstack-owned;
- 8 adopted dependencies/extras;
- 2 kingstack-authored (`king-mode`, `memory-review`);
- 12 plugin-manager-owned.

Implemented:

- authoritative immutable skill catalog;
- authored skill sources under `core/skills/authored/`;
- frozen pstack revision `63d938c`;
- pure adapter-aware skill manifests;
- plugin-managed accounting without bundling package-managed files;
- descriptor-confined source and adapter discovery;
- strict, baseline-compatible frontmatter validation;
- typed transforms with token-shape constraints;
- independent semantic parity over headings, instruction paragraphs,
  frontmatter, resource sets, and script bytes;
- exact-tree clobber detection, including missing/extra/deleted/edited files and
  symlink or identity-swap rejection;
- dependency-closed unsupported accounting for Codex;
- granular adapter ownership instead of owning the mixed `skills/` directory;
- a pure compatibility wrapper replacing the legacy live-mutating pstack sync.

The legacy script previously pulled upstream, removed and copied live skill
directories, rewrote files in place, pruned deleted skills, and wrote live
manifests. The new wrapper only invokes read-only source checks and bundle
manifest generation. Immutable release materialization remains a later phase.

Commits:

- `190587c` — single-source skill/pstack implementation
- `07cd989` — source, parity, clobber, ownership, and direct Codex accounting
- `c53ae87` — descriptor cleanup, transform token constraints, dependency
  closure, strict frontmatter, and confined adapter discovery

Final implementer evidence:

- grouped five-class closure suite: 5/5;
- complete skill suite: 23/23;
- full repository suite: 107/107;
- Claude: 53 bundled, 12 plugin-managed, 0 unsupported;
- Codex: 36 bundled, 11 plugin-managed, 18 unsupported;
- semantic parity: no errors;
- pstack: clean at `63d938c`;
- Python, JSON, shell, and diff checks: clean;
- protected live hashes/types unchanged; adapter `current` links absent.

Task 4 implementation is complete. Independent closure review remains pending.

## Important architectural corrections made during implementation

The commit history deliberately preserves corrections rather than hiding them.
The most important lessons are:

1. **Mutable staging was the wrong abstraction.** Repeated filesystem races
   were not a reason to add more checks; they were evidence that rendering
   should not publish at all. Pure bundles removed the whole race class.
2. **Path validation is a security boundary.** Lexical “relative path” checks
   were insufficient across Unicode-normalizing filesystems and Windows path
   aliases. The contract now has one shared portable canonicalizer.
3. **A passing semantic check can be tautological.** Transform output cannot be
   verified by computing an expected result with the same unrestricted
   transform. Parity must compare independent invariants.
4. **Ownership must match the unit of preservation.** Claiming all of `skills/`
   would conflict with plugin-managed children. The adapter now owns only
   generated skill paths.
5. **Unsupported must propagate.** A Codex skill is not usable if its required
   child skill is unsupported, even when its own bytes contain no foreign
   token. Capability accounting is dependency-closed.
6. **Publication has a linearization point.** Foundation bootstrap work proved
   that a durable manifest must be the final success commit point; errors after
   publication cannot retroactively turn committed success into reported
   failure.
7. **No-loss evidence must be independent.** Hashes, exact inventories,
   descriptor identities, fault injection, and rollback proofs are stronger
   than a health command asserting its own correctness.

## Repository and evidence map

| Path | Purpose |
|---|---|
| `docs/migration/agent-neutral-kingstack-handoff.md` | This continuation document |
| `docs/migration/foundation-verification.md` | Frozen foundation and no-loss evidence |
| `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md` | Approved target architecture |
| `docs/superpowers/plans/2026-08-20-kingstack-*-plan.md` | Phase implementation plans; temporary until final requested deletion |
| `.superpowers/sdd/2026-08-20-kingstack-core-claude-plan/progress.md` | Durable execution ledger and rulings |
| `.superpowers/sdd/2026-08-20-kingstack-core-claude-plan/task-*-brief.md` | Exact implementer contracts |
| `.superpowers/sdd/2026-08-20-kingstack-core-claude-plan/task-*-report.md` | Append-only RED/GREEN/review evidence |
| `adapters/contract/` | Declaration and capability schemas |
| `adapters/{claude,codex}/` | Native declarations, models, appendices, transforms |
| `core/instructions/` | Ordered vendor-neutral guidance |
| `core/routing/` | Portable work policy |
| `core/skills/` | Skill ownership, authored sources, transforms |
| `lib/kingstack/` | Contract, rendering, routing, skills, CLI implementation |
| `tests/` | Foundation, adversarial, parity, and regression tests |

## Task 4 closure review

Review must be read-only and use the exact range:

```text
07cd9895ffaf02bdeaf876095127e3ed148b60a5
..
c53ae8752a0c8b3ca533b94cb38d2792bacb5b44
```

Nominal commands:

```bash
cd /Users/mac/Desktop/Work/kingstack
git switch feat/agent-neutral-kingstack
git pull --ff-only
PYTHONPATH=lib python3 -m unittest tests.test_skills -v
PYTHONPATH=lib python3 -m unittest discover -s tests -v
./scripts/kingstack sync-upstream pstack --check
./scripts/kingstack sync-upstream pstack --adapter claude --bundle-manifest
./scripts/kingstack sync-upstream pstack --adapter codex --bundle-manifest
./scripts/kingstack render --adapter claude --manifest
./scripts/kingstack render --adapter codex --manifest
git diff 07cd989..c53ae87 --check
git status --short --branch
```

Adversarial review must independently replay:

- every descriptor-acquisition and early-validation failure with an FD count;
- the full instruction-paragraph disguised as a `path`, `model`, `tool`, or
  `host` transform;
- accepted baseline frontmatter plus empty, comment-only, null, boolean,
  collection, control-containing, ambiguous, and all-caps-alias rejection;
- dependency-closed Codex unsupported accounting;
- symlinked and deterministically swapped adapter declarations;
- previous source-tree symlink/swap and exact clobber-tree cases;
- absence of mutable staging, native writes, activation, and current links.

Return `APPROVE` or `REJECT` with reproducible findings. Do not fix findings in
the review turn. Task 5 must not consume Task 4 until this review approves.

## Remaining work

### Phase A: portable lifecycle hooks and Claude parity

Implemented on this branch; independent Phase A review is still required
before Phase B.

Neutral handlers cover:

- session start;
- stop/candidate capture;
- pre-compaction checkpoint and preservation directive;
- post-tool-use bulk-context observation;
- subagent-start model, effort, role, and task visibility.

Claude’s normalizer should reproduce existing behavior from captured fixtures.
Bundle syntax tests must compile shell/Python bytes and parse JSON/TOML/skill
frontmatter without materializing the bundle. Then prove rendered Claude
behavior against the frozen capability baseline.

Review cadence: implement lifecycle hooks and Claude parity together, then one
independent phase review.

### Phase B: shared curated memory and inbox

Build the three-class memory design:

1. shared curated memory approved for cross-agent use;
2. native agent memory that remains private to Claude or Codex;
3. private runtime candidates/inbox awaiting review.

Required properties include deterministic project identity, deduplication,
promotion provenance, safe concurrent capture, migration without deleting any
native memory, and cross-agent recall tests.

Review cadence: one independent memory-phase review.

### Phase C: complete Codex adapter

Implement and prove:

- `AGENTS.md` guidance;
- Codex-compatible portable skills;
- configuration patch declarations without copying secrets;
- lifecycle integration or explicit documented fallbacks;
- routing defaults and explicit subagent effort visibility;
- shared memory access;
- scheduled-task equivalents;
- honest capability gaps where strict parity is impossible.

Review cadence: one independent review of the complete adapter, not one review
per small file.

### Phase D: releases, activation, rollback, and health

Build immutable releases at:

```text
~/.kingstack/adapters/<adapter>/releases/<content-hash>
```

Each release must bind source commit, adapter declaration, provider inputs,
resolved private inputs, file hashes, modes, capabilities, and ownership.

Activation must:

- preserve an existing native path through exact atomic rename;
- publish only manifest-owned paths;
- merge mixed JSON/TOML ownership without discarding unrelated keys;
- record enough state for inverse rollback;
- fail safely under injected crashes and namespace swaps;
- never replace a native home.

Rollback must preserve unrelated changes made after activation. Health must
validate source, release, active native state, memory, schedules, and ownership
without treating its own claims as proof.

This phase requires an independent safety review before any live link.

### Phase E: schedules, documentation, versioning, and release preparation

- migrate existing schedules without duplicate execution;
- add SemVer `VERSION`;
- add and maintain `CHANGELOG.md`;
- replace/rewrite the backlog as `docs/ROADMAP.md`;
- rewrite/classify README and authored Markdown for the neutral architecture;
- add a rule/test requiring version, changelog, and roadmap maintenance;
- build final Claude and Codex releases in private runtime;
- prove both releases without activation.

### Phase F: mandatory pre-link briefing

Stop before the first live link and give Hassan:

- exact clone/history/origin proof;
- complete baseline and no-loss comparison;
- memory/inbox and pstack preservation hashes;
- release IDs and manifests;
- every native path that will change;
- every original path and dated preservation sibling;
- link/merge targets and ownership projections;
- rollback commands and fault-injection evidence;
- capability gaps and residual risks.

Do nothing live until Hassan explicitly approves this briefing.

### Phase G: controlled cutover and final cleanup

After approval:

1. activate Claude;
2. prove behavior in a fresh Claude session;
3. rollback and verify byte/projection restoration;
4. reactivate Claude;
5. activate and prove Codex;
6. prove shared memory and schedules across both;
7. run final no-loss audit;
8. disable Superpowers by exact reversible version-directory relocation only
   after replacement parity;
9. delete the six specifically requested plan files from canonical and legacy
   locations;
10. review exact commits, release notes, tag, and remote state;
11. push/merge only with the user’s final authorization.

### Phase H: Cursor Agent adapter

Add a first-party Cursor Agent adapter after Claude and Codex cutover, using
the same contract and provider extension already proven by the synthetic
third adapter. Do not fork core for Cursor-specific branches.

At that time, inventory Cursor’s native surfaces (rules, skills, hooks,
guidance files, and any agent-home config) and declare an honest capability
matrix. Render an immutable Cursor bundle, then prove it the same way Claude
and Codex are proved: no-loss, exact-path ownership, and no activation until
Hassan approves a pre-link briefing.

This phase is requested and deferred. It is not part of Phase A.

## Files that must be deleted only at final completion

Delete these only after their work is complete and replacement documentation
is committed:

1. `docs/superpowers/plans/2026-08-20-agent-neutral-kingstack-migration.md`
2. `docs/superpowers/plans/2026-08-20-kingstack-foundation-plan.md`
3. `docs/superpowers/plans/2026-08-20-kingstack-core-claude-plan.md`
4. `docs/superpowers/plans/2026-08-20-kingstack-shared-memory-plan.md`
5. `docs/superpowers/plans/2026-08-20-kingstack-codex-adapter-plan.md`
6. `docs/superpowers/plans/2026-08-20-kingstack-cutover-plan.md`

The same exact six legacy paths under `/Users/mac/.claude/docs/superpowers/plans/`
must then be removed explicitly. Do not broaden the deletion target.

## Superpowers disablement rule

Superpowers is currently cache-only and remains enabled. Final disablement is
not “delete whatever matches superpowers.” Recheck installation state at that
time. If it remains cache-only, atomically relocate each exact version
directory to:

```text
~/.kingstack/disabled/superpowers/<version>-<hash>
```

Then prove a fresh session exposes no `superpowers:*` skills. Restore by reverse
rename if proof fails. If Superpowers is installed differently at cutover,
stop and replan rather than applying the cache-only procedure blindly.

## Review and execution policy going forward

The early work used frequent implement/review/fix/re-review loops. That caught
real defects, but it also consumed excessive quota and encouraged local fixes.
The approved cadence is now:

- one closure review for lifecycle hooks plus Claude parity;
- one review for shared memory;
- one review for the complete Codex adapter;
- one mandatory activation/rollback review before live mutation;
- one final end-to-end review.

Use balanced/medium effort for ordinary implementation. Reserve frontier/high
effort for filesystem confinement, data loss, activation/rollback, and final
review. A review should exhaust a defect class before returning findings so one
fix cycle can close it categorically.

## Current safety state

At the Task 4 implementation head:

- `~/.claude`, `~/.codex`, and `~/.kingstack` are real directories;
- no adapter `current` symlink exists;
- no bundle has been installed or activated;
- no native configuration, memory, session, skill, schedule, or auth state was
  intentionally changed by the migration;
- Superpowers remains enabled;
- the six plan files remain present;
- historical snapshots and archives remain untouched and are not production
  dependencies;
- the feature branch is public and intentionally unfinished;
- `main` is untouched.

## Final acceptance criteria

The migration is complete only when all of the following are true:

- Claude’s existing behavior is preserved or every difference is explicitly
  approved;
- Codex receives the portable capabilities it can support, with honest gaps;
- shared memory works without deleting or conflating native memory;
- no native auth/session/cache/private state is tracked or overwritten;
- releases are immutable and reproducible;
- activation and rollback survive injected crashes and path swaps;
- unrelated native changes survive rollback;
- schedules run once at the intended cadence;
- health detects drift independently;
- README, version, changelog, and roadmap describe the final system;
- Superpowers is disabled reversibly after replacement parity;
- the six temporary plans are deleted exactly as requested;
- final source, tag, remote, and no-loss evidence are reviewed;
- Hassan explicitly approves the live cutover and final publication.

Until then, treat `feat/agent-neutral-kingstack` as a reviewed work-in-progress,
not a deployable release.
