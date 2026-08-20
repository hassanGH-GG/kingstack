# Kingstack Foundation and Lossless Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the neutral kingstack checkout, private runtime skeleton, deterministic inventories, and immutable capture-only configuration archives without changing either live agent profile.

**Architecture:** A dependency-free Python CLI captures typed inventories and immutable private archives, redacts the report safe for Git, and clones the current repository with its history and real origin. Archives have no apply operation: normal rollback later uses dated originals of manifest-owned paths, while disaster recovery materializes beside a live home. All writes target only the isolated worktree, the new checkout, and `~/.kingstack`; `~/.claude` and `~/.codex` are read-only inputs in this phase.

**Tech Stack:** Python 3 standard library, Git, POSIX shell, JSON, SHA-256.

**Spec:** `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md`

## Global Constraints

- Run from the isolated feature worktree and require its tracked state clean at each acceptance gate. Treat live `~/.claude` as the read-only baseline; `--allow-unpushed` is permitted only for the initial local clone after exact HEAD/origin evidence is recorded.
- Do not read or copy `~/.claude.json`, `~/.codex/auth.json`, keychains, browser state, or credential stores.
- Full configuration backups are private mode `0600`; tracked reports contain hashes and key names, never values.
- The new checkout must retain the Git object history, branch, tags, and original remote URL.
- No symlink under an agent home is created in this phase.
- Delete the experimental in-place restore implementation before foundation acceptance; preserve its private snapshot directories but expose no production `snapshot apply` or `restore_snapshot` interface.

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

### Task 3: Replace experimental restore with immutable capture-only archives

**Files:**

- Delete: `lib/kingstack/snapshot.py`
- Delete: `tests/test_snapshot.py`
- Create: `lib/kingstack/archive.py`
- Create: `tests/test_archive.py`
- Modify: `lib/kingstack/cli.py`

- [ ] **Step 1: Write failing capture, verification, and non-restoration tests**

Use a temporary fake home and archive root. Assert a normal capture preserves
selected bytes, relative symlink targets, and owner permissions; a denied auth
path is rejected; a source mutation injected between pre- and post-inventory
rejects and publishes nothing; an existing archive ID is never replaced; and
the CLI parser has no archive apply/restore command.

```python
class ArchiveTest(TestCase):
    def test_source_change_aborts_without_publication(self):
        with self.assertRaises(SourceChanged):
            create_archive(paths, root, "race", after_copy=mutate_source)
        self.assertEqual(list(root.glob("archive-*")), [])

    def test_archive_api_is_capture_only(self):
        self.assertFalse(hasattr(archive, "restore_snapshot"))
        self.assertNotIn("apply", archive_cli_subcommands())
```

- [ ] **Step 2: Run the tests and confirm failure**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_archive -v`

Expected: import failure because `kingstack.archive` does not exist.

- [ ] **Step 3: Remove the experimental engine and implement capture-only archives**

Delete the experimental snapshot module and its transaction tests. Do not delete
any directory under `~/.kingstack/backups`; those are private evidence.

The replacement exposes only:

```python
def create_archive(paths: Paths, destination: Path, label: str,
                   after_copy: Optional[Callable[[], None]] = None) -> Path: ...
def verify_archive(archive_dir: Path, check_permissions: bool = False) -> List[str]: ...
```

Use Python 3.9-compatible annotations from `typing`. Capture a deterministic
pre-inventory, copy only allowlisted authored configuration into a private
temporary sibling, capture a post-inventory, and reject if source identities or
hashes differ. Verify copied bytes and modes against the manifest before one
exclusive rename publishes the archive. Never keep one descriptor per copied
directory; bound simultaneous file descriptors to a constant number.

Layout:

```text
archive-YYYYMMDD-HHMMSS/
  manifest.json       # version, source inventories, path/hash/mode/kind/target
  files/claude/...
  files/codex/...
```

Create directories with `0700`, files with their original mode capped so group
and other permissions are removed. Copy with `shutil.copy2`; recreate symlinks
without following them. Use a hard denylist for `auth.json`, `.claude.json`,
`credentials`, `keychain`, `sessions`, and transcript extensions. The CLI
supports only `archive create --label LABEL --print-id` and
`archive verify IDENTIFIER --check-permissions`. It contains no restore or apply
path.

- [ ] **Step 4: Prove capture, source-change rejection, descriptor bounds, and permissions**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_archive -v
ks_archive_id=$(./scripts/kingstack archive create --label pre-neutral-migration --print-id)
test -n "${ks_archive_id:?}"
./scripts/kingstack archive verify "$ks_archive_id" --check-permissions
! ./scripts/kingstack archive apply "$ks_archive_id"
```

Expected: tests pass, verification prints `verified`, and the unsupported apply
command exits nonzero without changing any live path.

- [ ] **Step 5: Commit**

```bash
git add lib/kingstack/snapshot.py tests/test_snapshot.py lib/kingstack/archive.py tests/test_archive.py lib/kingstack/cli.py
git commit -m "fix: replace in-place restore with immutable archives"
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

Expected: it names the target checkout, archive path, HEAD, origin, and every
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
./scripts/kingstack archive create --label foundation-acceptance --print-id
git fsck --full
git status --short
"$HOME/.claude/scripts/check-setup.sh"
```

- [ ] **Step 2: Record exact before/after evidence**

The verification document records: old and new HEAD, origin, tag count, public
inventory counts, private archive ID, unchanged live hashes, permission checks,
and the Claude health output. It explicitly states that no live path changed.

- [ ] **Step 3: Commit; do not push yet**

```bash
git add docs/migration/foundation-verification.md
git commit -m "test: verify neutral foundation without data loss"
```

- [ ] **Step 4: Record the foundation gate and continue only while live homes remain read-only**

The working tree must be clean and an independent review must approve the
foundation evidence. Continue into the portable-core plan without a live-path
change. The mandatory Hassan stop occurs after cloning, staging, and parity
proof, immediately before the first manifest-owned link.
