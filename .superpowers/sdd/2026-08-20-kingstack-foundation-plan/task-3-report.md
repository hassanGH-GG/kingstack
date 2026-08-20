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

## Fix Round 4 — Initial complete GREEN and live evidence

The final evidence is recorded here before the preserved tail of the prior
round; the exact RED chronology and audit failures continue in the dedicated
Fix Round 4 section below.

### Exact initial complete GREEN command and unabridged output

```sh
PYTHONPATH=lib python3 -m unittest tests.test_paths tests.test_inventory tests.test_snapshot -v
```

```text
test_defaults_are_agent_neutral_and_runtime_is_outside_repo (tests.test_paths.PathsTest) ... ok
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
test_apply_recovers_a_valid_interrupted_transaction_before_new_work (tests.test_snapshot.SnapshotTest)
A prepared journal restores its private backup before the next apply validates state. ... ok
test_apply_refuses_full_journal_with_symlinked_backup_entry (tests.test_snapshot.SnapshotTest)
A backup entry must physically match its recorded before-state before rollback. ... ok
test_apply_refuses_full_journal_with_symlinked_target_ancestor (tests.test_snapshot.SnapshotTest)
A complete journal cannot traverse a target ancestor symlink during recovery. ... ok
test_apply_refuses_journal_temp_symlink_without_outside_mutation (tests.test_snapshot.SnapshotTest)
The exclusive descriptor-relative journal temporary never follows a static symlink. ... ok
test_apply_refuses_symlinked_valid_journal_backup_without_outside_mutation (tests.test_snapshot.SnapshotTest)
A syntactically valid journal cannot redirect recovery through a backup symlink. ... ok
test_apply_refuses_unconfined_journal_without_touching_sentinel (tests.test_snapshot.SnapshotTest)
Malformed recovery metadata cannot name or mutate an outside target. ... ok
test_cleanup_refuses_transaction_directory_created_after_validation (tests.test_snapshot.SnapshotTest)
An absent transaction directory cannot be rebound to attacker data for cleanup. ... ok
test_cli_prints_snapshot_id_and_verifies_it_by_id (tests.test_snapshot.SnapshotTest)
The CLI identifier must resolve to the private snapshot it just created. ... ok
test_cli_rejects_traversal_ids_and_apply_without_expected_hash (tests.test_snapshot.SnapshotTest)
CLI identifiers stay direct children and apply cannot bypass its precondition. ... ok
test_committed_recovery_finishes_after_backup_cleanup_crash (tests.test_snapshot.SnapshotTest)
Committed after-state is sufficient once a durable backup cleanup has happened. ... ok
test_committed_recovery_never_cleans_up_when_restored_content_is_absent (tests.test_snapshot.SnapshotTest)
A committed journal remains recoverable if its claimed target is missing. ... ok
test_creation_refuses_destination_root_rebind_without_writing_replacement (tests.test_snapshot.SnapshotTest)
Snapshot writes remain on the opened destination descriptor after pathname rebind. ... ok
test_creation_refuses_source_root_rebind_without_reading_replacement (tests.test_snapshot.SnapshotTest)
Source reads remain on the opened root descriptor after its pathname is rebound. ... ok
test_dry_run_leaves_planted_journals_and_sentinels_unchanged (tests.test_snapshot.SnapshotTest)
Dry-run is observational even if a recovery journal is present or malformed. ... ok
test_dry_run_with_complete_pending_journal_is_byte_for_byte_read_only (tests.test_snapshot.SnapshotTest)
Even a valid pending transaction is only reported, never recovered by dry-run. ... ok
test_expected_hash_bad_type_raises_controlled_value_error (tests.test_snapshot.SnapshotTest)
An unhashable expected hash is rejected before membership or filesystem mutation. ... ok
test_interruption_after_backup_rename_is_recovered_to_before_state (tests.test_snapshot.SnapshotTest)
A crash after target-to-backup rename leaves a durable prepared rollback. ... ok
test_interruptions_around_committed_journal_recover_correct_side (tests.test_snapshot.SnapshotTest)
Prepared crashes roll back, while durably committed crashes retain restored bytes. ... ok
test_journal_status_mode_and_each_control_path_raise_controlled_value_error (tests.test_snapshot.SnapshotTest)
Malformed journal types and controls never escape as TypeError or OSError. ... ok
test_journal_temp_collision_rolls_back_without_touching_destination (tests.test_snapshot.SnapshotTest)
An exclusive journal-temp failure leaves the pre-apply destination intact. ... ok
test_malformed_octal_manifest_mode_is_a_problem_not_an_exception (tests.test_snapshot.SnapshotTest)
A hostile mode field cannot crash the verifier before reporting invalidity. ... ok
test_manifest_mode_type_and_each_control_path_are_rejected_independently (tests.test_snapshot.SnapshotTest)
Unhashable modes and every C0/C1 control path produce verifier problems. ... ok
test_nested_mutations_use_dir_fds_and_fsync_every_renamed_parent (tests.test_snapshot.SnapshotTest)
Every actual rename is descriptor-relative and synced in both affected parents. ... ok
test_recovery_unlink_stays_anchored_during_post_validation_parent_rebind (tests.test_snapshot.SnapshotTest)
Rebinding a validated target parent cannot redirect the actual rollback unlink. ... ok
test_restore_preflights_late_namespace_before_mutating_early_namespace (tests.test_snapshot.SnapshotTest)
A bad Codex parent must not permit any earlier Claude replacement. ... ok
test_restore_refuses_a_symlinked_destination_parent (tests.test_snapshot.SnapshotTest)
A restore must not follow a destination symlink outside the selected home. ... ok
test_restore_refuses_unknown_live_file_without_current_hash (tests.test_snapshot.SnapshotTest)
An existing destination file must not be overwritten without a precondition. ... ok
test_restore_requires_expected_hash_for_missing_targets_and_hashes_modes (tests.test_snapshot.SnapshotTest)
A creation-only restore still needs a state precondition, including modes. ... ok
test_snapshot_creation_rejects_an_existing_or_symlinked_id_path (tests.test_snapshot.SnapshotTest)
A timing collision must fail instead of reusing or chmodding an existing path. ... ok
test_snapshot_refuses_a_denylisted_source_path (tests.test_snapshot.SnapshotTest)
Copying auth state from an otherwise selected directory is forbidden. ... ok
test_snapshot_round_trips_files_symlinks_and_private_modes (tests.test_snapshot.SnapshotTest)
Following a link or broadening a mode would corrupt a private restore. ... ok
test_valid_prepared_journal_with_missing_parents_recovers_then_applies (tests.test_snapshot.SnapshotTest)
A journal published before parent creation remains recoverable after a crash. ... ok
test_verify_rejects_denylisted_duplicate_and_extra_manifest_entries (tests.test_snapshot.SnapshotTest)
A forged manifest must not smuggle auth state or unlisted payloads. ... ok
test_verify_rejects_noncanonical_manifest_aliases_and_malformed_records (tests.test_snapshot.SnapshotTest)
Equivalent-looking paths and incomplete records must not reach restore logic. ... ok
test_verify_rejects_symlinked_snapshot_storage_and_manifest_ancestors (tests.test_snapshot.SnapshotTest)
Verification must not follow a snapshot directory or files-tree symlink. ... ok
test_verify_reports_control_character_and_bad_type_records (tests.test_snapshot.SnapshotTest)
Hostile JSON types, NULs, and control characters must never escape verification. ... ok
test_verify_reports_tampered_content_and_permissions (tests.test_snapshot.SnapshotTest)
A manifest that is readable by others or no longer hashes correctly is invalid. ... ok
test_verify_requires_exact_file_modes_and_null_symlink_mode (tests.test_snapshot.SnapshotTest)
Private proof rejects narrow modes and symlink modes are deliberately ignored. ... ok

----------------------------------------------------------------------
Ran 46 tests in 16.534s

OK
```

Exact formatting check:

```sh
git diff --check
```

```text
```

Exit status: `0`.

### Implementation and security evidence

- Snapshot creation now opens Claude, Codex, and snapshot roots component by
  component with mandatory `O_DIRECTORY|O_NOFOLLOW`, retains those descriptors
  through selection, traversal, `readlink`, file reads, private destination
  writes, root-identity rechecks, and descriptor-recursive failure cleanup.
- Restore opens the verified snapshot and destination once and retains trusted
  root, target-parent, stage, and backup descriptors through recovery,
  replacement, rollback, committed-state verification, and cleanup. All
  `mkdir`, `rename`, `unlink`, `rmdir`, `chmod`, file creation, hashing, and
  recursive cleanup operations at this boundary are descriptor-relative.
- Journal v2 records both before- and after-state. Prepared journals roll back
  and committed journals clean only after exact after-state and parent-mode
  verification. Legacy v1 prepared journals remain recoverable; v1 committed
  journals refuse cleanup because they cannot prove after-state.
- Stage/backup entries and file contents are fsynced before the prepared
  journal; journal temporaries use `O_NOFOLLOW|O_EXCL`, file fsync, anchored
  rename, and destination-directory fsync. Parent mkdir/chmod, both parents of
  every cross-directory rename, target replacement, rollback, recursive
  cleanup, and journal unlink are each fsynced in dependency order.
- Manifest and journal validation type-checks every field before membership,
  regex, integer conversion, and filesystem access. C0/C1 control characters,
  NULs, unhashable lists/dicts, noncanonical paths, and physically unconfined
  entries return controlled `ValueError`/problem results.
- The adversarial suite now reaches full journal entries and parent records for
  symlinked target ancestors, symlinked backup directories and entries,
  post-validation rebinding, missing-parent recovery, dry-run immutability,
  static journal-temp symlinks, source/destination root rebinding, crash phases
  around backup/commit/cleanup, and actual `dir_fd`/fsync ordering.

### Exact new private snapshot and preservation proof

Before creation:

```sh
find /Users/mac/.kingstack/snapshots -mindepth 1 -maxdepth 1 -type d -name 'snapshot-*' -print | sort
```

```text
/Users/mac/.kingstack/snapshots/snapshot-20260820-092749
/Users/mac/.kingstack/snapshots/snapshot-20260820-092901
/Users/mac/.kingstack/snapshots/snapshot-20260820-093002
/Users/mac/.kingstack/snapshots/snapshot-20260820-093104
/Users/mac/.kingstack/snapshots/snapshot-20260820-094710
/Users/mac/.kingstack/snapshots/snapshot-20260820-101106
```

Creation with the required printed identifier:

```sh
ks_snapshot_id=$(./scripts/kingstack snapshot --label pre-neutral-migration-round-4 --print-id)
test -n "${ks_snapshot_id:?}"
printf '%s\n' "$ks_snapshot_id"
```

```text
snapshot-20260820-105637
```

Verification of that exact new identifier:

```sh
./scripts/kingstack snapshot verify snapshot-20260820-105637 --check-permissions
```

```text
verified snapshot-20260820-105637
```

After creation:

```sh
find /Users/mac/.kingstack/snapshots -mindepth 1 -maxdepth 1 -type d -name 'snapshot-*' -print | sort
```

```text
/Users/mac/.kingstack/snapshots/snapshot-20260820-092749
/Users/mac/.kingstack/snapshots/snapshot-20260820-092901
/Users/mac/.kingstack/snapshots/snapshot-20260820-093002
/Users/mac/.kingstack/snapshots/snapshot-20260820-093104
/Users/mac/.kingstack/snapshots/snapshot-20260820-094710
/Users/mac/.kingstack/snapshots/snapshot-20260820-101106
/Users/mac/.kingstack/snapshots/snapshot-20260820-105637
```

All six pre-existing snapshot directories remain. The only live write was the
new private snapshot `snapshot-20260820-105637`; no old snapshot was modified
or removed.

### Files and self-review

- `lib/kingstack/snapshot.py`: descriptor-anchored snapshot traversal,
  verification, expected-state hashing, journal publication, restoration,
  crash recovery, rollback, and durable cleanup.
- `tests/test_snapshot.py`: 16 new adversarial, schema, crash, root-rebind, and
  durability-order tests plus a strengthened backup-symlink fixture (38
  snapshot tests total).
- `.superpowers/sdd/2026-08-20-kingstack-foundation-plan/task-3-report.md`:
  exact RED/GREEN/live evidence for this round.

Self-review found and fixed two extra committed-cleanup crash windows with
focused RED tests before the final full GREEN run. The security behavior has no
known correctness blocker. Maintainability concern: `snapshot.py` is now a
large single-responsibility module because Python 3.9 descriptor-relative
filesystem primitives require explicit traversal, transaction, and durability
helpers. Splitting it was outside the Task 3 file plan and would add review
surface during the security fix round.

## Fix Round 3 — Remaining original evidence

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

## Fix Round 4 — RED chronology and audit evidence

Commit: this report is part of the single scoped Fix Round 4 commit. Its exact
SHA is reported by the implementer after commit creation because a Git commit
cannot embed its own hash.

### Exact primary RED command and unabridged output

```sh
PYTHONPATH=lib python3 -m unittest tests.test_snapshot -v
```

```text
test_apply_recovers_a_valid_interrupted_transaction_before_new_work (tests.test_snapshot.SnapshotTest)
A prepared journal restores its private backup before the next apply validates state. ... ok
test_apply_refuses_full_journal_with_symlinked_backup_entry (tests.test_snapshot.SnapshotTest)
A backup entry must physically match its recorded before-state before rollback. ... FAIL
test_apply_refuses_full_journal_with_symlinked_target_ancestor (tests.test_snapshot.SnapshotTest)
A complete journal cannot traverse a target ancestor symlink during recovery. ... ok
test_apply_refuses_journal_temp_symlink_without_outside_mutation (tests.test_snapshot.SnapshotTest)
The exclusive descriptor-relative journal temporary never follows a static symlink. ... ok
test_apply_refuses_symlinked_valid_journal_backup_without_outside_mutation (tests.test_snapshot.SnapshotTest)
A syntactically valid journal cannot redirect recovery through a backup symlink. ... ok
test_apply_refuses_unconfined_journal_without_touching_sentinel (tests.test_snapshot.SnapshotTest)
Malformed recovery metadata cannot name or mutate an outside target. ... ok
test_cli_prints_snapshot_id_and_verifies_it_by_id (tests.test_snapshot.SnapshotTest)
The CLI identifier must resolve to the private snapshot it just created. ... ok
test_cli_rejects_traversal_ids_and_apply_without_expected_hash (tests.test_snapshot.SnapshotTest)
CLI identifiers stay direct children and apply cannot bypass its precondition. ... ok
test_committed_recovery_never_cleans_up_when_restored_content_is_absent (tests.test_snapshot.SnapshotTest)
A committed journal remains recoverable if its claimed target is missing. ... FAIL
test_creation_refuses_destination_root_rebind_without_writing_replacement (tests.test_snapshot.SnapshotTest)
Snapshot writes remain on the opened destination descriptor after pathname rebind. ... FAIL
test_creation_refuses_source_root_rebind_without_reading_replacement (tests.test_snapshot.SnapshotTest)
Source reads remain on the opened root descriptor after its pathname is rebound. ... FAIL
test_dry_run_leaves_planted_journals_and_sentinels_unchanged (tests.test_snapshot.SnapshotTest)
Dry-run is observational even if a recovery journal is present or malformed. ... ok
test_dry_run_with_complete_pending_journal_is_byte_for_byte_read_only (tests.test_snapshot.SnapshotTest)
Even a valid pending transaction is only reported, never recovered by dry-run. ... ok
test_expected_hash_bad_type_raises_controlled_value_error (tests.test_snapshot.SnapshotTest)
An unhashable expected hash is rejected before membership or filesystem mutation. ... ERROR
test_interruption_after_backup_rename_is_recovered_to_before_state (tests.test_snapshot.SnapshotTest)
A crash after target-to-backup rename leaves a durable prepared rollback. ... ok
test_interruptions_around_committed_journal_recover_correct_side (tests.test_snapshot.SnapshotTest)
Prepared crashes roll back, while durably committed crashes retain restored bytes. ... ok
test_journal_status_mode_and_each_control_path_raise_controlled_value_error (tests.test_snapshot.SnapshotTest)
Malformed journal types and controls never escape as TypeError or OSError. ... test_journal_temp_collision_rolls_back_without_touching_destination (tests.test_snapshot.SnapshotTest)
An exclusive journal-temp failure leaves the pre-apply destination intact. ... ok
test_malformed_octal_manifest_mode_is_a_problem_not_an_exception (tests.test_snapshot.SnapshotTest)
A hostile mode field cannot crash the verifier before reporting invalidity. ... ok
test_manifest_mode_type_and_each_control_path_are_rejected_independently (tests.test_snapshot.SnapshotTest)
Unhashable modes and every C0/C1 control path produce verifier problems. ... test_nested_mutations_use_dir_fds_and_fsync_every_renamed_parent (tests.test_snapshot.SnapshotTest)
Every actual rename is descriptor-relative and synced in both affected parents. ... FAIL
test_recovery_unlink_stays_anchored_during_post_validation_parent_rebind (tests.test_snapshot.SnapshotTest)
Rebinding a validated target parent cannot redirect the actual rollback unlink. ... ERROR
test_restore_preflights_late_namespace_before_mutating_early_namespace (tests.test_snapshot.SnapshotTest)
A bad Codex parent must not permit any earlier Claude replacement. ... ok
test_restore_refuses_a_symlinked_destination_parent (tests.test_snapshot.SnapshotTest)
A restore must not follow a destination symlink outside the selected home. ... ok
test_restore_refuses_unknown_live_file_without_current_hash (tests.test_snapshot.SnapshotTest)
An existing destination file must not be overwritten without a precondition. ... ok
test_restore_requires_expected_hash_for_missing_targets_and_hashes_modes (tests.test_snapshot.SnapshotTest)
A creation-only restore still needs a state precondition, including modes. ... ok
test_snapshot_creation_rejects_an_existing_or_symlinked_id_path (tests.test_snapshot.SnapshotTest)
A timing collision must fail instead of reusing or chmodding an existing path. ... ok
test_snapshot_refuses_a_denylisted_source_path (tests.test_snapshot.SnapshotTest)
Copying auth state from an otherwise selected directory is forbidden. ... ok
test_snapshot_round_trips_files_symlinks_and_private_modes (tests.test_snapshot.SnapshotTest)
Following a link or broadening a mode would corrupt a private restore. ... ok
test_valid_prepared_journal_with_missing_parents_recovers_then_applies (tests.test_snapshot.SnapshotTest)
A journal published before parent creation remains recoverable after a crash. ... ERROR
test_verify_rejects_denylisted_duplicate_and_extra_manifest_entries (tests.test_snapshot.SnapshotTest)
A forged manifest must not smuggle auth state or unlisted payloads. ... ok
test_verify_rejects_noncanonical_manifest_aliases_and_malformed_records (tests.test_snapshot.SnapshotTest)
Equivalent-looking paths and incomplete records must not reach restore logic. ... ok
test_verify_rejects_symlinked_snapshot_storage_and_manifest_ancestors (tests.test_snapshot.SnapshotTest)
Verification must not follow a snapshot directory or files-tree symlink. ... ok
test_verify_reports_control_character_and_bad_type_records (tests.test_snapshot.SnapshotTest)
Hostile JSON types, NULs, and control characters must never escape verification. ... ok
test_verify_reports_tampered_content_and_permissions (tests.test_snapshot.SnapshotTest)
A manifest that is readable by others or no longer hashes correctly is invalid. ... ok
test_verify_requires_exact_file_modes_and_null_symlink_mode (tests.test_snapshot.SnapshotTest)
Private proof rejects narrow modes and symlink modes are deliberately ignored. ... ok

======================================================================
ERROR: test_expected_hash_bad_type_raises_controlled_value_error (tests.test_snapshot.SnapshotTest)
An unhashable expected hash is rejected before membership or filesystem mutation.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 683, in test_expected_hash_bad_type_raises_controlled_value_error
    restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=["not-a-hash"])
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 137, in restore_snapshot
    if not _HASH_PATTERN.fullmatch(expected_current_hash):
TypeError: expected string or bytes-like object

======================================================================
ERROR: test_journal_status_mode_and_each_control_path_raise_controlled_value_error (tests.test_snapshot.SnapshotTest) (field='status', value='[]')
Malformed journal types and controls never escape as TypeError or OSError.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 669, in test_journal_status_mode_and_each_control_path_raise_controlled_value_error
    restore_snapshot(
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 134, in restore_snapshot
    _recover_transaction(destination_home)
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 217, in _recover_transaction
    transaction = _read_journal(journal, destination)
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 297, in _read_journal
    if not isinstance(value, dict) or set(value) != required or value["version"] != 1 or value["status"] not in {"prepared", "committed"} or not isinstance(value["entries"], list) or not isinstance(value["parents"], list) or not isinstance(value["destination"], str) or value["destination"] != str(destination.resolve()) or not isinstance(value["snapshot"], str) or not _ID_PATTERN.fullmatch(value["snapshot"]) or not isinstance(value["expected"], str) or not _HASH_PATTERN.fullmatch(value["expected"]):
TypeError: unhashable type: 'list'

======================================================================
ERROR: test_manifest_mode_type_and_each_control_path_are_rejected_independently (tests.test_snapshot.SnapshotTest) (field='mode', value='[]')
Unhashable modes and every C0/C1 control path produce verifier problems.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 635, in test_manifest_mode_type_and_each_control_path_are_rejected_independently
    problems = verify_snapshot(snapshot, check_permissions=True)
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 96, in verify_snapshot
    problems = _manifest_problems(manifest)
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 427, in _manifest_problems
    if record["mode"] not in {"0600", "0700"} or record["target"] is not None:
TypeError: unhashable type: 'list'

======================================================================
ERROR: test_recovery_unlink_stays_anchored_during_post_validation_parent_rebind (tests.test_snapshot.SnapshotTest)
Rebinding a validated target parent cannot redirect the actual rollback unlink.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 522, in test_recovery_unlink_stays_anchored_during_post_validation_parent_rebind
    self.assertEqual(sentinel.read_bytes(), b"outside-sentinel\n")
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1249, in read_bytes
    with self.open(mode='rb') as f:
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1242, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1110, in _opener
    return self._accessor.open(self, flags, mode)
FileNotFoundError: [Errno 2] No such file or directory: '/var/folders/ly/53rfjx09379f11nthm4flvxc0000gn/T/tmp5kz4v16x/outside/settings.json'

======================================================================
ERROR: test_valid_prepared_journal_with_missing_parents_recovers_then_applies (tests.test_snapshot.SnapshotTest)
A journal published before parent creation remains recoverable after a crash.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 263, in _validate_journal_physical
    _open_journal_parent(root_fd, entry["target"])
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 667, in _open_journal_parent
    _open_journal_parts(root_fd, PurePosixPath(relative).parts[:-1])
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 678, in _open_journal_parts
    child = _open_child_directory(descriptor, part)
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 659, in _open_child_directory
    descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
FileNotFoundError: [Errno 2] No such file or directory: '.claude'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 592, in test_valid_prepared_journal_with_missing_parents_recovers_then_applies
    restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=expected)
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 134, in restore_snapshot
    _recover_transaction(destination_home)
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 218, in _recover_transaction
    _validate_journal_physical(destination, transaction)
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/lib/kingstack/snapshot.py", line 267, in _validate_journal_physical
    raise ValueError("invalid restore transaction journal") from error
ValueError: invalid restore transaction journal

======================================================================
FAIL: test_apply_refuses_full_journal_with_symlinked_backup_entry (tests.test_snapshot.SnapshotTest)
A backup entry must physically match its recorded before-state before rollback.
----------------------------------------------------------------------
ValueError: refusing live apply: expected current hash does not match

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 567, in test_apply_refuses_full_journal_with_symlinked_backup_entry
    restore_snapshot(
AssertionError: "journal" does not match "refusing live apply: expected current hash does not match"

======================================================================
FAIL: test_committed_recovery_never_cleans_up_when_restored_content_is_absent (tests.test_snapshot.SnapshotTest)
A committed journal remains recoverable if its claimed target is missing.
----------------------------------------------------------------------
ValueError: refusing live apply: expected current hash does not match

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 838, in test_committed_recovery_never_cleans_up_when_restored_content_is_absent
    restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash="0" * 64)
AssertionError: "committed|journal" does not match "refusing live apply: expected current hash does not match"

======================================================================
FAIL: test_creation_refuses_destination_root_rebind_without_writing_replacement (tests.test_snapshot.SnapshotTest)
Snapshot writes remain on the opened destination descriptor after pathname rebind.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 743, in test_creation_refuses_destination_root_rebind_without_writing_replacement
    self.assertFalse(any(relocated.glob("snapshot-*")))
AssertionError: True is not false

======================================================================
FAIL: test_creation_refuses_source_root_rebind_without_reading_replacement (tests.test_snapshot.SnapshotTest)
Source reads remain on the opened root descriptor after its pathname is rebound.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 708, in test_creation_refuses_source_root_rebind_without_reading_replacement
    create_snapshot(Paths.for_home(self.home), self.snapshot_root, "source-rebind")
AssertionError: ValueError not raised

======================================================================
FAIL: test_manifest_mode_type_and_each_control_path_are_rejected_independently (tests.test_snapshot.SnapshotTest) (field='path', value="'claude/bad\\x7fname'")
Unhashable modes and every C0/C1 control path produce verifier problems.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 636, in test_manifest_mode_type_and_each_control_path_are_rejected_independently
    self.assertTrue(any("invalid" in problem for problem in problems), problems)
AssertionError: False is not true : ['missing or wrong snapshot entry: files/claude/bad\x7fname', 'unexpected snapshot entry: files/claude/agents', 'unexpected snapshot entry: files/claude/agents/read-only.json']

======================================================================
FAIL: test_manifest_mode_type_and_each_control_path_are_rejected_independently (tests.test_snapshot.SnapshotTest) (field='path', value="'claude/bad\\x85name'")
Unhashable modes and every C0/C1 control path produce verifier problems.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 636, in test_manifest_mode_type_and_each_control_path_are_rejected_independently
    self.assertTrue(any("invalid" in problem for problem in problems), problems)
AssertionError: False is not true : ['missing or wrong snapshot entry: files/claude/bad\x85name', 'unexpected snapshot entry: files/claude/agents', 'unexpected snapshot entry: files/claude/agents/read-only.json']

======================================================================
FAIL: test_nested_mutations_use_dir_fds_and_fsync_every_renamed_parent (tests.test_snapshot.SnapshotTest)
Every actual rename is descriptor-relative and synced in both affected parents.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 893, in test_nested_mutations_use_dir_fds_and_fsync_every_renamed_parent
    self.assertTrue(rename_indexes, events)
AssertionError: [] is not true : [('fsync', (16777233, 121908914)), ('fsync', (16777233, 121908915)), ('fsync', (16777233, 121908916)), ('fsync', (16777233, 121908917)), ('fsync', (16777233, 121908919)), ('fsync', (16777233, 121908912)), ('fsync', (16777233, 121908913)), ('fsync', (16777233, 121908920)), ('fsync', (16777233, 121908909)), ('fsync', (16777233, 121908922)), ('fsync', (16777233, 121908923)), ('fsync', (16777233, 121908927)), ('fsync', (16777233, 121908913)), ('fsync', (16777233, 121908910)), ('fsync', (16777233, 121908925)), ('fsync', (16777233, 121908921)), ('fsync', (16777233, 121908928)), ('fsync', (16777233, 121908909))]

----------------------------------------------------------------------
Ran 36 tests in 2.874s

FAILED (failures=7, errors=5)
```

### Exact audit RED commands and unabridged outputs

```sh
PYTHONPATH=lib python3 -m unittest tests.test_snapshot.SnapshotTest.test_committed_recovery_finishes_after_backup_cleanup_crash -v
```

```text
test_committed_recovery_finishes_after_backup_cleanup_crash (tests.test_snapshot.SnapshotTest)
Committed after-state is sufficient once a durable backup cleanup has happened. ... FAIL

======================================================================
FAIL: test_committed_recovery_finishes_after_backup_cleanup_crash (tests.test_snapshot.SnapshotTest)
Committed after-state is sufficient once a durable backup cleanup has happened.
----------------------------------------------------------------------
ValueError: invalid restore transaction journal

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 879, in test_committed_recovery_finishes_after_backup_cleanup_crash
    restore_snapshot(
AssertionError: "expected current hash" does not match "invalid restore transaction journal"

----------------------------------------------------------------------
Ran 1 test in 0.495s

FAILED (failures=1)
```

```sh
PYTHONPATH=lib python3 -m unittest tests.test_snapshot.SnapshotTest.test_cleanup_refuses_transaction_directory_created_after_validation -v
```

```text
test_cleanup_refuses_transaction_directory_created_after_validation (tests.test_snapshot.SnapshotTest)
An absent transaction directory cannot be rebound to attacker data for cleanup. ... ERROR

======================================================================
ERROR: test_cleanup_refuses_transaction_directory_created_after_validation (tests.test_snapshot.SnapshotTest)
An absent transaction directory cannot be rebound to attacker data for cleanup.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 940, in test_cleanup_refuses_transaction_directory_created_after_validation
    self.assertEqual(replacement_sentinel.read_bytes(), b"attacker-data\n")
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1249, in read_bytes
    with self.open(mode='rb') as f:
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1242, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py", line 1110, in _opener
    return self._accessor.open(self, flags, mode)
FileNotFoundError: [Errno 2] No such file or directory: '/var/folders/ly/53rfjx09379f11nthm4flvxc0000gn/T/tmpo3ii_v40/restore-home/.kingstack-restore-stage-3adb1e006d824979990f74fbd853352c/sentinel'

----------------------------------------------------------------------
Ran 1 test in 0.528s

FAILED (errors=1)
```

### Pre-final-audit status

Both recovery audit REDs were converted to GREEN before the subsequent
durability-order audit. The module-size maintainability concern is recorded with
the complete evidence above.

### Exact durability-order audit RED command and unabridged output

```sh
PYTHONPATH=lib python3 -m unittest tests.test_snapshot.SnapshotTest.test_nested_mutations_use_dir_fds_and_fsync_every_renamed_parent -v
```

```text
test_nested_mutations_use_dir_fds_and_fsync_every_renamed_parent (tests.test_snapshot.SnapshotTest)
Every actual rename is descriptor-relative and synced in both affected parents. ... FAIL

======================================================================
FAIL: test_nested_mutations_use_dir_fds_and_fsync_every_renamed_parent (tests.test_snapshot.SnapshotTest)
Every actual rename is descriptor-relative and synced in both affected parents.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/.claude/.worktrees/agent-neutral-kingstack/tests/test_snapshot.py", line 1013, in test_nested_mutations_use_dir_fds_and_fsync_every_renamed_parent
    self.assertEqual(
AssertionError: Lists differ: [(16777233, 121951763), (16777233, 121951773)] != [(16777233, 121951773), (16777233, 121951763)]

First differing element 0:
(16777233, 121951763)
(16777233, 121951773)

- [(16777233, 121951763), (16777233, 121951773)]
+ [(16777233, 121951773), (16777233, 121951763)] : (('rename', '0', 'read-only.json', (16777233, 121951763), (16777233, 121951773), (16777233, 121951765)), [('fsync', (16777233, 121951763)), ('fsync', (16777233, 121951773))])

----------------------------------------------------------------------
Ran 1 test in 0.750s

FAILED (failures=1)
```

The helper now fsyncs the destination directory first for cross-directory
renames, preserving a durable name for the inode before making source removal
durable. Same-directory renames still require one directory fsync.

### Exact final GREEN command and unabridged output

```sh
PYTHONPATH=lib python3 -m unittest tests.test_paths tests.test_inventory tests.test_snapshot -v
```

```text
test_defaults_are_agent_neutral_and_runtime_is_outside_repo (tests.test_paths.PathsTest) ... ok
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
test_apply_recovers_a_valid_interrupted_transaction_before_new_work (tests.test_snapshot.SnapshotTest)
A prepared journal restores its private backup before the next apply validates state. ... ok
test_apply_refuses_full_journal_with_symlinked_backup_entry (tests.test_snapshot.SnapshotTest)
A backup entry must physically match its recorded before-state before rollback. ... ok
test_apply_refuses_full_journal_with_symlinked_target_ancestor (tests.test_snapshot.SnapshotTest)
A complete journal cannot traverse a target ancestor symlink during recovery. ... ok
test_apply_refuses_journal_temp_symlink_without_outside_mutation (tests.test_snapshot.SnapshotTest)
The exclusive descriptor-relative journal temporary never follows a static symlink. ... ok
test_apply_refuses_symlinked_valid_journal_backup_without_outside_mutation (tests.test_snapshot.SnapshotTest)
A syntactically valid journal cannot redirect recovery through a backup symlink. ... ok
test_apply_refuses_unconfined_journal_without_touching_sentinel (tests.test_snapshot.SnapshotTest)
Malformed recovery metadata cannot name or mutate an outside target. ... ok
test_cleanup_refuses_transaction_directory_created_after_validation (tests.test_snapshot.SnapshotTest)
An absent transaction directory cannot be rebound to attacker data for cleanup. ... ok
test_cli_prints_snapshot_id_and_verifies_it_by_id (tests.test_snapshot.SnapshotTest)
The CLI identifier must resolve to the private snapshot it just created. ... ok
test_cli_rejects_traversal_ids_and_apply_without_expected_hash (tests.test_snapshot.SnapshotTest)
CLI identifiers stay direct children and apply cannot bypass its precondition. ... ok
test_committed_recovery_finishes_after_backup_cleanup_crash (tests.test_snapshot.SnapshotTest)
Committed after-state is sufficient once a durable backup cleanup has happened. ... ok
test_committed_recovery_never_cleans_up_when_restored_content_is_absent (tests.test_snapshot.SnapshotTest)
A committed journal remains recoverable if its claimed target is missing. ... ok
test_creation_refuses_destination_root_rebind_without_writing_replacement (tests.test_snapshot.SnapshotTest)
Snapshot writes remain on the opened destination descriptor after pathname rebind. ... ok
test_creation_refuses_source_root_rebind_without_reading_replacement (tests.test_snapshot.SnapshotTest)
Source reads remain on the opened root descriptor after its pathname is rebound. ... ok
test_dry_run_leaves_planted_journals_and_sentinels_unchanged (tests.test_snapshot.SnapshotTest)
Dry-run is observational even if a recovery journal is present or malformed. ... ok
test_dry_run_with_complete_pending_journal_is_byte_for_byte_read_only (tests.test_snapshot.SnapshotTest)
Even a valid pending transaction is only reported, never recovered by dry-run. ... ok
test_expected_hash_bad_type_raises_controlled_value_error (tests.test_snapshot.SnapshotTest)
An unhashable expected hash is rejected before membership or filesystem mutation. ... ok
test_interruption_after_backup_rename_is_recovered_to_before_state (tests.test_snapshot.SnapshotTest)
A crash after target-to-backup rename leaves a durable prepared rollback. ... ok
test_interruptions_around_committed_journal_recover_correct_side (tests.test_snapshot.SnapshotTest)
Prepared crashes roll back, while durably committed crashes retain restored bytes. ... ok
test_journal_status_mode_and_each_control_path_raise_controlled_value_error (tests.test_snapshot.SnapshotTest)
Malformed journal types and controls never escape as TypeError or OSError. ... ok
test_journal_temp_collision_rolls_back_without_touching_destination (tests.test_snapshot.SnapshotTest)
An exclusive journal-temp failure leaves the pre-apply destination intact. ... ok
test_malformed_octal_manifest_mode_is_a_problem_not_an_exception (tests.test_snapshot.SnapshotTest)
A hostile mode field cannot crash the verifier before reporting invalidity. ... ok
test_manifest_mode_type_and_each_control_path_are_rejected_independently (tests.test_snapshot.SnapshotTest)
Unhashable modes and every C0/C1 control path produce verifier problems. ... ok
test_nested_mutations_use_dir_fds_and_fsync_every_renamed_parent (tests.test_snapshot.SnapshotTest)
Every actual rename is descriptor-relative and synced in both affected parents. ... ok
test_recovery_unlink_stays_anchored_during_post_validation_parent_rebind (tests.test_snapshot.SnapshotTest)
Rebinding a validated target parent cannot redirect the actual rollback unlink. ... ok
test_restore_preflights_late_namespace_before_mutating_early_namespace (tests.test_snapshot.SnapshotTest)
A bad Codex parent must not permit any earlier Claude replacement. ... ok
test_restore_refuses_a_symlinked_destination_parent (tests.test_snapshot.SnapshotTest)
A restore must not follow a destination symlink outside the selected home. ... ok
test_restore_refuses_unknown_live_file_without_current_hash (tests.test_snapshot.SnapshotTest)
An existing destination file must not be overwritten without a precondition. ... ok
test_restore_requires_expected_hash_for_missing_targets_and_hashes_modes (tests.test_snapshot.SnapshotTest)
A creation-only restore still needs a state precondition, including modes. ... ok
test_snapshot_creation_rejects_an_existing_or_symlinked_id_path (tests.test_snapshot.SnapshotTest)
A timing collision must fail instead of reusing or chmodding an existing path. ... ok
test_snapshot_refuses_a_denylisted_source_path (tests.test_snapshot.SnapshotTest)
Copying auth state from an otherwise selected directory is forbidden. ... ok
test_snapshot_round_trips_files_symlinks_and_private_modes (tests.test_snapshot.SnapshotTest)
Following a link or broadening a mode would corrupt a private restore. ... ok
test_valid_prepared_journal_with_missing_parents_recovers_then_applies (tests.test_snapshot.SnapshotTest)
A journal published before parent creation remains recoverable after a crash. ... ok
test_verify_rejects_denylisted_duplicate_and_extra_manifest_entries (tests.test_snapshot.SnapshotTest)
A forged manifest must not smuggle auth state or unlisted payloads. ... ok
test_verify_rejects_noncanonical_manifest_aliases_and_malformed_records (tests.test_snapshot.SnapshotTest)
Equivalent-looking paths and incomplete records must not reach restore logic. ... ok
test_verify_rejects_symlinked_snapshot_storage_and_manifest_ancestors (tests.test_snapshot.SnapshotTest)
Verification must not follow a snapshot directory or files-tree symlink. ... ok
test_verify_reports_control_character_and_bad_type_records (tests.test_snapshot.SnapshotTest)
Hostile JSON types, NULs, and control characters must never escape verification. ... ok
test_verify_reports_tampered_content_and_permissions (tests.test_snapshot.SnapshotTest)
A manifest that is readable by others or no longer hashes correctly is invalid. ... ok
test_verify_requires_exact_file_modes_and_null_symlink_mode (tests.test_snapshot.SnapshotTest)
Private proof rejects narrow modes and symlink modes are deliberately ignored. ... ok

----------------------------------------------------------------------
Ran 46 tests in 3.669s

OK
```

Final result: 46 tests passed with no skips. The snapshot subset contributes 38
tests, including the adversarial transaction, crash, schema, and root-rebinding
coverage added or strengthened in this round.
