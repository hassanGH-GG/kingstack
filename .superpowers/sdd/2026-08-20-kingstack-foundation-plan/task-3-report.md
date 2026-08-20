# Task 3 report: immutable capture-only archives

## Implementation

Replaced the experimental snapshot/restore engine with `kingstack.archive`.
Archives take deterministic pre- and post-copy source inventories containing
path, kind, SHA-256, source mode, symlink target, and device/inode identity.
The capture aborts and removes its private temporary sibling if those
inventories differ. Regular payload files are copied sequentially through
no-follow, descriptor-relative file descriptors; symlinks are recreated without
dereferencing, every archive directory is
`0700`, and payload modes are capped to owner-only bits. A no-replace platform
rename is the only publication operation. `auth.json`, `.claude.json`,
`credentials`, `keychain`, `sessions`, `.jsonl`, `.transcript`, and
`.transcript.json` are rejected in every selected subtree.

The CLI now supports only `archive create --label LABEL --print-id` and
`archive verify IDENTIFIER --check-permissions`; no snapshot, restore, or
apply route remains.

## TDD evidence

### RED

Command:

```sh
PYTHONPATH=lib python3 -m unittest tests.test_archive -v
```

Relevant output before implementation:

```text
ERROR: test_capture_preserves_selected_bytes_relative_links_and_private_modes
ModuleNotFoundError: No module named 'kingstack.archive'

ERROR: test_archive_cli_has_no_apply_or_restore_command
ImportError: cannot import name 'archive_cli_subcommands' from 'kingstack.cli'

Ran 5 tests in 0.036s
FAILED (errors=5)
```

The failures were expected because `kingstack.archive` and the archive CLI did
not yet exist.

During live verification, a broad-umask capture exposed a second concrete
case: intermediate directories made by `mkdir(parents=True)` could retain
`0755`. The regression test was added first and failed as expected:

```sh
PYTHONPATH=lib python3 -m unittest tests.test_archive.ArchiveTest.test_capture_makes_every_intermediate_directory_private_under_a_broad_umask -v
```

```text
ValueError: created archive failed verification: directory permission mismatch: claude/projects; directory permission mismatch: claude/projects/demo
FAILED (errors=1)
```

### GREEN

Focused command:

```sh
PYTHONPATH=lib python3 -m unittest tests.test_archive -v
```

Output:

```text
Ran 6 tests in 0.087s
OK
```

Final suite command:

```sh
PYTHONPATH=lib python3 -m unittest tests.test_archive tests.test_inventory tests.test_paths -v
```

Output:

```text
Ran 14 tests in 0.487s
OK
```

Descriptor-bound command (64 nested selected files under `ulimit -n 16`, with
an archive creation and permission verification in a `TemporaryDirectory`):

```sh
ulimit -n 16
PYTHONPATH=lib python3 - <<'PY'
# creates 64 nested selected files, then create_archive(...)
# and assert verify_archive(..., check_permissions=True) == []
PY
```

Output:

```text
fd-bound-ok
```

This demonstrates capture does not retain a descriptor per source directory.

## Required live capture and verification

After the tests were green, exactly one archive was published:

```sh
ks_archive_id=$(./scripts/kingstack archive create --label pre-neutral-migration --print-id)
test -n "${ks_archive_id:?}"
./scripts/kingstack archive verify "$ks_archive_id" --check-permissions
! ./scripts/kingstack archive apply "$ks_archive_id"
```

Output:

```text
verified archive-20260820-121406
kingstack archive: error: argument archive_action: invalid choice: 'apply' (choose from 'create', 'verify')
```

Archive ID: `archive-20260820-121406` at
`/Users/mac/.kingstack/archives/archive-20260820-121406`.

An initial attempted live capture did not publish an archive: its own private
verification detected broad-umask intermediate directories and removed the
temporary sibling. The regression above fixed that root cause before the sole
successful publication.

## Existing private snapshot preservation

Before capture, and again after capture, the following eight directories were
present unchanged under `/Users/mac/.kingstack/snapshots`:

```text
snapshot-20260820-092749
snapshot-20260820-092901
snapshot-20260820-093002
snapshot-20260820-093104
snapshot-20260820-094710
snapshot-20260820-101106
snapshot-20260820-105637
snapshot-20260820-113207
```

Afterward, `/Users/mac/.kingstack/archives` contains only
`archive-20260820-121406`.

## Files changed

- Deleted `lib/kingstack/snapshot.py`
- Deleted `tests/test_snapshot.py`
- Added `lib/kingstack/archive.py`
- Added `tests/test_archive.py`
- Modified `lib/kingstack/cli.py`

## Self-review

- Confirmed there are no `kingstack.snapshot` imports or CLI restore/apply
  paths.
- Confirmed source mutation, denylist, collision, symlink, byte, permission,
  and parser behavior are tested against real filesystem behavior.
- Confirmed `git diff --check` is clean.
- Confirmed only constant-scope file operations are used; no directory
  descriptor cache is retained.

## Concerns

None. The archive is intentionally capture-only; it supplies no restore or
apply API.

## Fix Round 1

### Findings addressed

1. A raced source replacement can no longer cause a destination `chmod` to
   follow a symlink. Regular files are opened from no-follow directory
   descriptors, checked with `fstat` against the pre-inventory identity, and
   copied to a no-follow `O_EXCL` destination descriptor that is mode-set with
   `fchmod`.
2. The component denylist now rejects `auth`, `session`, `sessions`,
   `transcript`, and `transcripts`, plus every `credentials*` and `keychain*`
   stem, at every selected depth.
3. `verify_archive` now returns `invalid archive manifest` for a valid JSON
   value that is not an object.

### Focused RED evidence

First focused command (before the production fixes):

```sh
PYTHONPATH=lib python3 -m unittest tests.test_archive.ArchiveTest.test_source_swap_to_symlink_never_changes_its_target tests.test_archive.ArchiveTest.test_nested_sensitive_component_variants_are_rejected tests.test_archive.ArchiveTest.test_verify_reports_a_non_object_manifest -v
```

Exact output:

```text
test_source_swap_to_symlink_never_changes_its_target (tests.test_archive.ArchiveTest)
Following a raced source link and chmodding its target must fail this test. ... FAIL
test_nested_sensitive_component_variants_are_rejected (tests.test_archive.ArchiveTest)
Missing a sensitive component or prefix variant must fail this test. ... test_verify_reports_a_non_object_manifest (tests.test_archive.ArchiveTest)
Calling dict methods on a JSON array must fail this test. ... ERROR

======================================================================
ERROR: test_verify_reports_a_non_object_manifest (tests.test_archive.ArchiveTest)
Calling dict methods on a JSON array must fail this test.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_archive.py", line 130, in test_verify_reports_a_non_object_manifest
    self.assertEqual(verify_archive(archive), ["invalid archive manifest"])
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/archive.py", line 128, in verify_archive
    if manifest.get("version") != ARCHIVE_VERSION or not isinstance(records, list):
AttributeError: 'list' object has no attribute 'get'

======================================================================
FAIL: test_source_swap_to_symlink_never_changes_its_target (tests.test_archive.ArchiveTest)
Following a raced source link and chmodding its target must fail this test.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_archive.py", line 100, in test_source_swap_to_symlink_never_changes_its_target
    create_archive(Paths.for_home(self.home), self.archive_root, "raced-link")
AssertionError: SourceChanged not raised

======================================================================
FAIL: test_nested_sensitive_component_variants_are_rejected (tests.test_archive.ArchiveTest) (variant='auth')
Missing a sensitive component or prefix variant must fail this test.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_archive.py", line 119, in test_nested_sensitive_component_variants_are_rejected
    create_archive(Paths.for_home(home), self.tempdir / ("archives-" + variant), "unsafe")
AssertionError: ValueError not raised

======================================================================
FAIL: test_nested_sensitive_component_variants_are_rejected (tests.test_archive.ArchiveTest) (variant='session')
Missing a sensitive component or prefix variant must fail this test.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_archive.py", line 119, in test_nested_sensitive_component_variants_are_rejected
    create_archive(Paths.for_home(home), self.tempdir / ("archives-" + variant), "unsafe")
AssertionError: ValueError not raised

======================================================================
FAIL: test_nested_sensitive_component_variants_are_rejected (tests.test_archive.ArchiveTest) (variant='transcript')
Missing a sensitive component or prefix variant must fail this test.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_archive.py", line 119, in test_nested_sensitive_component_variants_are_rejected
    create_archive(Paths.for_home(home), self.tempdir / ("archives-" + variant), "unsafe")
AssertionError: ValueError not raised

======================================================================
FAIL: test_nested_sensitive_component_variants_are_rejected (tests.test_archive.ArchiveTest) (variant='transcripts')
Missing a sensitive component or prefix variant must fail this test.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_archive.py", line 119, in test_nested_sensitive_component_variants_are_rejected
    create_archive(Paths.for_home(home), self.tempdir / ("archives-" + variant), "unsafe")
AssertionError: ValueError not raised

======================================================================
FAIL: test_nested_sensitive_component_variants_are_rejected (tests.test_archive.ArchiveTest) (variant='credentials-backup')
Missing a sensitive component or prefix variant must fail this test.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_archive.py", line 119, in test_nested_sensitive_component_variants_are_rejected
    create_archive(Paths.for_home(home), self.tempdir / ("archives-" + variant), "unsafe")
AssertionError: ValueError not raised

======================================================================
FAIL: test_nested_sensitive_component_variants_are_rejected (tests.test_archive.ArchiveTest) (variant='keychain-store')
Missing a sensitive component or prefix variant must fail this test.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_archive.py", line 119, in test_nested_sensitive_component_variants_are_rejected
    create_archive(Paths.for_home(home), self.tempdir / ("archives-" + variant), "unsafe")
AssertionError: ValueError not raised

----------------------------------------------------------------------
Ran 3 tests in 0.430s

FAILED (failures=7, errors=1)
```

The race test's initial path comparison used a non-canonical macOS temporary
path, so it did not inject the swap. After correcting that test setup (still
before production code changed), the intended race failure was reproduced with
this command:

```sh
PYTHONPATH=lib python3 -m unittest tests.test_archive.ArchiveTest.test_source_swap_to_symlink_never_changes_its_target -v
```

Exact output:

```text
test_source_swap_to_symlink_never_changes_its_target (tests.test_archive.ArchiveTest)
Following a raced source link and chmodding its target must fail this test. ... FAIL

======================================================================
FAIL: test_source_swap_to_symlink_never_changes_its_target (tests.test_archive.ArchiveTest)
Following a raced source link and chmodding its target must fail this test.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_archive.py", line 103, in test_source_swap_to_symlink_never_changes_its_target
    self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o640)
AssertionError: 384 != 416

----------------------------------------------------------------------
Ran 1 test in 0.043s

FAILED (failures=1)
```

### Focused GREEN evidence

Command:

```sh
PYTHONPATH=lib python3 -m py_compile lib/kingstack/archive.py && PYTHONPATH=lib python3 -m unittest tests.test_archive.ArchiveTest.test_source_swap_to_symlink_never_changes_its_target tests.test_archive.ArchiveTest.test_nested_sensitive_component_variants_are_rejected tests.test_archive.ArchiveTest.test_verify_reports_a_non_object_manifest -v
```

Exact output:

```text
test_source_swap_to_symlink_never_changes_its_target (tests.test_archive.ArchiveTest)
Following a raced source link and chmodding its target must fail this test. ... ok
test_nested_sensitive_component_variants_are_rejected (tests.test_archive.ArchiveTest)
Missing a sensitive component or prefix variant must fail this test. ... ok
test_verify_reports_a_non_object_manifest (tests.test_archive.ArchiveTest)
Calling dict methods on a JSON array must fail this test. ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.106s

OK
```

### Full explicit suite

Command:

```sh
git diff --check && PYTHONPATH=lib python3 -m unittest tests.test_archive tests.test_inventory tests.test_paths -v
```

Exact output:

```text
test_archive_cli_has_no_apply_or_restore_command (tests.test_archive.ArchiveTest)
Adding a mutating archive subcommand must fail this test. ... ok
test_capture_makes_every_intermediate_directory_private_under_a_broad_umask (tests.test_archive.ArchiveTest)
Leaving an intermediate directory group-readable must fail this test. ... ok
test_capture_preserves_selected_bytes_relative_links_and_private_modes (tests.test_archive.ArchiveTest)
Changing copied bytes, link text, or private mode must fail this test. ... ok
test_denied_auth_path_is_rejected (tests.test_archive.ArchiveTest)
Allowing auth material into an archive must fail this test. ... ok
test_existing_archive_id_is_never_replaced (tests.test_archive.ArchiveTest)
Replacing a matching timestamp directory must fail this test. ... ok
test_nested_sensitive_component_variants_are_rejected (tests.test_archive.ArchiveTest)
Missing a sensitive component or prefix variant must fail this test. ... ok
test_source_change_aborts_without_publication (tests.test_archive.ArchiveTest)
Publishing an archive after its source changes must fail this test. ... ok
test_source_swap_to_symlink_never_changes_its_target (tests.test_archive.ArchiveTest)
Following a raced source link and chmodding its target must fail this test. ... ok
test_verify_reports_a_non_object_manifest (tests.test_archive.ArchiveTest)
Calling dict methods on a JSON array must fail this test. ... ok
test_capture_excludes_sensitive_paths_at_every_depth (tests.test_inventory.InventoryTest)
Hashing a secret in an included directory would publish its fingerprint. ... ok
test_capture_is_deterministic_and_redacts_config_values (tests.test_inventory.InventoryTest)
Changing a config scalar must never expose it in the public report. ... ok
test_capture_records_symlink_mode_and_file_hash (tests.test_inventory.InventoryTest)
Dereferencing a symlink or losing its executable mode corrupts a baseline. ... ok
test_capture_redacts_absolute_symlink_targets (tests.test_inventory.InventoryTest)
An absolute symlink target would disclose a home path in the report. ... ok
test_capture_redacts_path_shaped_json_key_names (tests.test_inventory.InventoryTest)
A path-shaped JSON key must not reveal a home path as report metadata. ... ok
test_cli_writes_fixture_inventory_and_rejects_agent_home_output (tests.test_inventory.InventoryTest)
A CLI regression must not write a report under a protected agent home. ... ok
test_write_public_report_is_byte_deterministic_and_rejects_private_destinations (tests.test_inventory.InventoryTest)
A public report must be repeatable and never land in agent-private storage. ... ok
test_defaults_are_agent_neutral_and_runtime_is_outside_repo (tests.test_paths.PathsTest) ... ok

----------------------------------------------------------------------
Ran 17 tests in 1.224s

OK
```

### Constant-bounded descriptor evidence

Before this test, the exact private directory inventory was:

```sh
find /Users/mac/.kingstack/snapshots -mindepth 1 -maxdepth 1 -type d -name 'snapshot-*' -exec basename {} \; | sort
find /Users/mac/.kingstack/archives -mindepth 1 -maxdepth 1 -type d -name 'archive-*' -exec basename {} \; | sort
```

```text
snapshot-20260820-092749
snapshot-20260820-092901
snapshot-20260820-093002
snapshot-20260820-093104
snapshot-20260820-094710
snapshot-20260820-101106
snapshot-20260820-105637
snapshot-20260820-113207
archive-20260820-121406
```

Executed command:

```sh
ulimit -n 16
PYTHONPATH=lib python3 - <<'PY'
import tempfile
from pathlib import Path
from kingstack.archive import create_archive, verify_archive
from kingstack.paths import Paths

with tempfile.TemporaryDirectory() as temporary:
    home = Path(temporary) / "home"
    (home / ".claude" / "settings.json").parent.mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
    for number in range(320):
        entry = home / ".claude" / "skills" / ("dir-" + str(number)) / "entry.md"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("entry " + str(number) + "\n", encoding="utf-8")
    (home / ".codex").mkdir()
    (home / ".codex" / "config.toml").write_text("model = 'test'\n", encoding="utf-8")
    archive = create_archive(Paths.for_home(home), Path(temporary) / "archives", "fd-bound-320")
    assert verify_archive(archive, check_permissions=True) == []
    print("fd-bound-320-ok")
PY
```

Exact output:

```text
fd-bound-320-ok
```

### Live archive command, verification, and preservation proof

Command:

```sh
ks_archive_id=$(./scripts/kingstack archive create --label fix-round-1-evidence --print-id) && test -n "${ks_archive_id:?}" && ./scripts/kingstack archive verify "$ks_archive_id" --check-permissions && ! ./scripts/kingstack archive apply "$ks_archive_id" && printf 'created=%s\n' "$ks_archive_id" && printf 'snapshots-after\n' && find /Users/mac/.kingstack/snapshots -mindepth 1 -maxdepth 1 -type d -name 'snapshot-*' -exec basename {} \; | sort && printf 'archives-after\n' && find /Users/mac/.kingstack/archives -mindepth 1 -maxdepth 1 -type d -name 'archive-*' -exec basename {} \; | sort
```

Exact output:

```text
verified archive-20260820-122621
usage: kingstack archive [-h] {create,verify} ...
kingstack archive: error: argument archive_action: invalid choice: 'apply' (choose from 'create', 'verify')
created=archive-20260820-122621
snapshots-after
snapshot-20260820-092749
snapshot-20260820-092901
snapshot-20260820-093002
snapshot-20260820-093104
snapshot-20260820-094710
snapshot-20260820-101106
snapshot-20260820-105637
snapshot-20260820-113207
archives-after
archive-20260820-121406
archive-20260820-122621
```

No live `~/.claude` or `~/.codex` path was modified. The before and after
snapshot ID lists are identical; both pre-existing and Fix Round 1 archive IDs
remain intact.
