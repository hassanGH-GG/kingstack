# Task 3 report: immutable capture-only archives

## Implementation

Replaced the experimental snapshot/restore engine with `kingstack.archive`.
Archives take deterministic pre- and post-copy source inventories containing
path, kind, SHA-256, source mode, symlink target, and device/inode identity.
The capture aborts and removes its private temporary sibling if those
inventories differ. Payload files are copied sequentially with `shutil.copy2`,
symlinks are recreated without dereferencing, every archive directory is
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
- Confirmed only constant-scope file operations (`copy2` and hash contexts) are
  used; no directory descriptor cache is retained.

## Concerns

None. The archive is intentionally capture-only; it supplies no restore or
apply API.
