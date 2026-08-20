# Kingstack Versioned Cutover, Documentation, and Final Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate versioned Claude and Codex adapters through narrowly manifest-owned paths, transfer canonical operational ownership to the neutral checkout, keep schedules single-owned, rewrite product documentation, exercise rollback for both initial agents, and push only after complete no-loss acceptance review.

**Architecture:** Encode schedules and health checks as portable declarations, build immutable Claude and Codex releases, and generate exact ownership/activation plans. Stop for Hassan's requested briefing before any live link. After approval, preserve each manifest-owned original, install only stable wrappers or links, select the verified releases, prove/rollback/re-activate both adapters, rewrite every affected authored Markdown surface, and run a cross-agent behavioral matrix. Native homes and the legacy `~/.claude` repository remain intact outside those owned paths.

**Tech Stack:** Python 3 standard library, launchd, Claude Code, Codex, Git, JSON manifests, shell/Python test suites.

**Spec:** `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md`

## Global Constraints

- Do not remove `.git`, tracked files, memory banks, or runtime state from `~/.claude`.
- Do not enable a Codex Scheduled task that duplicates an active launchd job.
- Keep local no-model work under launchd. Move work to Codex scheduling only when it needs a persistent Codex chat/plugin/worktree and has an idempotency key.
- A live activation requires a fresh source/hash recheck, an exact ownership manifest with unique dated-sibling paths, and Hassan's explicit pre-link approval immediately before writes.
- Push only after Hassan reviews the final diff, rollback evidence, and no-loss matrix.
- Deleting or archiving the legacy Claude checkout is a separate future decision, not part of this plan.
- After every acceptance and rollback gate passes, delete the six dated implementation-plan files Hassan named from both the canonical checkout and their exact legacy `~/.claude` paths; preserve the approved design spec and Git history.
- Maintain one product-governance surface: SemVer in `VERSION`, Keep-a-Changelog entries in `CHANGELOG.md`, and the existing backlog renamed to `docs/ROADMAP.md` rather than duplicated.
- Never link an entire agent home or expose an archive, snapshot, or file-by-file restore command.

---

### Task 1: Declare schedules once and detect duplicate ownership

**Files:**

- Create: `core/schedules/schedules.json`
- Create: `lib/kingstack/schedules.py`
- Create: `tests/test_schedules.py`
- Modify: `scripts/install-launchd.sh`
- Modify: `lib/kingstack/render.py`

- [ ] **Step 1: Write failing schedule-schema and collision tests**

Each schedule requires: stable ID, owner (`launchd`, `codex`, or `cloud`),
cadence, command/task template, timeout, model tier/effort when applicable,
output path, idempotency key, and enabled state. Assert two enabled owners for
one stable ID fail. Assert no-model launchd work cannot declare a model.

- [ ] **Step 2: Encode the current three launchd jobs exactly**

Use the foundation inventory for labels, calendars, commands, and output paths.
Do not infer or modernize. The initial owner of all three stays `launchd` because
they are proven local-machine operations.

- [ ] **Step 3: Render launchd plists and compare semantics**

Normalize plist dictionary ordering, then assert label, program arguments,
calendar interval, environment, stdout/stderr, timeout behavior, and working
directory match the current active definitions. The only approved change is the
script root from `~/.claude` to `~/Desktop/Work/kingstack` after cutover.

- [ ] **Step 4: Add scheduler state and idempotency checks**

Before a job starts, atomically claim `~/.kingstack/manifests/schedules/ID.lock`;
record owner, start, completion, exit, output hash, and next expected time. A
second owner exits without doing work and logs `duplicate prevented`.

- [ ] **Step 5: Run tests and commit**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_schedules -v
git add core/schedules lib/kingstack/schedules.py tests/test_schedules.py scripts/install-launchd.sh lib/kingstack/render.py
git commit -m "feat: make schedule ownership explicit and single-run"
```

### Task 2: Build the versioned Claude release and activation plan

**Files:**

- Create: `adapters/claude/owned-paths.json`
- Create: `adapters/claude/bin/claude-check`
- Create: `adapters/claude/bin/kingstack-path`
- Create: `tests/test_claude_release.py`
- Modify: `lib/kingstack/release.py`
- Modify: `lib/kingstack/activation.py`
- Modify: `lib/kingstack/cli.py`

- [ ] **Step 1: Write fake-home release, ownership, and rollback-plan tests for both profile shapes**

Cover a normal `~/.claude` home and a second config directory whose shared
files are symlinks. Test deterministic immutable release IDs, unknown-file
refusal, modified-owned-file refusal, failed settings merge, duplicate
ownership, whole-home ownership refusal, interrupted private release
publication, no-write activation planning, and dated-original rollback plans.
Assert the plan preserves symlink targets and modes exactly and never names
memory/auth/session/plugin sentinels.

- [ ] **Step 2: Define Claude ownership narrowly**

Owned paths are generated `CLAUDE.md`, kingstack hook registrations, adapter
wrappers, managed skills/agents, and schedule wrappers. Existing settings keys,
plugins, native profile state, and unknown files remain unowned. The release
manifest maps each owned path to a release-relative target and exact dated
original location. The JSON merger adds or replaces only kingstack hook entries
and approved defaults; it does not rewrite unrelated keys.

- [ ] **Step 3: Make old commands resolve the neutral checkout**

Compatibility wrappers in the staged release exec the neutral
`scripts/kingstack` or canonical scripts. They contain no business logic.
`claude-check` becomes `kingstack check --adapter claude` while retaining the
old command name and exit behavior. No wrapper is linked during this task.

- [ ] **Step 4: Run focused install tests**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_claude_release -v`

- [ ] **Step 5: Render and review the real dry-run**

```bash
./scripts/kingstack render --adapter claude --output .staging/claude
ks_claude_release=$(./scripts/kingstack release build --adapter claude --staged .staging/claude --print-id)
test -n "${ks_claude_release:?}"
./scripts/kingstack release verify --adapter claude --release "$ks_claude_release"
./scripts/kingstack activate --adapter claude --release "$ks_claude_release" --all-profiles --dry-run
```

The report lists every proposed preserved original, wrapper/link, `current`
release selection, and unchanged live capability. Any path not in the ownership
declaration blocks the plan. Confirm the command created no live link.

- [ ] **Step 6: Commit the versioned Claude release mechanism**

```bash
git add adapters/claude/owned-paths.json adapters/claude/bin lib/kingstack/release.py lib/kingstack/activation.py lib/kingstack/cli.py tests/test_claude_release.py
git commit -m "feat: stage versioned Claude adapter releases"
```

### Task 3: Brief, activate, prove, roll back, and re-activate both initial adapters

**Files:**

- Create: `docs/migration/pre-link-briefing.md`
- Create: `docs/migration/claude-live-verification.md`
- Create: `docs/migration/codex-live-verification.md`

- [ ] **Step 1: Generate the mandatory pre-link briefing and stop**

The briefing records the canonical clone HEAD/origin/history proof; Claude and
Codex release IDs; capability matrices
and every non-native gap; shared-memory parity; pstack revision; all proposed
owned paths, existing types/hashes/modes, dated-original locations, and link
targets; unchanged native-state categories; hook hashes requiring trust;
schedule changes; exact activation commands; exact rollback commands; and
residual risks. Run both activation commands with `--dry-run` and attach their
machine-readable plans.

Stop and ask Hassan for explicit approval. A previous design or migration
approval is insufficient. Do not proceed to Step 2 until he approves this exact
briefing.

- [ ] **Step 2: Recheck live identities and activate the approved releases**

```bash
./scripts/kingstack activate --adapter claude --release "$ks_claude_release" --all-profiles --apply --approved-briefing docs/migration/pre-link-briefing.md
./scripts/kingstack activate --adapter codex --release "$ks_codex_release" --apply --approved-briefing docs/migration/pre-link-briefing.md
```

Immediately re-run the live precondition hashes captured by each activation
plan. Abort before a write on any mismatch. Hold the per-home activation lock,
open the verified native parent directory without following symlinks, atomically
rename each owned original to its unique dated sibling in that same directory,
then install the stable wrapper/link descriptor-relatively. Never copy or delete
the original and never link an entire agent home.

- [ ] **Step 3: Start fresh Claude work/personal and Codex CLI/desktop sessions**

For each surface prove: global instructions; pstack default process layer;
king-mode personal layer; shared project memory index; model/effort visibility;
bulk warning; PreCompact checkpoint; Stop candidate capture; all baseline skill
names or recorded package-equivalent providers; current commands; and native
authentication still works. Review and trust only the exact approved Codex hook
hashes. Use harmless fixtures, not production repos or databases.

- [ ] **Step 4: Prove the three real launchd jobs from their installed definitions**

Kickstart each job with launchctl, verify its exact installed argv resolves the
neutral checkout, validate output/ledger changes, and confirm duplicate-run
prevention. Do not rely on running scripts directly.

- [ ] **Step 5: Exercise manifest-owned rollback for both adapters**

Apply rollback using each activation manifest. Compare every restored hash,
symlink target, mode, schedule definition, and agent health with the dated
originals and pre-link inventory. Start all four surfaces; run the old
`claude-check` and the pre-existing Codex health/config commands to prove the
previous setups still operate. Historical snapshot/archive artifacts are
neither required nor consulted.

- [ ] **Step 6: Re-activate the same immutable releases and rerun the smoke suite**

Re-activate from the same release IDs after rechecking original/live hashes.
Repeat fresh start, memory index, one representative skill, one subagent
visibility event, and `kingstack check --adapter` for Claude and Codex.

- [ ] **Step 7: Record exact evidence and commit**

```bash
git add docs/migration/pre-link-briefing.md docs/migration/claude-live-verification.md docs/migration/codex-live-verification.md
git commit -m "test: prove versioned adapters and live rollback"
```

### Task 4: Implement one cross-agent health command

**Files:**

- Create: `lib/kingstack/checks.py`
- Create: `tests/test_checks.py`
- Modify: `lib/kingstack/cli.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing independent-check tests**

Each check returns its own status rather than using a shared global failure flag
(the existing framework previously hid passing evidence this way). Inject one
unrelated failure and assert all other pass lines remain visible.

- [ ] **Step 2: Implement `kingstack check` modes**

```text
kingstack check --core
kingstack check --adapter claude
kingstack check --adapter codex
kingstack check --memory
kingstack check --schedules
kingstack check --all
```

Checks include tracked-source cleanliness, generated-manifest drift, instruction
coverage, skill capability/provider parity, hook registration/hash/trust status,
config-owned keys, shared memory integrity, original memory source preservation,
scheduler ownership/last run, private permissions, pstack revision, and secret/
runtime tracking guards.

- [ ] **Step 3: Add machine-readable output**

`--json` emits schema-versioned rows `{id, adapter, status, evidence, fix}` and
an overall result. Human output derives from the same rows. Exit 0 only if all
required checks pass; drift exits 1; invalid invocation exits 2.

- [ ] **Step 4: Run tests and verify the exact healthy count**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_checks -v
./scripts/kingstack check --all
./scripts/kingstack check --all --json | jq -e '.overall == "healthy"'
```

Update the README with a count only after measuring it. Prefer documenting the
command over freezing a count that will drift.

- [ ] **Step 5: Commit**

```bash
git add lib/kingstack/checks.py lib/kingstack/cli.py tests/test_checks.py README.md
git commit -m "feat: verify the whole kingstack from one command"
```

### Task 5: Rewrite Markdown surfaces and add version, changelog, and roadmap governance

**Files:**

- Create: `VERSION`
- Create: `CHANGELOG.md`
- Move: `docs/BACKLOG.md` -> `docs/ROADMAP.md`
- Create: `docs/markdown-surfaces.json`
- Create: `docs/migration/markdown-rewrite-report.md`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `model-routing.md`
- Modify: `pstack-models.md`
- Modify: `hooks/poteto-mode-context.md`
- Modify: `skills/king-mode/SKILL.md`
- Modify: `skills/memory-review/SKILL.md`
- Modify: `sweeps/README.md`
- Modify: `sweeps/_template.md`
- Modify: `sweeps/kingstack-health.md`
- Modify: `sweeps/usage-watch.md`
- Modify: `docs/token-projection-2026-08.md`
- Delete: `.superpowers/sdd/2026-08-20-kingstack-foundation-plan/task-3-report.md`
- Modify: `lib/kingstack/release.py`
- Create: `lib/kingstack/docs_hygiene.py`
- Create: `tests/test_release.py`
- Create: `tests/test_docs_hygiene.py`
- Modify: `lib/kingstack/checks.py`
- Modify: `lib/kingstack/cli.py`
- Modify: `core/instructions/70-stack-iteration.md`

- [ ] **Step 1: Write failing Markdown-classification and stale-architecture tests**

Create a manifest schema whose status is exactly `rewrite`, `historical`,
`upstream`, `fixture`, or `delete-at-final-acceptance`. The test enumerates
`git ls-files '*.md'` and fails if any Markdown file is unclassified, any
current authored surface still calls `~/.claude` canonical, any production
command exposes archive/snapshot create, verify, apply, or restore, any shared interface restricts adapter
IDs to Claude/Codex, or any file marked historical lacks a visible historical
banner. Test fixtures may remain unchanged; upstream skill workflow text may
remain unchanged only with provenance.

```python
def test_every_tracked_markdown_has_a_disposition(self):
    self.assertEqual(set(git_markdown_files()), set(surface_manifest()))

def test_current_docs_have_no_backup_engine_contract(self):
    self.assertEqual(scan_current_docs(["snapshot apply", "restore_snapshot",
                                        "archive create", "archive verify"]), [])
```

- [ ] **Step 2: Rewrite every affected authored Markdown surface**

`README.md` leads with kingstack as an agent-neutral control plane and explains
core, adapter contract, capability matrix, private runtime, versioned releases,
memory classes, adding an adapter, activation, rollback, schedules, health,
versioning, and fresh-machine setup. `CLAUDE.md` becomes a generated-compatibility
surface whose shared meaning points to core fragments. Routing docs use portable
tiers and explicit adapter mappings. Authored skills and sweeps use `kingstack`
commands and `adapter_id`; they do not assume Claude is the parent harness.
`docs/token-projection-2026-08.md` receives a historical-measurement banner and
keeps its original numbers unchanged.

Move the failed foundation transaction evidence needed for engineering history
into a redacted section of `docs/migration/markdown-rewrite-report.md`, then
remove the tracked SDD task report because it contains absolute machine paths,
private snapshot identifiers, and implementations superseded by the approved
non-destructive ownership design. Do not delete private snapshots or archives.

The report lists every tracked Markdown file, its classification, whether it
changed, and why. The six dated implementation plans are classified
`delete-at-final-acceptance`; they are rewritten now for execution and removed
only at the final approved cleanup.

- [ ] **Step 3: Write failing behavior tests for release hygiene**

Name the production break each test catches: malformed SemVer; version/tag
mismatch; release-relevant changes with an empty `[Unreleased]`; roadmap without
`Now`, `Next`, `Later`, and `Done`; completed roadmap item without a commit or
version; dirty/unhealthy release refusal. Use temporary real Git repositories
and hand-derived expected results rather than grepping source text.

- [ ] **Step 4: Establish the single version and planning sources**

Choose the initial version from repository history and the proven migration
scope; do not invent it before reviewing existing tags. Create a
Keep-a-Changelog document with `[Unreleased]`, and use `git mv` to preserve the
history of `docs/BACKLOG.md` as `docs/ROADMAP.md`. Rewrite it for the
agent-neutral architecture: audit every old item, preserve and clarify valid
ideas, and remove stale/completed/duplicate items only when the migration report
records the evidence. The rewritten roadmap must include adapter SDK maturity,
third-adapter validation, cloud availability, Slack agent gateway, usage-aware
routing, `/loop` adoption, and team distribution where still valid. Organize the result under `Now`, `Next`, `Later`, and
`Done`, with an outcome and finish condition for every active item.

- [ ] **Step 5: Implement documentation, release, and hygiene commands**

```text
kingstack check --release-hygiene
kingstack check --docs-hygiene
kingstack release prepare MAJOR.MINOR.PATCH --dry-run
kingstack release prepare MAJOR.MINOR.PATCH --apply
kingstack release verify MAJOR.MINOR.PATCH
```

Preparation requires a clean tree, `kingstack check --all` green, non-empty
unreleased entries, coherent roadmap, and a version greater than the latest
SemVer tag. It atomically updates `VERSION`, dates the changelog section, and
prints the exact annotated-tag command; it does not push or publish.

- [ ] **Step 6: Make maintenance a shared operating rule**

The portable instruction says: every material capability/config/schema/hook/
adapter/memory/routing/schedule/install/rollback change updates
`CHANGELOG.md` `[Unreleased]` in the same task; every scope or priority change
updates `docs/ROADMAP.md`; every new or removed tracked Markdown file updates
`docs/markdown-surfaces.json`; one fact never lives in two authoritative docs. Documentation-only
wording and tests that do not change behavior are exempt.

- [ ] **Step 7: Run tests, both hygiene checks, and a dry-run release**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_release -v
PYTHONPATH=lib python3 -m unittest tests.test_docs_hygiene -v
./scripts/kingstack check --docs-hygiene
./scripts/kingstack check --release-hygiene
./scripts/kingstack release prepare "$(cat VERSION)" --dry-run
```

- [ ] **Step 8: Commit**

```bash
git add VERSION CHANGELOG.md README.md CLAUDE.md model-routing.md pstack-models.md hooks/poteto-mode-context.md skills/king-mode/SKILL.md skills/memory-review/SKILL.md sweeps/README.md sweeps/_template.md sweeps/kingstack-health.md sweeps/usage-watch.md docs/token-projection-2026-08.md docs/ROADMAP.md docs/markdown-surfaces.json docs/migration/markdown-rewrite-report.md .superpowers/sdd/2026-08-20-kingstack-foundation-plan/task-3-report.md lib/kingstack/release.py lib/kingstack/docs_hygiene.py lib/kingstack/checks.py lib/kingstack/cli.py core/instructions/70-stack-iteration.md tests/test_release.py tests/test_docs_hygiene.py
git commit -m "docs: make kingstack agent-neutral and release-governed"
```

### Task 6: Run the cross-agent behavioral acceptance matrix

**Files:**

- Create: `tests/behavior/run_matrix.py`
- Create: `tests/behavior/cases.json`
- Create: `docs/migration/cross-agent-acceptance.md`

- [ ] **Step 1: Encode the ten acceptance behaviors from the spec**

Each case records setup, native trigger, expected observable evidence, cleanup,
and whether it must be run manually because it crosses a security/desktop
boundary. The runner never marks a manual case passed without an evidence path
and timestamp.

- [ ] **Step 2: Execute equivalent cases in fresh Claude work, Claude personal, Codex CLI, and Codex desktop sessions**

Required behaviors: instructions, process/personal layers, subagent visibility,
bulk warning, compaction checkpoint/preservation, candidate capture, cross-agent
promotion, rejection suppression, scheduler execution, and adapter health.

- [ ] **Step 3: Test one real cross-agent memory round trip**

Create a harmless unique fact in Claude, capture it, approve it through Codex,
start fresh sessions in both agents, and prove both see the same approved index.
Then create a second candidate in Codex, reject it through Claude, and prove it
does not recur. Remove only these test records through the store's audited test
cleanup command.

- [ ] **Step 4: Test compaction recovery, not only hook output**

In each agent create a session with a stated finish condition, touched file,
open decision, correction, and pending command; trigger native compaction; then
ask for all five. Compare the answer with the mechanical checkpoint. A missing
item fails even if the hook itself ran.

- [ ] **Step 5: Write the matrix with VERIFIED / NOT VERIFIED / INCONCLUSIVE**

No narrative substitution for a failed row. Each verified row links its log,
manifest, checkpoint, or session evidence. Inconclusive rows block canonical
cutover unless Hassan explicitly accepts the exception.

- [ ] **Step 6: Commit**

```bash
git add tests/behavior docs/migration/cross-agent-acceptance.md
git commit -m "test: verify kingstack behavior across Claude and Codex"
```

### Task 7: Switch operational references to the neutral checkout

**Files:**

- Modify: `README.md`
- Modify: `core/instructions/70-stack-iteration.md`
- Modify: `core/schedules/schedules.json`
- Create: `docs/migration/legacy-claude-checkout.md`

- [ ] **Step 1: Verify all acceptance rows and clean state before switching**

Run `kingstack check --all`, the entire test suite, both native health commands,
Git fsck, original-memory verification, and schedule last-run checks. Abort on
any failure.

- [ ] **Step 2: Update canonical path references**

Guidance now says stack work starts with:

```bash
cd ~/Desktop/Work/kingstack && claude
cd ~/Desktop/Work/kingstack && codex
```

Re-render/reinstall both adapters so the same source names the neutral repo.
Update launchd definitions only after their semantic diff shows path-only
changes, then kickstart and verify all three again.

- [ ] **Step 3: Mark, but do not dismantle, the legacy checkout**

Document `~/.claude` as the live Claude home and legacy Git rollback checkout.
Record its HEAD, origin, and why `.git` remains. Do not move
or delete `.git`, tracked files, or original memory. Add a health warning if new
kingstack commits are made there after cutover.

- [ ] **Step 4: Commit**

```bash
git add README.md core/instructions/70-stack-iteration.md core/schedules/schedules.json docs/migration/legacy-claude-checkout.md
git commit -m "docs: make neutral kingstack the canonical control plane"
```

### Task 8: Final no-loss audit, review, and push gate

**Files:**

- Create: `docs/migration/final-no-loss-report.md`

- [ ] **Step 1: Compare every baseline invariant**

The report includes machine-checked tables for:

```text
Claude capability names before == after
Claude authored hashes == preserved source or named transform
Original memory hashes == shared memory hashes
Pstack revision == adapter source revision
Schedules == active mapped schedules
Codex pre-existing unowned config bytes == current unowned config bytes
Auth/session/native-memory sentinels == unchanged
Historical snapshots/archives == untouched; dated owned originals == rollback-ready
```

- [ ] **Step 2: Scan the public repository for forbidden state**

Scan tracked files for credential prefixes, private-key blocks, assignment-
shaped secrets, raw memory bodies, transcript extensions, ledgers, absolute
private runtime paths, caches, backups, and generated adapters. Review every
match; variable names alone are not secrets.

- [ ] **Step 3: Disable the Superpowers provider only after replacement parity is independently proven**

Run the capability/provider report and require every overlapping Superpowers
skill used by this migration to have a verified kingstack or pstack provider.
Record `codex plugin list --json` and the exact discovered Superpowers source.
Because current Codex may expose Superpowers as a cache-only curated package
rather than an installed plugin, disable by provider type:

- installed plugin: first atomically move its exact source and manifest into
  the private disabled-provider directory, then
  run the official `codex plugin remove PLUGIN@MARKETPLACE --json`
- cache-only package: atomically rename only the exact version directory into
  `~/.kingstack/disabled/superpowers/<version>-<content-hash>`; do not recursively
  remove the marketplace or unrelated cache

Start a fresh Codex session and prove no `superpowers:*` skill is advertised,
the required capability-name set is unchanged through kingstack/pstack, and all
behavioral tests remain green. If Codex rehydrates the package or any capability
is missing, atomically rename the disabled provider back immediately and block
acceptance. The private disabled provider remains recoverable after success.

- [ ] **Step 4: Run final verification from a fresh shell**

```bash
cd "$HOME/Desktop/Work/kingstack"
PYTHONPATH=lib python3 -m unittest discover -s tests -v
./scripts/kingstack check --all
git fsck --full
git status --short --branch
git log --oneline --decorate -20
```

- [ ] **Step 5: Have Hassan review the complete diff and reports**

Present before/after architecture, every intentional transform, rollback IDs,
behavior matrix, remaining exceptions, and exact commits pending push. Do not
push on a generic earlier approval; this is the explicit final migration gate.

- [ ] **Step 6: Remove the completed implementation plans, then push after approval**

Remove these six files from the canonical checkout and commit the removal:

```text
docs/superpowers/plans/2026-08-20-agent-neutral-kingstack-migration.md
docs/superpowers/plans/2026-08-20-kingstack-foundation-plan.md
docs/superpowers/plans/2026-08-20-kingstack-core-claude-plan.md
docs/superpowers/plans/2026-08-20-kingstack-shared-memory-plan.md
docs/superpowers/plans/2026-08-20-kingstack-codex-adapter-plan.md
docs/superpowers/plans/2026-08-20-kingstack-cutover-plan.md
```

Then push and verify:

```bash
git push origin main
git fetch origin main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
./scripts/kingstack check --all
```

- [ ] **Step 7: Remove the exact legacy plan paths after the successful push**

Verify each of the six files exists in the pushed Git history, then delete
exactly the six `/Users/mac/.claude/docs/superpowers/plans/...` paths Hassan
listed. Do not recurse into the plans directory and do not remove the approved
design spec. Verify each target is absent. The content remains recoverable from
the canonical and legacy Git histories; no new private archive is created.

- [ ] **Step 8: Keep rollback material**

Report the untouched historical snapshots/archives, dated manifest-owned
originals, disabled Superpowers provider, and legacy checkout location. Ask separately
in a future session before deleting any of them. Completion means the new system
works and the old system remains recoverable—not that old data has been erased.
