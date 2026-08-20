# Kingstack Foundation and Lossless Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the neutral kingstack checkout, private runtime skeleton, and reproducible baseline/rollback snapshots without changing either live agent profile.

**Architecture:** A dependency-free Python CLI captures typed inventories and private backups, redacts the report safe for Git, and clones the current repository with its history and real origin. All writes target only the new checkout and `~/.kingstack`; `~/.claude` and `~/.codex` are read-only inputs in this phase.

**Tech Stack:** Python 3 standard library, Git, POSIX shell, JSON, SHA-256.

**Spec:** `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md`

## Global Constraints

- Run from the current clean `~/.claude` repository; abort if tracked changes or unpushed commits exist unless `--allow-unpushed` is explicitly used for the initial local clone.
- Do not read or copy `~/.claude.json`, `~/.codex/auth.json`, keychains, browser state, or credential stores.
- Full configuration backups are private mode `0600`; tracked reports contain hashes and key names, never values.
- The new checkout must retain the Git object history, branch, tags, and original remote URL.
- No symlink under an agent home is created in this phase.

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
`python3 -m kingstack.cli "$@"`. Add all runtime and staging names to the
allowlist `.gitignore`: `.staging/`, `*.private.json`, `*.snapshot.tar`, and
`runtime/`.

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

### Task 3: Build private snapshot and restoration manifests

**Files:**

- Create: `lib/kingstack/snapshot.py`
- Create: `tests/test_snapshot.py`
- Modify: `lib/kingstack/cli.py`

- [ ] **Step 1: Write failing round-trip and refusal tests**

Use a temporary fake home. Snapshot selected Claude/Codex files, mutate them,
restore into a separate destination, and assert byte content, symlink targets,
and modes match. Add tests that snapshot refuses auth paths and that restore
refuses to overwrite an unknown live file.

- [ ] **Step 2: Run the tests and confirm failure**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_snapshot -v`

- [ ] **Step 3: Implement the private snapshot format**

The module exposes `create_snapshot(paths, destination, label)`,
`verify_snapshot(snapshot_dir)`, and
`restore_snapshot(snapshot_dir, destination_home, dry_run=True)`. Return paths
and lists using Python 3.9-compatible annotations from `typing`.

Layout:

```text
snapshot-YYYYMMDD-HHMMSS/
  manifest.json       # relative path, hash, mode, kind, target
  files/claude/...
  files/codex/...
```

Create directories with `0700`, files with their original mode capped so group
and other permissions are removed. Copy with `shutil.copy2`; recreate symlinks
without following them. Use a hard denylist for `auth.json`, `.claude.json`,
`credentials`, `keychain`, `sessions`, and transcript extensions. Restore is
dry-run by default and requires `--apply --expected-current-hash` for a live
destination. The CLI supports `snapshot --label LABEL --print-id`; its returned
identifier is then passed to `snapshot verify IDENTIFIER --check-permissions`,
so later phases never guess an identifier.

- [ ] **Step 4: Prove round-trip and permissions**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_snapshot -v
ks_snapshot_id=$(./scripts/kingstack snapshot --label pre-neutral-migration --print-id)
test -n "${ks_snapshot_id:?}"
./scripts/kingstack snapshot verify "$ks_snapshot_id" --check-permissions
```

Expected: tests pass and both `find` commands print nothing.

- [ ] **Step 5: Commit**

```bash
git add lib/kingstack/snapshot.py lib/kingstack/cli.py tests/test_snapshot.py
git commit -m "feat: add private lossless configuration snapshots"
```

### Task 4: Create the neutral checkout without changing live ownership

**Files:**

- Create: `lib/kingstack/bootstrap.py`
- Create: `tests/test_bootstrap.py`
- Modify: `lib/kingstack/cli.py`
- Create: `core/.gitkeep`
- Create: `adapters/claude/.gitkeep`
- Create: `adapters/codex/.gitkeep`

- [ ] **Step 1: Write failing tests for dirty-state refusal and Git preservation**

Create a temporary source Git repo with a tag, branch, and fake origin. Assert:

```python
self.assertRaises(BootstrapError, bootstrap, dirty_source, destination)
self.assertEqual(run_git(dest, "rev-parse", "HEAD"), run_git(src, "rev-parse", "HEAD"))
self.assertEqual(run_git(dest, "remote", "get-url", "origin"), original_origin)
self.assertIn("v-test", run_git(dest, "tag"))
```

- [ ] **Step 2: Run and confirm failure**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_bootstrap -v`

- [ ] **Step 3: Implement clone-safe bootstrap**

The module exposes
`bootstrap(source, destination, runtime, allow_unpushed=False)` and returns the
same dictionary written to the private bootstrap manifest.

Algorithm: verify destination absent; verify source worktree clean; record HEAD,
branch, tags, origin, and upstream divergence; run `git clone --no-hardlinks`;
restore the recorded origin because a local clone otherwise points at the source
path; fetch tags; compare HEAD and `git fsck`; create `~/.kingstack` directories
with `0700`; write the baseline into the private manifest directory; create a
tracked redacted `docs/baselines/claude-codex-baseline.json` only after checking
it contains no home path or secret value.

- [ ] **Step 4: Run the bootstrap tests**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_bootstrap -v`

- [ ] **Step 5: Run the real dry-run**

```bash
./scripts/kingstack bootstrap --source "$HOME/.claude" --dry-run
```

Expected: it names the target checkout, snapshot path, HEAD, origin, and every
would-write path; it reports zero writes.

- [ ] **Step 6: Apply locally and prove the old setup is untouched**

Capture hashes of `~/.claude/CLAUDE.md`, `settings.json`, memory indexes, and
`~/.codex/config.toml`; run:

```bash
./scripts/kingstack bootstrap --source "$HOME/.claude" --allow-unpushed
```

Then compare the captured hashes, run `git fsck` in both repos, compare HEAD,
tags, and origin, and run the current `~/.claude/scripts/check-setup.sh`.

Expected: old hashes unchanged, both Git checks clean, neutral checkout at the
same HEAD, current setup still `SETUP HEALTHY`.

- [ ] **Step 7: Commit in the neutral checkout**

```bash
cd "$HOME/Desktop/Work/kingstack"
git add core adapters docs/baselines lib/kingstack/bootstrap.py lib/kingstack/cli.py tests/test_bootstrap.py
git commit -m "feat: bootstrap neutral kingstack without live mutation"
```

### Task 5: Foundation phase acceptance gate

**Files:**

- Create: `docs/migration/foundation-verification.md`

- [ ] **Step 1: Run the complete foundation suite**

```bash
cd "$HOME/Desktop/Work/kingstack"
PYTHONPATH=lib python3 -m unittest discover -s tests -v
./scripts/kingstack inventory --output "$(mktemp -d)/baseline.json"
./scripts/kingstack snapshot --label foundation-acceptance --print-id
git fsck --full
git status --short
"$HOME/.claude/scripts/check-setup.sh"
```

- [ ] **Step 2: Record exact before/after evidence**

The verification document records: old and new HEAD, origin, tag count, public
inventory counts, private snapshot ID, unchanged live hashes, permission checks,
and the Claude health output. It explicitly states that no live path changed.

- [ ] **Step 3: Commit; do not push yet**

```bash
git add docs/migration/foundation-verification.md
git commit -m "test: verify neutral foundation without data loss"
```

- [ ] **Step 4: Stop for Hassan's phase review**

Do not begin the portable-core plan until Hassan approves the evidence and the
working tree is clean.
