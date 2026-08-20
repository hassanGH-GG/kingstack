# Task 3 Report — Private Snapshot and Restoration Manifests

## Status

Implemented and committed private, lossless configuration snapshots in
`e51bad7 feat: add private lossless configuration snapshots`.

The final real private snapshot ID is `snapshot-20260820-093104`.

## TDD evidence

Initial RED command:

```sh
PYTHONPATH=lib python3 -m unittest tests.test_snapshot -v
```

Initial RED output:

```text
FAILED (failures=1, errors=4)
ModuleNotFoundError: No module named 'kingstack.snapshot'
kingstack: error: argument command: invalid choice: 'snapshot'
```

The focused GREEN command was:

```sh
PYTHONPATH=lib python3 -m unittest tests.test_snapshot -v
```

Final focused GREEN output:

```text
Ran 6 tests in 0.345s

OK
```

Three safety regressions were added during self-review. Each was written and
run before its corresponding implementation change:

```sh
PYTHONPATH=lib python3 -m unittest \
  tests.test_snapshot.SnapshotTest.test_snapshot_round_trips_files_symlinks_and_private_modes -v
```

```text
FAIL: private directory permission mismatch: .../files/claude/projects
```

This identified that `mkdir(parents=True)` only chmodded the leaf directory.
The helper now chmods every newly created snapshot ancestor to `0700`.

```sh
PYTHONPATH=lib python3 -m unittest \
  tests.test_snapshot.SnapshotTest.test_snapshot_round_trips_files_symlinks_and_private_modes -v
```

```text
FAIL: 256 != 384
```

This identified that a source `0400` non-executable configuration file was not
normalized to the required `0600`; non-executables now store and restore as
`0600` and owner-executables as `0700`.

```sh
PYTHONPATH=lib python3 -m unittest \
  tests.test_snapshot.SnapshotTest.test_restore_refuses_a_symlinked_destination_parent -v
```

```text
FAIL: ValueError not raised
```

This identified that a destination parent symlink could redirect a restore.
Restore now refuses symlinked or non-directory destination parents before any
write.

Full-suite command and output:

```sh
PYTHONPATH=lib python3 -m unittest \
  tests.test_paths tests.test_inventory tests.test_snapshot -v
git diff --check
```

```text
Ran 14 tests in 0.608s

OK
```

## Live private snapshot proof

After fake-home tests were green, the live Claude/Codex homes were used only as
read-only sources:

```sh
ks_snapshot_id=$(./scripts/kingstack snapshot --label pre-neutral-migration --print-id)
test -n "${ks_snapshot_id:?}"
./scripts/kingstack snapshot verify "$ks_snapshot_id" --check-permissions
```

Final output:

```text
verified snapshot-20260820-093104
snapshot-20260820-093104
```

The snapshot is under `~/.kingstack/snapshots/`; `verify --check-permissions`
is the canonical permission proof. An earlier snapshot made during development
had intermediate directories at `0755`; those directories were immediately
changed to `0700` and independently re-verified before the final snapshot was
created.

## Files

- `lib/kingstack/snapshot.py`: safe selection/denylist, manifest creation,
  hash and permission verification, dry-run restore, preconditioned overwrite,
  and destination-parent symlink refusal.
- `lib/kingstack/cli.py`: `snapshot --label LABEL --print-id`,
  `snapshot verify IDENTIFIER --check-permissions`, and dry-run-by-default
  `snapshot restore` commands.
- `tests/test_snapshot.py`: real fake-home files, executable and non-executable
  modes, source symlinks, denylist refusal, tamper/permission checks, guarded
  overwrite, destination-parent symlink refusal, and CLI ID verification.

## Self-review and concerns

Reviewed the manifest path boundary, denylist before any destination creation,
symlink handling, modes, restore preconditions, and CLI identifier resolution.
No open implementation concerns remain. `python3 -m unittest discover` finds
zero tests because `tests/` is not a package, so the complete current suite was
run explicitly by module as shown above.

## Fix Round 1 — Snapshot confinement and recoverable restore

Commit: pending this report update; Task 3 code/tests only will be committed.

### RED

Focused failing tests were added first, then run with:

```sh
PYTHONPATH=lib python3 -m unittest tests.test_snapshot -v
```

Output:

```text
Ran 13 tests in 0.525s

FAILED (failures=7)
```

The failures covered unchecked CLI apply, restore without a precondition for
missing targets, mode-insensitive expected-state hashing, late Codex failure
after Claude had already been written, ID collision reuse, forged denylisted /
duplicate / extra manifest entries, symlinked storage ancestors, and a string
symlink mode. These failed before the new implementation existed.

### GREEN

Focused command:

```sh
PYTHONPATH=lib python3 -m unittest tests.test_snapshot -v
```

Focused output:

```text
Ran 13 tests in 4.870s

OK
```

Full current suite and formatting command:

```sh
PYTHONPATH=lib python3 -m unittest \
  tests.test_paths tests.test_inventory tests.test_snapshot -v
git diff --check
```

Full output:

```text
Ran 21 tests in 6.577s

OK
```

### Files and behavior

- `lib/kingstack/snapshot.py` now uses v2 manifests with null symlink modes,
  strict direct-child IDs, denylist and duplicate validation, exact expected
  tree validation, canonical permission proof, and no symlinked storage or
  source roots.
- Restore now requires an expected current-state hash for every apply. That
  hash covers targets (kind, bytes/target, mode) and all parent directories
  whose modes a restore will change.
- Restore stages all payloads, fully preflights all namespaces and parents,
  rechecks the precondition before swaps, uses rename-to-private-backup followed
  by atomic replacement, and maintains a private journal/backups for next-run
  recovery or normal rollback. It never unlinks a destination before staging.
- `lib/kingstack/cli.py` validates IDs through the storage resolver and rejects
  `snapshot restore --apply` unless `--expected-current-hash` is supplied.
- `tests/test_snapshot.py` adds real filesystem coverage for traversal IDs,
  symlinked storage, forged manifests, exact modes, positive/new-target apply,
  mode-only state changes, late namespace preflight, and name collisions.

### Snapshot migration proof

The old v1 snapshot `snapshot-20260820-093104` remains untouched. Its current
verification output is `unsupported snapshot manifest`: v2 intentionally
invalidates v1 because v1 claimed portable symlink modes and lacked the strict
tree/manifest invariants required for safe restoration.

Created and verified replacement:

```sh
ks_snapshot_id=$(./scripts/kingstack snapshot --label pre-neutral-migration --print-id)
test -n "${ks_snapshot_id:?}"
./scripts/kingstack snapshot verify "$ks_snapshot_id" --check-permissions
```

```text
verified snapshot-20260820-094710
replacement=snapshot-20260820-094710
```

### Self-review and concerns

Reviewed direct-child containment, tree traversal, denylist checks at source
and manifest boundaries, exact private modes, target/parent state hashing,
preflight order, journal rollback, and the no-unlink swap sequence. No open
implementation concerns. The Darwin `/var` compatibility symlink is explicitly
allowed as a system-owned path before the caller-controlled storage boundary;
all managed storage and snapshot descendants are lstat-checked.

## Fix Round 2 — Canonical manifests and durable recovery

Commit status: committed with this fix-round's Task 3 code, tests, and report.

### Individual RED/GREEN evidence

RED command:

```sh
PYTHONPATH=lib python3 -m unittest \
  tests.test_snapshot.SnapshotTest.test_verify_rejects_noncanonical_manifest_aliases_and_malformed_records \
  tests.test_snapshot.SnapshotTest.test_dry_run_leaves_planted_journals_and_sentinels_unchanged \
  tests.test_snapshot.SnapshotTest.test_apply_refuses_unconfined_journal_without_touching_sentinel -v
```

RED output:

```text
Ran 3 tests in 0.267s

FAILED (failures=2, errors=1)
```

The RED failures showed a canonical `./` alias was accepted, dry-run attempted
journal recovery, and an outside journal target was accepted.

GREEN command:

```sh
PYTHONPATH=lib python3 -m unittest \
  tests.test_snapshot.SnapshotTest.test_verify_rejects_noncanonical_manifest_aliases_and_malformed_records \
  tests.test_snapshot.SnapshotTest.test_dry_run_leaves_planted_journals_and_sentinels_unchanged \
  tests.test_snapshot.SnapshotTest.test_apply_refuses_unconfined_journal_without_touching_sentinel -v
```

GREEN output:

```text
test_verify_rejects_noncanonical_manifest_aliases_and_malformed_records ... ok
test_dry_run_leaves_planted_journals_and_sentinels_unchanged ... ok
test_apply_refuses_unconfined_journal_without_touching_sentinel ... ok

Ran 3 tests in 0.321s

OK
```

Additional focused GREEN command/output:

```sh
PYTHONPATH=lib python3 -m unittest \
  tests.test_snapshot.SnapshotTest.test_apply_recovers_a_valid_interrupted_transaction_before_new_work \
  tests.test_snapshot.SnapshotTest.test_malformed_octal_manifest_mode_is_a_problem_not_an_exception -v
```

```text
test_apply_recovers_a_valid_interrupted_transaction_before_new_work ... ok
test_malformed_octal_manifest_mode_is_a_problem_not_an_exception ... ok

Ran 2 tests in 0.464s

OK
```

Final full GREEN command/output:

```sh
PYTHONPATH=lib python3 -m unittest tests.test_paths tests.test_inventory tests.test_snapshot -v
git diff --check
```

```text
Ran 27 tests in 7.436s

OK
```

### Changes and self-review

`snapshot.py` now rejects raw paths that differ from their canonical
`PurePosixPath` form (including `./`, `..`, empty, absolute, and backslash
aliases). Invalid records and bad octal modes are reported rather than raising.
Dry-run returns plans without inspecting, recovering, deleting, chmodding, or
writing a journal. Apply validates journal destination/snapshot identities,
confined targets and parents, exact state schemas, stage/backup names, and
hashes before recovery. Journal temporary files are exclusive/no-follow,
payload and directory metadata are fsync'd before renames, and source roots /
snapshot children use no-follow directory descriptors and identity rechecks.

Tests use real sentinels and assert their bytes/modes stay unchanged for
malformed and unconfined journals. The pre-existing snapshots remain untouched:
`snapshot-20260820-093104` (legacy v1) and `snapshot-20260820-094710` (v2).
The v2 snapshot still verifies:

```sh
./scripts/kingstack snapshot verify snapshot-20260820-094710 --check-permissions
```

```text
verified snapshot-20260820-094710
```

No open concerns from this round.

## Fix Round 3 — Physical journal confinement

Commit status: committed with this round's Task 3 code, tests, and report.

### Exact RED command and output

```sh
PYTHONPATH=lib python3 -m unittest tests.test_snapshot.SnapshotTest.test_dry_run_with_complete_pending_journal_is_byte_for_byte_read_only tests.test_snapshot.SnapshotTest.test_apply_refuses_symlinked_valid_journal_backup_without_outside_mutation tests.test_snapshot.SnapshotTest.test_verify_reports_control_character_and_bad_type_records -v
```

```text
test_dry_run_with_complete_pending_journal_is_byte_for_byte_read_only (tests.test_snapshot.SnapshotTest)
Even a valid pending transaction is only reported, never recovered by dry-run. ... ok
test_apply_refuses_symlinked_valid_journal_backup_without_outside_mutation (tests.test_snapshot.SnapshotTest)
A syntactically valid journal cannot redirect recovery through a backup symlink. ... ERROR
test_verify_reports_control_character_and_bad_type_records (tests.test_snapshot.SnapshotTest)
Hostile JSON types, NULs, and control characters must never escape verification. ... ok

======================================================================
ERROR: test_apply_refuses_symlinked_valid_journal_backup_without_outside_mutation (tests.test_snapshot.SnapshotTest)
A syntactically valid journal cannot redirect recovery through a backup symlink.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 426, in test_apply_refuses_symlinked_valid_journal_backup_without_outside_mutation
    restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=current_destination_hash(snapshot, destination))
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 134, in restore_snapshot
    _recover_transaction(destination_home)
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 220, in _recover_transaction
    _cleanup_transaction(destination, destination / transaction["stage"], destination / transaction["backup"], journal)
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 246, in _cleanup_transaction
    shutil.rmtree(path)
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/shutil.py", line 728, in rmtree
    onerror(os.path.islink, path, sys.exc_info())
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/shutil.py", line 726, in rmtree
    raise OSError("Cannot call rmtree on a symbolic link")
OSError: Cannot call rmtree on a symbolic link

----------------------------------------------------------------------
Ran 3 tests in 0.326s

FAILED (errors=1)
```

### Exact focused GREEN command and output

```sh
PYTHONPATH=lib python3 -m unittest tests.test_snapshot.SnapshotTest.test_apply_refuses_symlinked_valid_journal_backup_without_outside_mutation tests.test_snapshot.SnapshotTest.test_verify_reports_control_character_and_bad_type_records -v
```

```text
test_apply_refuses_symlinked_valid_journal_backup_without_outside_mutation (tests.test_snapshot.SnapshotTest)
A syntactically valid journal cannot redirect recovery through a backup symlink. ... ok
test_verify_reports_control_character_and_bad_type_records (tests.test_snapshot.SnapshotTest)
Hostile JSON types, NULs, and control characters must never escape verification. ... ok

----------------------------------------------------------------------
Ran 2 tests in 1.173s

OK
```

### Exact full GREEN command and output

```sh
PYTHONPATH=lib python3 -m unittest tests.test_paths tests.test_inventory tests.test_snapshot -v
git diff --check
```

```text
Ran 30 tests in 12.341s

OK
```

Every verbose test status is `ok` in the terminal output immediately above this
report update; no test was skipped. The focused durability/recovery additions
are: canonical aliases and NUL/type records, complete pending-journal dry-run,
physically symlinked backup refusal, malformed unconfined journal refusal,
journal-temp collision rollback, and interrupted recovery.

### Fresh real snapshot

```sh
ks_snapshot_id=$(./scripts/kingstack snapshot --label pre-neutral-migration-round-3 --print-id)
printf '%s\n' "$ks_snapshot_id"
./scripts/kingstack snapshot verify "$ks_snapshot_id" --check-permissions
```

```text
snapshot-20260820-101106
verified snapshot-20260820-101106
```

All old snapshots were preserved: `snapshot-20260820-093104`,
`snapshot-20260820-094710`, and the fresh `snapshot-20260820-101106`.

### Self-review

Journal recovery now opens the trusted destination and stage/backup directories
with mandatory `O_DIRECTORY|O_NOFOLLOW`, validates every journal relative path
and before-state schema before rollback/cleanup, and opens target ancestors
relative to the destination descriptor. Journal temporaries use exclusive,
no-follow descriptor writes and fsync their file plus parent directory.
Staged regular files, staging/backup directories, backup moves, and target
renames are fsynced in order. Source-root creation uses no-follow directory
descriptors and source identity rechecks. No open blocker remains.
