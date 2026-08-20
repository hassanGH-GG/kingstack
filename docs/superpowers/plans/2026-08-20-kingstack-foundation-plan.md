# Kingstack Foundation and Lossless Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the neutral kingstack checkout, private runtime skeleton, and deterministic inventories without copying or changing either live agent profile.

**Architecture:** A dependency-free Python CLI captures typed inventories, redacts a report safe for Git, and clones the current repository with its history and real origin. Kingstack implements no recursive archive or restore path: native homes stay in place, and later rollback uses atomic dated siblings of only manifest-owned paths. All writes target only the isolated worktree, the new checkout, and non-home metadata under `~/.kingstack`; `~/.claude` and `~/.codex` are read-only inputs in this phase.

**Tech Stack:** Python 3 standard library, Git, POSIX shell, JSON, SHA-256.

**Spec:** `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md`

## Global Constraints

- Run from the isolated feature worktree and require its tracked state clean at each acceptance gate. Clone that reviewed worktree HEAD—not legacy `~/.claude`—into the canonical checkout. Treat live `~/.claude` as the read-only behavioral baseline; `--allow-unpushed` is permitted only for this initial local clone after exact source HEAD/origin/divergence evidence is recorded.
- Do not read or copy `~/.claude.json`, `~/.codex/auth.json`, keychains, browser state, or credential stores.
- Private manifests are mode `0600`; tracked reports contain hashes and key names, never values.
- The new checkout must retain the Git object history, branch, tags, and original remote URL.
- No symlink under an agent home is created in this phase.
- Delete both experimental recursive filesystem engines before foundation acceptance. Preserve all private snapshot/archive directories as historical evidence, but expose no production archive, snapshot, apply, verify, or restore interface.

---

### Task 1: Add the package skeleton and canonical path contract

**Files:**

- Create: `lib/kingstack/__init__.py`
- Create: `lib/kingstack/cli.py`
- Create: `lib/kingstack/paths.py`
- Create: `scripts/kingstack`
- Create: `tests/test_paths.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing path-contract test**

```python
from pathlib import Path
from unittest import TestCase
from kingstack.paths import Paths

class PathsTest(TestCase):
    def test_defaults_are_agent_neutral_and_runtime_is_outside_repo(self):
        p = Paths.for_home(Path("/Users/test"))
        self.assertEqual(p.repo, Path("/Users/test/Desktop/Work/kingstack"))
        self.assertEqual(p.runtime, Path("/Users/test/.kingstack"))
        self.assertEqual(p.claude_home, Path("/Users/test/.claude"))
        self.assertEqual(p.codex_home, Path("/Users/test/.codex"))
        self.assertFalse(p.runtime.is_relative_to(p.repo))
```

- [ ] **Step 2: Run it and confirm the missing module failure**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_paths -v`

Expected: `ModuleNotFoundError: No module named 'kingstack.paths'`.

- [ ] **Step 3: Implement the immutable path object and thin CLI launcher**

```python
# lib/kingstack/paths.py
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Paths:
    home: Path
    repo: Path
    runtime: Path
    claude_home: Path
    codex_home: Path

    @classmethod
    def for_home(cls, home: Path) -> "Paths":
        home = home.expanduser().resolve()
        return cls(home, home / "Desktop/Work/kingstack", home / ".kingstack",
                   home / ".claude", home / ".codex")
```

`scripts/kingstack` exports `PYTHONPATH="$SCRIPT_DIR/../lib"` and executes
`python3 -m kingstack.cli "$@"`. Add private runtime names to the allowlist
`.gitignore`: `*.private.json` and `runtime/`. Renderers do not materialize a
mutable staging tree.

- [ ] **Step 4: Run the focused test**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_paths -v`

Expected: one passing test.

- [ ] **Step 5: Commit**

```bash
git add .gitignore lib/kingstack/__init__.py lib/kingstack/cli.py lib/kingstack/paths.py scripts/kingstack tests/test_paths.py
git commit -m "feat: establish agent-neutral kingstack paths"
```

### Task 2: Capture a typed, deterministic baseline inventory

**Files:**

- Create: `lib/kingstack/inventory.py`
- Create: `tests/test_inventory.py`
- Create: `tests/fixtures/inventory-home/.claude/settings.json`
- Create: `tests/fixtures/inventory-home/.codex/config.toml`
- Modify: `lib/kingstack/cli.py`

- [ ] **Step 1: Write failing tests for files, symlinks, modes, redaction, and determinism**

The fixture contains a regular file, executable hook, symlink, a config key
named `token`, and a mock memory bank. Assert the public report contains:

```python
self.assertEqual(a, b)                         # deterministic JSON
self.assertEqual(record["kind"], "symlink")
self.assertEqual(record["target"], "../shared/SKILL.md")
self.assertEqual(record["mode"], "0755")
self.assertNotIn("top-secret-value", json.dumps(report))
self.assertEqual(report["counts"]["memory_banks"], 1)
```

- [ ] **Step 2: Run and observe the missing implementation**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_inventory -v`

Expected: import failure.

- [ ] **Step 3: Implement inventory primitives**

Define these exact interfaces:

The module exposes `FileRecord(path, kind, sha256, mode, target)`,
`hash_file(path)`, `walk_records(root, include)`, `capture_baseline(paths)`, and
`write_public_report(baseline, destination)`. Use `typing.Optional`, `List`, and
`Tuple` so the implementation runs on the installed Python 3.9.6.

The Claude include set is the tracked-file list plus live `settings.json`,
`hooks/`, `scripts/`, `agents/`, `skills/`, `launchd/`, sweep definitions, and
`projects/*/memory/`. The Codex include set is `config.toml`, `AGENTS.md`,
`AGENTS.override.md`, `hooks.json`, `hooks/`, `skills/`, and plugin manifest
names. Ignore auth, sessions, caches, histories, logs, downloads, browser data,
native memory databases, and backups.

The public report stores configuration key paths and whole-file hashes, not
scalar values. Sort every path and JSON key before writing.

- [ ] **Step 4: Add the CLI**

```text
kingstack inventory --output PATH
kingstack inventory --home FIXTURE_HOME --output PATH
```

The command refuses an output path inside `~/.claude`, `~/.codex`, or a memory
bank.

- [ ] **Step 5: Run tests twice and compare output hashes**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_inventory -v
tmp=$(mktemp -d)
./scripts/kingstack inventory --output "$tmp/a.json"
./scripts/kingstack inventory --output "$tmp/b.json"
cmp "$tmp/a.json" "$tmp/b.json"
```

Expected: tests pass and `cmp` exits 0.

- [ ] **Step 6: Commit**

```bash
git add lib/kingstack/inventory.py lib/kingstack/cli.py tests/test_inventory.py tests/fixtures
git commit -m "feat: capture deterministic agent baselines"
```

### Task 3: Remove custom recursive archive and restore engines

**Files:**

- Delete: `lib/kingstack/snapshot.py`
- Delete: `tests/test_snapshot.py`
- Delete: `lib/kingstack/archive.py`
- Delete: `tests/test_archive.py`
- Modify: `lib/kingstack/cli.py`
- Create: `tests/test_cli_surface.py`

- [ ] **Step 1: Write the failing public-surface test**

Add a CLI/package test which inventories command names and importable production
modules. It must fail while either experimental engine remains:

```python
def test_no_recursive_backup_or_restore_surface(self):
    self.assertFalse((ROOT / "lib/kingstack/snapshot.py").exists())
    self.assertFalse((ROOT / "lib/kingstack/archive.py").exists())
    self.assertNotIn("snapshot", cli_command_names())
    self.assertNotIn("archive", cli_command_names())
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_cli_surface -v`

Expected: failure naming the still-present archive module or command.

- [ ] **Step 3: Delete both engines and remove their CLI surface**

Delete the snapshot/archive implementations and their implementation-specific
tests. Remove their parser branches, imports, and handlers from `cli.py`. Do not
delete, rename, chmod, verify, or enumerate contents inside
`~/.kingstack/snapshots` or `~/.kingstack/archives`. Listing only their
top-level directory names before and after is expressly allowed as preservation
evidence.

- [ ] **Step 4: Prove absence and historical preservation**

```bash
before=$(mktemp)
after=$(mktemp)
find "$HOME/.kingstack/snapshots" "$HOME/.kingstack/archives" -mindepth 1 -maxdepth 1 -type d -print 2>/dev/null | sort > "$before"
PYTHONPATH=lib python3 -m unittest tests.test_cli_surface -v
! ./scripts/kingstack archive create --label forbidden --print-id
! ./scripts/kingstack snapshot create --label forbidden
find "$HOME/.kingstack/snapshots" "$HOME/.kingstack/archives" -mindepth 1 -maxdepth 1 -type d -print 2>/dev/null | sort > "$after"
cmp "$before" "$after"
```

Expected: the absence test passes, both commands fail at parsing, and the exact
historical directory list is unchanged.

- [ ] **Step 5: Commit**

```bash
git add lib/kingstack/snapshot.py tests/test_snapshot.py lib/kingstack/archive.py tests/test_archive.py lib/kingstack/cli.py tests/test_cli_surface.py
git commit -m "refactor: remove custom filesystem backup engines"
```

### Task 4: Create the neutral checkout without changing live ownership

**Files:**

- Create: `lib/kingstack/bootstrap.py`
- Create: `tests/test_bootstrap.py`
- Modify: `lib/kingstack/cli.py`
- Create: `core/.gitkeep`
- Create: `adapters/contract/.gitkeep`
- Create: `adapters/claude/.gitkeep`
- Create: `adapters/codex/.gitkeep`
- Create: `adapters/templates/.gitkeep`

- [ ] **Step 1: Write failing tests for dirty-state refusal and Git preservation**

Create a temporary source Git repo with a tag, branch, and fake origin. Assert:

```python
self.assertRaises(BootstrapError, bootstrap, dirty_source, destination,
                  runtime, [claude_home, codex_home])
self.assertEqual(run_git(dest, "rev-parse", "HEAD"), run_git(src, "rev-parse", "HEAD"))
self.assertEqual(run_git(dest, "remote", "get-url", "origin"), original_origin)
self.assertIn("v-test", run_git(dest, "tag"))
```

- [ ] **Step 2: Run and confirm failure**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_bootstrap -v`

- [ ] **Step 3: Implement clone-safe bootstrap**

The module exposes
`bootstrap(source_repo, destination, runtime, baseline_homes,
allow_unpushed=False)` and returns the same dictionary written to the private
bootstrap manifest.

Algorithm: verify destination absent; verify the reviewed feature worktree is
clean; record its HEAD, branch, tags, origin, and upstream divergence; record
but do not use the legacy live repo HEAD as clone source; run
`git clone --no-hardlinks` from the reviewed feature worktree;
restore the recorded origin because a local clone otherwise points at the source
path; fetch tags; compare HEAD and `git fsck`; create `~/.kingstack` directories
with `0700`; write the baseline into the private manifest directory; create a
tracked redacted `docs/baselines/claude-codex-baseline.json` only after checking
it contains no home path or secret value.

- [ ] **Step 4: Run the bootstrap tests**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_bootstrap -v`

- [ ] **Step 5: Commit the bootstrap implementation in the reviewed source worktree**

```bash
git add core adapters lib/kingstack/bootstrap.py lib/kingstack/cli.py tests/test_bootstrap.py
git commit -m "feat: bootstrap neutral kingstack without live mutation"
```

The canonical clone must include this commit. Do not create or commit new source
files only after cloning.

- [ ] **Step 6: Run the real dry-run**

```bash
./scripts/kingstack bootstrap --source-repo "$(git rev-parse --show-toplevel)" --baseline-home "$HOME/.claude" --baseline-home "$HOME/.codex" --allow-unpushed --dry-run
```

Expected: it names the target checkout, HEAD, origin, and every
would-write path; it reports zero writes.

- [ ] **Step 7: Apply locally and prove the old setup is untouched**

Capture hashes of `~/.claude/CLAUDE.md`, `settings.json`, memory indexes, and
`~/.codex/config.toml`; run:

```bash
./scripts/kingstack bootstrap --source-repo "$(git rev-parse --show-toplevel)" --baseline-home "$HOME/.claude" --baseline-home "$HOME/.codex" --allow-unpushed
```

Then compare the captured hashes, run `git fsck` in the source worktree repo,
canonical clone, and legacy live repo; compare the source-worktree and clone
HEAD/tags/origin; record the intentionally different legacy live HEAD; and run
the current `~/.claude/scripts/check-setup.sh`.

Expected: old hashes unchanged, all Git checks clean, neutral checkout at the
same reviewed feature HEAD with the same tags/origin, current setup still
`SETUP HEALTHY`, and the canonical working tree contains only the expected new
redacted baseline report.

### Task 5: Foundation phase acceptance gate

**Files:**

- Create: `docs/migration/foundation-verification.md`
- Create: `docs/baselines/claude-codex-baseline.json`

- [ ] **Step 1: Run the complete foundation suite**

```bash
cd "$HOME/Desktop/Work/kingstack"
PYTHONPATH=lib python3 -m unittest discover -s tests -v
./scripts/kingstack inventory --output "$(mktemp -d)/baseline.json"
git fsck --full
git status --short
"$HOME/.claude/scripts/check-setup.sh"
```

- [ ] **Step 2: Record exact before/after evidence**

The verification document records: old and new HEAD, origin, tag count, public
inventory counts, preserved historical snapshot/archive directory names,
unchanged live hashes, permission checks,
and the Claude health output. It explicitly states that no live path changed.

- [ ] **Step 3: Commit; do not push yet**

```bash
git add docs/migration/foundation-verification.md docs/baselines/claude-codex-baseline.json
git commit -m "test: verify neutral foundation without data loss"
```

- [ ] **Step 4: Record the foundation gate and continue only while live homes remain read-only**

The working tree must be clean and an independent review must approve the
foundation evidence. Continue into the portable-core plan without a live-path
change. The mandatory Hassan stop occurs after cloning, immutable-release preparation, and parity
proof, immediately before the first manifest-owned link.
