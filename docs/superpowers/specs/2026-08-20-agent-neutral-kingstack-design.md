# Agent-neutral kingstack design

Date: 2026-08-20
Status: Approved revised architecture
Owner: Hassan Ghandour

## Summary

Kingstack will become Hassan's agent-neutral control plane. Its canonical Git
checkout will move from `~/.claude` to `~/Desktop/Work/kingstack`. Agent
harnesses consume native, versioned adapters generated from one shared source;
no agent's home directory, syntax, model catalog, or memory format defines the
core.

The migration is an expansion, not a replacement:

```text
Before: kingstack -> Claude Code

After:                 kingstack core
                  ┌──────────┼──────────┐
                  v          v          v
                Claude     Codex      future agent
                adapter    adapter    adapter
```

Claude and Codex are the first consumers, not architectural owners. Future
local, cloud, editor, CLI, or chat agents join by implementing the adapter
contract and capability tests. No live profile is deleted or overwritten during
migration. Claude Code remains operational until the initial adapters pass
parity tests, and every original kingstack-owned path stays available as a dated
rollback backup until Hassan explicitly approves its removal.

## Goals

1. Preserve every capability already implemented in kingstack.
2. Give Claude Code and Codex equivalent behavior through their native surfaces.
3. Keep one source of truth for shared policies, skills, memory, and operational
   tooling.
4. Keep agent-specific authentication, sessions, transcripts, caches, automatic
   memories, and account usage separate.
5. Make installation, verification, drift detection, and rollback mechanical.
6. Keep pstack absorbed whole, credited, upstream-syncable, and isolated from
   personal customization.
7. Let future agents gain an adapter by satisfying a stable contract, without
   restructuring or copying the core.
8. Treat kingstack as a maintained product with semantic versions, a factual
   changelog, and one durable roadmap.

## Non-goals

- Making any two agent harnesses use identical file formats or internal state.
- Merging authentication, subscriptions, raw transcripts, caches, or databases.
- Publishing personal memories or runtime ledgers in the public repository.
- Rewriting pstack as a kingstack-owned framework.
- Removing any existing setup during the first migration.
- Claiming parity when a harness lacks a capability; gaps remain explicit.
- Building a general in-place, file-by-file home-directory restore engine.
- Depending on Codex's Claude import as the permanent synchronization layer.

## Migration baseline

The live Claude installation was inventoried before design approval:

| Capability | Baseline |
|---|---:|
| Skills | 65 |
| Pstack agents | 2 |
| Hook files | 8 |
| Registered lifecycle events | 5 |
| Helper scripts | 16 |
| Launchd schedules | 3 |
| Sweep definitions | 4 |
| Project memory banks | 7 |
| Reviewed memory-inbox entries | 28 |
| Pending memory-inbox entries | 0 |
| Memory tests | 9 passing |
| Pstack upstream revision | `63d938c` |

The existing health check reported `SETUP HEALTHY`. Implementation must capture
file hashes, symlink targets, permissions, schedule definitions, Git state, and
the full skill/agent name lists before changing a live path. The generated
baseline manifest becomes the migration parity contract.

## Canonical repository and private state

### Tracked source

The canonical repository will live at:

```text
~/Desktop/Work/kingstack/
├── core/
│   ├── identity/
│   ├── policies/
│   ├── skills/
│   ├── memory/
│   └── schedules/
├── adapters/
│   ├── contract/
│   ├── claude/
│   ├── codex/
│   └── templates/
├── scripts/
│   ├── migrate
│   ├── install
│   ├── verify
│   ├── rollback
│   └── sync-upstream
├── docs/
└── tests/
```

The repository remains public only for authored framework content. Its
allowlist `.gitignore` must exclude generated adapters, secrets, raw transcripts,
native databases, memory content, checkpoints, ledgers, logs, backups, and
authentication.

### Private runtime state

Shared private state will live outside the public repository:

```text
~/.kingstack/
├── adapters/
│   ├── claude/releases/
│   ├── codex/releases/
│   └── manifests/
├── backups/
├── checkpoints/
├── ledgers/
├── manifests/
├── memory/
└── logs/
```

`~/.kingstack` is never a symlink to either agent home and is never tracked by
the public repository. Permissions default to user-only. Auth tokens and agent
credentials never enter it.

Generated adapter releases are private runtime artifacts, not tracked source.
Each release is immutable and named by its source hash. A per-agent `current`
link selects the active verified release; publishing a new release changes that
single link only after generation and validation finish.

### Snapshot boundary

Snapshot capture is deliberately smaller than adapter rollback. It records a
read-only inventory and private archive of the authored configuration selected
by an allowlist. Capture compares source identity and content before and after;
if the source changed, the attempt is rejected and retried rather than declared
lossless. A completed archive is verified, permission-checked, and then
published immutably.

There is no production snapshot `apply` operation. The experimental
file-by-file restore transaction built during foundation is removed before
foundation acceptance because independent review found irreducible late-rename
windows and unbounded descriptor retention. Existing verified snapshot
directories remain preserved as evidence and additional recovery inputs, but
they are not the sole rollback mechanism.

Normal rollback uses the dated originals of manifest-owned paths. Disaster
recovery materializes an archive beside, never into, a live agent home and
requires a separate verification and human-approved whole-directory decision.

## Shared core

The core contains portable meaning, not harness syntax.

### Adapter contract and capability matrix

Every adapter implements the same conceptual interface:

- render global guidance from ordered core fragments
- register portable and package-managed skills
- map portable model tiers and effort levels to native controls
- expose supported lifecycle events and documented fallbacks
- inject approved shared-memory indexes and emit inbox candidates
- declare schedule execution surfaces and idempotency behavior
- inventory owned paths without claiming native runtime state
- stage, validate, activate, inspect, and roll back a versioned release
- report supported, emulated, degraded, and unsupported capabilities

The contract is behavioral rather than file-shaped. It does not require
`CLAUDE.md`, `AGENTS.md`, a particular hook name, or a particular model family.
Portable policy uses capability classes such as `frontier` and lifecycle intents
such as `before-compaction`; adapters translate those into native mechanisms.

Every adapter emits a machine-readable capability matrix. Unsupported native
features remain visible and block strict parity where required. An adapter may
use a wrapper, local scheduler, or checkpoint process as a declared fallback,
but it may not silently omit behavior or describe emulation as native support.

The minimum adapter test contract covers deterministic rendering, schema and
syntax validation, capability reporting, ownership boundaries, staged
activation, shared-memory round trips, model/effort mapping, health reporting,
and rollback. This is the extension point for Cursor, Gemini CLI, Slack-hosted
agents, cloud agents, and future harnesses.

### Identity and operating policy

The present `CLAUDE.md` will be decomposed by concern:

- identity and team context
- standing correction rule
- operating principles
- design grounding
- engineering and Git discipline
- approval boundaries
- communication preferences
- cost and model-routing policy
- documentation and stack-iteration policy

Claude's `CLAUDE.md` and Codex's `AGENTS.md` will be generated from the same
ordered source fragments plus a small adapter-specific appendix. A shared rule
must never be maintained independently in both generated files.

### Skills

Portable `SKILL.md` sources live once under `core/skills`. Adapter generation
may translate frontmatter, model names, tool names, or paths, but must not change
workflow meaning.

The shared set includes:

- pstack's complete supported skill set
- `king-mode`
- `memory-review`
- adopted Cursor skills and review rubrics
- kingstack-authored workflow skills

Plugin-managed skills such as Cloudflare remain owned by their package managers
unless kingstack adds a portable wrapper. The parity manifest records them so a
missing dependency is detected rather than silently ignored.

Pstack remains upstream-owned. `sync-upstream` records the upstream revision,
applies deterministic per-adapter transformations, protects hand-edited output,
and fails if untranslated host-specific content remains. Kingstack-specific
behavior belongs in core policies or king-mode, not in generated pstack output.

### Model and effort routing

The core routing policy uses capability classes rather than vendor model names:

| Work class | Portable tier | Default effort |
|---|---|---|
| Waiting/polling | no model | none |
| Mechanical extraction | economical | low |
| Precise execution | balanced | medium |
| Judgment/review | frontier | high |
| Escalation after evidence | next capable tier | explicit |

Adapters map tiers to models available in their harness. Initial mappings are:

- Claude: Haiku, Sonnet, Opus/Fable according to availability.
- Codex: Luna, Terra, Sol according to availability.

Every subagent spawn sets model and effort explicitly. Native default-subagent
settings act as a backstop. A lifecycle hook reports actual model, effort, role,
and task to the parent. Unavailable models fall back one adjacent tier for that
spawn; they do not trigger blanket overrides.

## Native adapters

Claude and Codex are the initial first-party adapters. This section records
their native surfaces without granting either one ownership of shared policy.

### Claude Code adapter

The Claude adapter preserves all current behavior:

- generated global `CLAUDE.md`
- `settings.json` fragments and five lifecycle event registrations
- SessionStart routing contract
- Stop memory capture
- PreCompact preservation and checkpointing
- PostToolUse bulk-context warning
- SubagentStart model/effort visibility
- pstack and king-mode activation
- 200k compaction ceiling
- helper scripts, sweeps, and launchd jobs
- existing two-profile sharing between work and personal accounts

Paths may remain compatible wrappers under `~/.claude` so existing launchd jobs,
aliases, and commands continue working while their implementation moves to the
neutral checkout.

### Codex adapter

The Codex adapter uses Codex-native surfaces:

- global `~/.codex/AGENTS.md`
- user-level `~/.codex/config.toml`
- native Codex hooks for SessionStart, Stop, PreCompact, PostToolUse, and
  SubagentStart
- native skills or a local kingstack plugin
- Codex subagent defaults and explicit spawn overrides
- Codex memories enabled for private native learning
- shared curated-memory injection
- Codex Scheduled tasks when they are superior to launchd
- launchd/shared scripts when local files or machine continuity are required

The existing Codex model choice remains user-controlled. The adapter changes the
default reasoning effort from high to medium only after a parity test confirms
the resulting configuration. Current Codex plugins, MCP servers, trusted
projects, notifications, and authentication are merged, never replaced.

Codex's official Claude import is used once as a discovery and comparison tool.
Its detected instructions, settings, skills, memories, hooks, subagents, MCP
configuration, and recent chats are compared against kingstack's generated
adapter. Import output is not the canonical source.

## Memory architecture

### Three memory classes

1. **Shared curated memory**: approved project facts, corrections, decisions,
   and durable preferences in `~/.kingstack/memory`.
2. **Claude-native memory**: Claude's raw transcripts, automatic state, and
   profile-specific data under `~/.claude`.
3. **Codex-native memory**: Codex's memory database, sessions, and automatic
   consolidation under `~/.codex`.

Only the first class crosses agents. Native automatic memories never write
directly into the shared bank.

### Capture and promotion

Both adapters emit candidate records into one inbox schema with:

- source agent
- source account/profile where available
- project identity
- session/thread identifier
- timestamp
- candidate type
- prompt provenance
- content hash

`memory-review` remains the promotion gate. Accepted candidates become shared
memory files with stable IDs and an index. Rejections remain recorded so the
same candidate is not repeatedly proposed. Secrets are rejected before the
inbox write and again before promotion.

Both agents inject only the relevant project's approved index at session start.
Full memory bodies load on demand. The existing seven Claude memory banks are
copied into the shared store with hashes and provenance; originals remain intact
until parity is proven.

## Scheduling and unattended work

Schedules are declared once in `core/schedules` and assigned an execution
surface:

- Codex Scheduled task for workflows that benefit from a persistent chat,
  plugins, Codex tools, or isolated worktrees.
- Launchd for local scripts, ledgers, machine health, or behavior that must not
  spend model turns.
- Agent-native cloud scheduling only when the required files and credentials are
  available there.

The current three launchd jobs remain active through migration. Equivalent
Codex tasks are added only after duplicate-run prevention exists. Every schedule
has an owner, cadence, timeout, model/effort policy, output path, last-run state,
and idempotency key.

## Installation ownership

Generated releases carry a manifest containing the core source hash, adapter
contract version, generator version, generation timestamp, content hashes,
capability matrix, and every native path kingstack owns. Installation follows:

1. render a complete immutable release under the private adapter store
2. validate syntax, schemas, capability declarations, and content hashes
3. compare its ownership manifest against the live agent home
4. refuse unknown, modified, mixed-ownership, or agent-native paths
5. atomically preserve each pre-existing kingstack-owned path by renaming it
   into a dated private backup
6. install only the reviewed wrapper or symbolic link for that owned path
7. atomically select the verified release through the adapter's `current` link
8. run native and shared health checks in fresh sessions

Agent homes remain real native directories; kingstack never replaces or links
an entire `~/.claude`, `~/.codex`, or future agent home. Authentication,
sessions, transcripts, databases, caches, plugins, MCP state, trusted-project
state, notifications, and native automatic memory are outside kingstack
ownership.

The installer has per-adapter and `--all` modes plus `--dry-run`. It never
removes an unknown file and never performs a general file-by-file restore into a
live home. Forced replacement requires an explicit flag, an ownership match,
and a successfully verified dated backup.

## Migration sequence

### Phase 0: freeze and inventory

- Require clean kingstack Git state.
- Record the live baseline, hashes, symlinks, modes, and schedules.
- Capture immutable, user-only snapshots of authored Claude files and existing
  Codex configuration. Snapshots are evidence and disaster-recovery inputs, not
  instructions for mutating a live home in place.
- Export a redacted configuration report; never export auth or secret values.

### Phase 1: create neutral checkout

- Clone the existing kingstack repository to `~/Desktop/Work/kingstack`.
- Preserve remote, branches, tags, commit authorship, and full history.
- Add the core/adapter structure without changing live profiles.
- Keep `~/.claude` untouched and operational.

### Phase 2: extract the shared core

- Decompose instructions and routing policy into portable fragments.
- Move portable skill sources into the core.
- Preserve pstack revision and transformation behavior.
- Define and test the agent-neutral adapter contract and capability-matrix
  schema before treating either initial adapter as canonical.
- Add generation tests proving adapter output is deterministic.

### Phase 3: stage adapters

- Generate immutable Claude and Codex release candidates under the private
  adapter store without linking a live path.
- Validate JSON, TOML, Markdown frontmatter, hook schemas, shell/Python syntax,
  model mappings, and skill registration.
- Compare the staged Claude adapter against the live baseline.
- Prove both adapters satisfy the common contract or record explicit gaps.

### Phase 4: migrate shared memory

- Copy the seven curated banks into `~/.kingstack/memory`.
- Preserve filenames, bodies, indexes, timestamps, and hashes.
- Update both adapters to read the shared bank.
- Keep original Claude banks unchanged.

### Phase 5: install Claude adapter

- Stop for Hassan's pre-link briefing and approval.
- Preserve and link only manifest-owned Claude surfaces; do not replace the
  Claude home or touch native state.
- Start a fresh test session in both Claude profiles.
- Prove pstack, king-mode, memory capture/review, compaction preservation,
  subagent visibility, model routing, health checks, and schedules.
- Roll back the test installation once, then reinstall to prove reversibility.

### Phase 6: install Codex adapter

- Preserve and link only manifest-owned Codex surfaces without altering auth,
  notifications, plugins, MCP, trusted projects, or existing native state.
- Enable native memories with explicit safe settings.
- Install global AGENTS.md, shared skills/plugin, hooks, and routing defaults.
- Start fresh CLI and desktop sessions and prove native behavior.
- Run the official Claude import as a comparison report and reconcile any
  supported capability the adapter missed.

### Phase 7: switch canonical ownership

- Update launchd jobs, aliases, and wrappers to the neutral checkout.
- Mark `~/Desktop/Work/kingstack` as canonical in both adapters.
- Preserve the original `~/.claude` repository metadata and authored files as a
  dated backup.
- Push only after all acceptance tests pass and Hassan reviews the diff.

### Adding another agent

A future agent is added without changing core meaning:

1. inventory its native configuration and private-state boundaries
2. implement the adapter contract and capability matrix
3. map portable model/effort tiers and lifecycle intents
4. generate and validate an immutable release candidate
5. prove shared-memory and scheduling behavior in staging
6. document unsupported or degraded capabilities
7. obtain a pre-link review, preserve owned native paths, and activate its
   versioned release

No existing adapter is copied as the new source of truth. Reuse happens through
the contract, generators, fixtures, and shared core.

## Verification strategy

### Static verification

- The adapter contract schema and every capability matrix validate.
- Every claimed native, emulated, degraded, or unsupported capability has a
  corresponding test or explicit evidence record.
- JSON parses with `jq`.
- TOML parses with a real TOML parser.
- Every shell script passes `bash -n`.
- Every Python file compiles and its focused tests pass.
- Every skill has valid frontmatter and registers in its target harness.
- No unresolved Claude names appear in Codex-only output, and vice versa,
  except explicit documentation.
- No secret-shaped values or runtime files are tracked.

### Behavioral verification

For each agent, fresh sessions must prove:

1. global instructions load
2. non-trivial work activates the process and personal layers
3. model and effort appear on subagent start
4. bulk output triggers the context warning
5. compaction writes a checkpoint and preserves required state
6. a candidate memory reaches the shared inbox
7. promotion makes the memory visible to both agents
8. a rejected candidate does not return
9. scheduled health work runs through its real scheduler
10. `kingstack check` reports the correct adapter state

### No-loss parity

Migration cannot switch canonical ownership unless all conditions hold:

```text
Claude capability names before == Claude capability names after
Claude authored file hashes before == preserved source or intentional transform
Memory content hashes before == shared-memory content hashes after
Pstack upstream revision before == adapter source revision after
Schedules before == active or deliberately mapped schedules after
Codex pre-existing config == preserved config plus reviewed kingstack additions
```

Any mismatch blocks the switch and leaves the current Claude installation live.

## Rollback

Rollback is a first-class command, not a general restore engine and not merely
written instructions.

Normal adapter rollback operates only on manifest-owned surfaces:

1. stop new activation
2. atomically move the adapter's `current` link to the preceding verified
   release, or remove a newly installed owned wrapper
3. atomically rename the dated original owned path back into place where the
   migration introduced the path
4. restore prior hook and scheduler registrations from their ownership records
5. run the same health and parity checks used during activation

Immutable snapshots are never replayed file by file into a live agent home. For
disaster recovery, a snapshot is materialized into a separate directory,
verified there, and presented for an explicit whole-directory recovery decision.
The original live tree is not incrementally repaired.

Rollback never touches auth, transcripts, native memory databases, caches,
plugins, or shared-memory content. It is tested against staged homes and then by
one controlled activate/rollback/re-activate cycle on every initial adapter
before migration is declared complete.

## Versioning, changelog, and roadmap

Kingstack uses Semantic Versioning for the public framework. A tracked `VERSION`
file is the current release version and annotated Git tags use `vMAJOR.MINOR.PATCH`.
The migration culminates in the first reviewed agent-neutral release rather than
inventing a version before the capability set is proven.

`CHANGELOG.md` follows a Keep-a-Changelog shape with an `[Unreleased]` section.
Every material change to behavior, configuration schema, hooks, adapters,
memory, routing, schedules, installation, or rollback adds one concise user-
visible entry in the same task. Release automation moves those entries under a
dated version heading, updates comparison links, updates `VERSION`, and refuses
to tag a dirty or unhealthy tree.

The existing `docs/BACKLOG.md` becomes `docs/ROADMAP.md` through `git mv`, then
is rewritten against the agent-neutral architecture rather than merely renamed.
Every existing item is audited: valid ideas are preserved and clarified; stale,
completed, or duplicate items are removed only with an evidence note in the
migration report. There is one durable planning surface rather than parallel
backlog and roadmap files. It has `Now`, `Next`, `Later`, and `Done` sections.
Active items require an outcome and finish condition; completed items move to
`Done` with a version or commit and eventually compact into the changelog.

Shared operating policy requires agents to update `[Unreleased]` whenever a
material capability changes and update the roadmap whenever scope or priority
changes. `kingstack check --release-hygiene` enforces that release-relevant
changes since the last version have an unreleased entry, the roadmap is valid,
the version/tag relationship is coherent, and no completed roadmap item lacks
a durable destination. This avoids relying on memory or goodwill to maintain
the records.

## Security and privacy

- The public repository contains no memories, transcripts, ledgers, credentials,
  environment values, machine identifiers, or private project paths beyond
  documented examples.
- Generated reports redact emails, tokens, URLs with credentials, and secret-like
  values.
- Shared memory is local, user-only, and human-approved.
- Native memories remain private to each agent.
- Hooks receive the minimum input required and use scoped permissions.
- Scheduled model work uses the narrowest sandbox and never relies on interactive
  approval.
- Import output is reviewed before any generated configuration is installed.

## Acceptance criteria

The design is complete when implementation proves all of the following:

- `~/Desktop/Work/kingstack` is the canonical clean Git checkout with full
  existing history and the same remote.
- A versioned adapter contract and capability-matrix schema exist independently
  of Claude and Codex, with a documented path for a third adapter.
- Claude and Claude Personal remain operational and behaviorally equivalent to
  the baseline.
- Codex loads native kingstack guidance, skills, hooks, memory, and routing.
- All 65 baseline skills are either available in both agents or documented as
  package-managed with equivalent availability.
- All pstack workflows remain upstream-syncable and protected from clobbering.
- The seven curated memory banks are shared without losing or rewriting content.
- Raw agent state remains separate.
- Both adapters pass static and behavioral suites.
- Versioned activation and manifest-owned rollback have been exercised
  successfully for both initial adapters without replacing either native home.
- Immutable snapshots verify, and no production command performs an in-place
  file-by-file restore into a live agent home.
- No secrets or runtime state are tracked.
- `kingstack check --all` is green.
- Semantic version, changelog, and roadmap checks are green, with one source of
  truth for future work.
- Hassan reviews the final migration diff before push or removal of any legacy
  backup.

## Official Codex references

- [Import from another agent](https://learn.chatgpt.com/docs/import)
- [Custom instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Hooks](https://learn.chatgpt.com/docs/hooks)
- [Memories](https://learn.chatgpt.com/docs/customization/memories)
- [Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Scheduled tasks](https://learn.chatgpt.com/docs/automations)
