# Kingstack Cutover, Schedulers, and Final Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the Claude adapter in both profiles, transfer canonical operational ownership to the neutral checkout, keep schedules single-owned, exercise rollback for both agents, and push only after a complete no-loss acceptance review.

**Architecture:** First encode schedules and health checks as portable declarations. Then install the staged Claude adapter through compatibility wrappers, prove and roll it back, reinstall it, repoint only verified operational paths to the neutral checkout, and run a cross-agent behavioral matrix. The legacy `~/.claude` repository remains intact as rollback material until Hassan separately approves archival or removal.

**Tech Stack:** Python 3 standard library, launchd, Claude Code, Codex, Git, JSON manifests, shell/Python test suites.

**Spec:** `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md`

## Global Constraints

- Do not remove `.git`, tracked files, memory banks, or runtime state from `~/.claude`.
- Do not enable a Codex Scheduled task that duplicates an active launchd job.
- Keep local no-model work under launchd. Move work to Codex scheduling only when it needs a persistent Codex chat/plugin/worktree and has an idempotency key.
- A live install requires a fresh snapshot and hash recheck immediately before writes.
- Push only after Hassan reviews the final diff, rollback evidence, and no-loss matrix.
- Deleting or archiving the legacy Claude checkout is a separate future decision, not part of this plan.

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

### Task 2: Build Claude atomic install and compatibility wrappers

**Files:**

- Create: `adapters/claude/owned-paths.json`
- Create: `adapters/claude/bin/claude-check`
- Create: `adapters/claude/bin/kingstack-path`
- Create: `tests/test_install_claude.py`
- Modify: `lib/kingstack/install.py`
- Modify: `lib/kingstack/rollback.py`
- Modify: `lib/kingstack/cli.py`

- [ ] **Step 1: Write fake-home destruction tests for both profile shapes**

Cover a normal `~/.claude` home and a second config directory whose shared
files are symlinks. Test unknown-file refusal, modified-owned-file refusal,
failed settings merge, interrupted install, successful install, and rollback.
Assert symlink targets and modes restore exactly and memory/auth/session
sentinels never change.

- [ ] **Step 2: Define Claude ownership narrowly**

Owned paths are generated `CLAUDE.md`, kingstack hook registrations, adapter
wrappers, managed skills/agents, and schedule wrappers. Existing settings keys,
plugins, native profile state, and unknown files remain unowned. The JSON merger
adds or replaces only kingstack hook entries and approved defaults; it does not
rewrite unrelated formatting unless the live file is already normalized and
the before hash is captured.

- [ ] **Step 3: Make old commands resolve the neutral checkout**

Compatibility wrappers under `~/.claude/scripts` and `~/.claude/bin` exec the
neutral `scripts/kingstack` or canonical scripts. They contain no business
logic. `claude-check` becomes `kingstack check --adapter claude` while retaining
the old command name and exit behavior.

- [ ] **Step 4: Run focused install tests**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_install_claude -v`

- [ ] **Step 5: Render and review the real dry-run**

```bash
./scripts/kingstack render --adapter claude --output .staging/claude
./scripts/kingstack install --claude --all-profiles --dry-run
```

The report lists every write, backup, symlink change, and unchanged live
capability. Any path not in the ownership declaration blocks the plan.

- [ ] **Step 6: Commit; stop for live-install approval**

```bash
git add adapters/claude/owned-paths.json adapters/claude/bin lib/kingstack/install.py lib/kingstack/rollback.py lib/kingstack/cli.py tests/test_install_claude.py
git commit -m "feat: install Claude adapter through compatibility wrappers"
```

### Task 3: Install, prove, roll back, and reinstall both Claude profiles

**Files:**

- Create: `docs/migration/claude-live-verification.md`

- [ ] **Step 1: Snapshot immediately before the live write**

```bash
ks_snapshot_id=$(./scripts/kingstack snapshot --label pre-claude-adapter --print-id)
test -n "${ks_snapshot_id:?}"
./scripts/kingstack install --claude --all-profiles --apply --snapshot-id "$ks_snapshot_id"
```

- [ ] **Step 2: Start fresh sessions in work and personal profiles**

For each profile prove: global instructions; pstack default process layer;
king-mode personal layer; shared project memory index; model/effort visibility;
bulk warning; PreCompact checkpoint; Stop candidate capture; all baseline skill
names; current commands; and profile-specific auth still works. Use harmless
fixtures, not production repos or databases.

- [ ] **Step 3: Prove the three real launchd jobs from their installed definitions**

Kickstart each job with launchctl, verify its exact installed argv resolves the
neutral checkout, validate output/ledger changes, and confirm duplicate-run
prevention. Do not rely on running scripts directly.

- [ ] **Step 4: Exercise live rollback**

Apply rollback using the Claude install manifest. Compare every restored hash,
symlink target, mode, schedule definition, and profile health with the snapshot.
Start both profiles and run the old `claude-check` to prove the previous setup
still operates.

- [ ] **Step 5: Reinstall and rerun the smoke suite**

Reapply from the same staged source after rechecking hashes. Repeat fresh start,
memory index, one representative skill, one subagent visibility event, and
`kingstack check --adapter claude` for both profiles.

- [ ] **Step 6: Record exact evidence and commit**

```bash
git add docs/migration/claude-live-verification.md
git commit -m "test: prove Claude parity and live rollback"
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

### Task 5: Run the cross-agent behavioral acceptance matrix

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

### Task 6: Switch operational references to the neutral checkout

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
Record its HEAD, origin, bundle/snapshot ID, and why `.git` remains. Do not move
or delete `.git`, tracked files, or original memory. Add a health warning if new
kingstack commits are made there after cutover.

- [ ] **Step 4: Commit**

```bash
git add README.md core/instructions/70-stack-iteration.md core/schedules/schedules.json docs/migration/legacy-claude-checkout.md
git commit -m "docs: make neutral kingstack the canonical control plane"
```

### Task 7: Final no-loss audit, review, and push gate

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
Rollback snapshots == verified and restorable
```

- [ ] **Step 2: Scan the public repository for forbidden state**

Scan tracked files for credential prefixes, private-key blocks, assignment-
shaped secrets, raw memory bodies, transcript extensions, ledgers, absolute
private runtime paths, caches, backups, and generated adapters. Review every
match; variable names alone are not secrets.

- [ ] **Step 3: Run final verification from a fresh shell**

```bash
cd "$HOME/Desktop/Work/kingstack"
PYTHONPATH=lib python3 -m unittest discover -s tests -v
./scripts/kingstack check --all
git fsck --full
git status --short --branch
git log --oneline --decorate -20
```

- [ ] **Step 4: Have Hassan review the complete diff and reports**

Present before/after architecture, every intentional transform, rollback IDs,
behavior matrix, remaining exceptions, and exact commits pending push. Do not
push on a generic earlier approval; this is the explicit final migration gate.

- [ ] **Step 5: Push only after approval and verify remote equality**

```bash
git push origin main
git fetch origin main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
./scripts/kingstack check --all
```

- [ ] **Step 6: Keep rollback material**

Report the dated private snapshots and legacy checkout location. Ask separately
in a future session before deleting any of them. Completion means the new system
works and the old system remains recoverable—not that old data has been erased.
