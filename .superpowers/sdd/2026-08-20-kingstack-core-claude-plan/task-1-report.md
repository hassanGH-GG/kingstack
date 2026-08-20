# Core Task 1 implementation report

Append-only evidence log.

## Implementation result (2026-08-20)

Implemented the exact seven-field adapter declaration, JSON schemas, stable
capability catalog, typed loader/validator/report types, first-party declaration
fixtures, synthetic third-adapter fixture, and the `kingstack check --contract`
surface. No renderer or first-party implementation module is imported during
contract loading.

### RED

Command:

```text
PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract -v
```

Unabridged result before production implementation:

```text
test_adapter_contract (unittest.loader._FailedTest) ... ERROR

======================================================================
ERROR: test_adapter_contract (unittest.loader._FailedTest)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_adapter_contract
Traceback (most recent call last):
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/unittest/loader.py", line 154, in loadTestsFromName
    module = __import__(module_name)
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 8, in <module>
    from kingstack.adapter_contract import (
ModuleNotFoundError: No module named 'kingstack.adapter_contract'


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

The failure was the required missing contract module, not a test typo or an
unrelated error.

### Focused GREEN

Command:

```text
PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract -v
```

Unabridged final result:

```text
test_contract_cli_accepts_named_and_synthetic_adapters (tests.test_adapter_contract.AdapterContractTest) ... ok
test_contract_cli_requires_exactly_one_adapter_selector (tests.test_adapter_contract.AdapterContractTest) ... ok
test_every_non_native_state_requires_evidence_and_impact (tests.test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_duplicates_absolute_paths_and_home_root (tests.test_adapter_contract.AdapterContractTest) ... ok
test_render_module_must_be_an_importable_shape (tests.test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_reject_unknown_top_level_key (tests.test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_validation_agree_on_checked_in_declarations (tests.test_adapter_contract.AdapterContractTest) ... ok
test_strict_parity_cannot_overstate_degraded_or_unsupported_state (tests.test_adapter_contract.AdapterContractTest) ... ok
test_synthetic_adapter_has_no_first_party_dependency (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unknown_capability_and_status_are_rejected (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unknown_tier_and_unmapped_catalog_tier_are_reported (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unsupported_capability_is_visible (tests.test_adapter_contract.AdapterContractTest) ... ok

----------------------------------------------------------------------
Ran 12 tests in 0.060s

OK
```

### Contract CLI

Commands and unabridged output:

```text
$ ./scripts/kingstack check --contract --adapter claude
claude adapter contract valid
$ ./scripts/kingstack check --contract --adapter codex
codex adapter contract valid
$ ./scripts/kingstack check --contract --adapter-path tests/fixtures/adapters/example
example adapter contract valid
```

The example declaration resolves its external capability matrix and validates
without importing or naming either first-party renderer in `render_module`.

### Full regression suite

Command:

```text
PYTHONPATH=lib python3 -m unittest discover -s tests -v
```

Unabridged final result:

```text
test_contract_cli_accepts_named_and_synthetic_adapters (test_adapter_contract.AdapterContractTest) ... ok
test_contract_cli_requires_exactly_one_adapter_selector (test_adapter_contract.AdapterContractTest) ... ok
test_every_non_native_state_requires_evidence_and_impact (test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_duplicates_absolute_paths_and_home_root (test_adapter_contract.AdapterContractTest) ... ok
test_render_module_must_be_an_importable_shape (test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_reject_unknown_top_level_key (test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_validation_agree_on_checked_in_declarations (test_adapter_contract.AdapterContractTest) ... ok
test_strict_parity_cannot_overstate_degraded_or_unsupported_state (test_adapter_contract.AdapterContractTest) ... ok
test_synthetic_adapter_has_no_first_party_dependency (test_adapter_contract.AdapterContractTest) ... ok
test_unknown_capability_and_status_are_rejected (test_adapter_contract.AdapterContractTest) ... ok
test_unknown_tier_and_unmapped_catalog_tier_are_reported (test_adapter_contract.AdapterContractTest) ... ok
test_unsupported_capability_is_visible (test_adapter_contract.AdapterContractTest) ... ok
test_baseline_home_parent_alias_cannot_hide_native_destination (test_bootstrap.BootstrapTest) ... ok
test_clone_preserves_head_origin_tags_and_writes_only_redacted_baseline (test_bootstrap.BootstrapTest) ... ok
test_clone_with_no_source_upstream_has_no_manufactured_upstream_or_refs (test_bootstrap.BootstrapTest) ... ok
test_cloned_symlinked_baseline_parent_never_overwrites_external_file (test_bootstrap.BootstrapTest) ... ok
test_destination_and_runtime_cannot_overlap_native_homes (test_bootstrap.BootstrapTest) ... ok
test_destination_parent_swap_during_source_check_never_redirects_clone (test_bootstrap.BootstrapTest) ... ok
test_dirty_source_is_always_refused_without_writes (test_bootstrap.BootstrapTest) ... ok
test_dry_run_reports_exact_writes_without_creating_any_path (test_bootstrap.BootstrapTest) ... ok
test_existing_cloned_baseline_is_never_overwritten (test_bootstrap.BootstrapTest) ... ok
test_existing_destination_is_refused_without_mutation (test_bootstrap.BootstrapTest) ... ok
test_existing_runtime_is_tightened_without_touching_its_contents (test_bootstrap.BootstrapTest) ... ok
test_manifest_publication_race_never_overwrites_contender (test_bootstrap.BootstrapTest) ... ok
test_parent_change_after_manifest_never_returns_failure_with_success_record (test_bootstrap.BootstrapTest) ... ok
test_parent_descriptor_close_error_cannot_turn_committed_success_into_failure (test_bootstrap.BootstrapTest) ... ok
test_private_manifest_commit_survives_owned_parent_close_error (test_bootstrap.BootstrapTest) ... ok
test_symlinked_destination_parent_is_refused_without_external_write (test_bootstrap.BootstrapTest) ... ok
test_symlinked_runtime_is_refused_without_following_it (test_bootstrap.BootstrapTest) ... ok
test_symlinked_runtime_parent_is_refused_without_external_write (test_bootstrap.BootstrapTest) ... ok
test_unpushed_history_requires_explicit_permission (test_bootstrap.BootstrapTest) ... ok
test_no_recursive_backup_or_restore_surface (test_cli_surface.CliSurfaceTest) ... ok
test_capture_excludes_sensitive_paths_at_every_depth (test_inventory.InventoryTest) ... ok
test_capture_is_deterministic_and_redacts_config_values (test_inventory.InventoryTest) ... ok
test_capture_records_symlink_mode_and_file_hash (test_inventory.InventoryTest) ... ok
test_capture_redacts_absolute_symlink_targets (test_inventory.InventoryTest) ... ok
test_capture_redacts_path_shaped_json_key_names (test_inventory.InventoryTest) ... ok
test_cli_writes_fixture_inventory_and_rejects_agent_home_output (test_inventory.InventoryTest) ... ok
test_committed_atomic_write_survives_temp_unlink_error_after_cleanup (test_inventory.InventoryTest) ... ok
test_write_public_report_is_byte_deterministic_and_rejects_private_destinations (test_inventory.InventoryTest) ... ok
test_write_public_report_refuses_symlinked_parent_and_existing_file (test_inventory.InventoryTest) ... ok
test_write_public_report_supports_real_macos_mktemp_var_alias (test_inventory.InventoryTest) ... ok
test_defaults_are_agent_neutral_and_runtime_is_outside_repo (test_paths.PathsTest) ... ok

----------------------------------------------------------------------
Ran 43 tests in 8.136s

OK
```

### Static and no-live-change proof

Commands:

```text
PYTHONPATH=lib python3 -m py_compile lib/kingstack/adapter_contract.py lib/kingstack/cli.py tests/test_adapter_contract.py
git diff --check
python3 -m json.tool <each Task 1 JSON document>
```

All exited zero with no output. A fresh read-only inventory was then compared
with the frozen foundation baseline:

```text
8d943deaa440a279452e3af79400c6651722306936d2d90922692810722ddf27  docs/baselines/claude-codex-baseline.json
8d943deaa440a279452e3af79400c6651722306936d2d90922692810722ddf27  <temporary>/live-baseline.json
native homes: real directories, not symlinks
historical top-level directories:
archive-20260820-121406
archive-20260820-122621
snapshot-20260820-092749
snapshot-20260820-092901
snapshot-20260820-093002
snapshot-20260820-093104
snapshot-20260820-094710
snapshot-20260820-101106
snapshot-20260820-105637
snapshot-20260820-113207
adapter runtime current links: none
```

The baseline files were byte-identical (`cmp` exit zero). No path under
`~/.claude`, `~/.codex`, or `~/.kingstack` was created, linked, renamed,
rewritten, activated, or removed by Task 1. Nothing was pushed.

## Independent-review fix round 1 (2026-08-20)

The independent review rejected the first implementation because ownership
paths were compared before canonicalization, matrices could omit catalog IDs,
model values could contain only whitespace, named selectors accepted path
syntax, and catalog identifiers were under-validated. The fix was developed as
a separate TDD cycle from commit `8896079`.

### RED cycle 1: named-selector boundary

Command:

```text
PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract -v
```

Unabridged result after adding the adversarial tests and before adding the named
selector boundary:

```text
test_adapter_contract (unittest.loader._FailedTest) ... ERROR

======================================================================
ERROR: test_adapter_contract (unittest.loader._FailedTest)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_adapter_contract
Traceback (most recent call last):
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/unittest/loader.py", line 154, in loadTestsFromName
    module = __import__(module_name)
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 17, in <module>
    from kingstack.cli import _load_selected_adapter, main
ImportError: cannot import name '_load_selected_adapter' from 'kingstack.cli' (/Users/mac/Desktop/Work/kingstack/lib/kingstack/cli.py)


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

### RED cycle 2: contract semantics

After the minimal named-selector boundary was implemented, the same command
executed all adversarial cases. Unabridged result:

```text
test_capability_matrix_must_cover_catalog_exactly (tests.test_adapter_contract.AdapterContractTest) ... FAIL
test_catalog_rejects_boolean_version_and_unstable_ids (tests.test_adapter_contract.AdapterContractTest) ... test_contract_cli_accepts_named_and_synthetic_adapters (tests.test_adapter_contract.AdapterContractTest) ... ok
test_contract_cli_requires_exactly_one_adapter_selector (tests.test_adapter_contract.AdapterContractTest) ... ok
test_every_non_native_state_requires_evidence_and_impact (tests.test_adapter_contract.AdapterContractTest) ... ok
test_model_mapping_rejects_whitespace_only_values (tests.test_adapter_contract.AdapterContractTest) ... FAIL
test_named_adapter_selector_must_match_loaded_id (tests.test_adapter_contract.AdapterContractTest) ... ok
test_named_adapter_selector_rejects_path_syntax (tests.test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_are_canonical_before_duplicate_and_root_checks (tests.test_adapter_contract.AdapterContractTest) ... FAIL
test_owned_paths_reject_duplicates_absolute_paths_and_home_root (tests.test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_lossy_or_backtracking_spelling (tests.test_adapter_contract.AdapterContractTest) ... test_render_module_must_be_an_importable_shape (tests.test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_reject_unknown_top_level_key (tests.test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_validation_agree_on_checked_in_declarations (tests.test_adapter_contract.AdapterContractTest) ... test_strict_parity_cannot_overstate_degraded_or_unsupported_state (tests.test_adapter_contract.AdapterContractTest) ... ok
test_synthetic_adapter_has_no_first_party_dependency (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unknown_capability_and_status_are_rejected (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unknown_tier_and_unmapped_catalog_tier_are_reported (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unsupported_capability_is_visible (tests.test_adapter_contract.AdapterContractTest) ... ok

======================================================================
FAIL: test_capability_matrix_must_cover_catalog_exactly (tests.test_adapter_contract.AdapterContractTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 237, in test_capability_matrix_must_cover_catalog_exactly
    self.assertTrue(any("missing capability" in error for error in errors))
AssertionError: False is not true

======================================================================
FAIL: test_catalog_rejects_boolean_version_and_unstable_ids (tests.test_adapter_contract.AdapterContractTest) (path=('contract_version',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 333, in test_catalog_rejects_boolean_version_and_unstable_ids
    load_capability_catalog(path)
AssertionError: AdapterContractError not raised

======================================================================
FAIL: test_catalog_rejects_boolean_version_and_unstable_ids (tests.test_adapter_contract.AdapterContractTest) (path=('model_tiers', 0))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 333, in test_catalog_rejects_boolean_version_and_unstable_ids
    load_capability_catalog(path)
AssertionError: AdapterContractError not raised

======================================================================
FAIL: test_catalog_rejects_boolean_version_and_unstable_ids (tests.test_adapter_contract.AdapterContractTest) (path=('capabilities', 0, 'id'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 333, in test_catalog_rejects_boolean_version_and_unstable_ids
    load_capability_catalog(path)
AssertionError: AdapterContractError not raised

======================================================================
FAIL: test_model_mapping_rejects_whitespace_only_values (tests.test_adapter_contract.AdapterContractTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 156, in test_model_mapping_rejects_whitespace_only_values
    load_adapter(self.write_adapter(payload))
AssertionError: AdapterContractError not raised

======================================================================
FAIL: test_owned_paths_are_canonical_before_duplicate_and_root_checks (tests.test_adapter_contract.AdapterContractTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 107, in test_owned_paths_are_canonical_before_duplicate_and_root_checks
    load_adapter(self.write_adapter(payload))
AssertionError: AdapterContractError not raised

======================================================================
FAIL: test_owned_paths_reject_lossy_or_backtracking_spelling (tests.test_adapter_contract.AdapterContractTest) (path='hooks/start/')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 130, in test_owned_paths_reject_lossy_or_backtracking_spelling
    load_adapter(self.write_adapter(payload))
AssertionError: AdapterContractError not raised

======================================================================
FAIL: test_owned_paths_reject_lossy_or_backtracking_spelling (tests.test_adapter_contract.AdapterContractTest) (path='hooks//start')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 130, in test_owned_paths_reject_lossy_or_backtracking_spelling
    load_adapter(self.write_adapter(payload))
AssertionError: AdapterContractError not raised

======================================================================
FAIL: test_owned_paths_reject_lossy_or_backtracking_spelling (tests.test_adapter_contract.AdapterContractTest) (path='../start')
----------------------------------------------------------------------
kingstack.adapter_contract.AdapterContractError: owned_paths entries may not escape the native home

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 130, in test_owned_paths_reject_lossy_or_backtracking_spelling
    load_adapter(self.write_adapter(payload))
AssertionError: "backtracking" does not match "owned_paths entries may not escape the native home"

======================================================================
FAIL: test_owned_paths_reject_lossy_or_backtracking_spelling (tests.test_adapter_contract.AdapterContractTest) (path='hooks/../start')
----------------------------------------------------------------------
kingstack.adapter_contract.AdapterContractError: owned_paths entries may not escape the native home

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 130, in test_owned_paths_reject_lossy_or_backtracking_spelling
    load_adapter(self.write_adapter(payload))
AssertionError: "backtracking" does not match "owned_paths entries may not escape the native home"

======================================================================
FAIL: test_schema_and_python_validation_agree_on_checked_in_declarations (tests.test_adapter_contract.AdapterContractTest) (adapter=PosixPath('/Users/mac/Desktop/Work/kingstack/adapters/claude/adapter.json'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 223, in test_schema_and_python_validation_agree_on_checked_in_declarations
    self.assertEqual(
AssertionError: Items in the second set but not the first:
'skill_catalog'
'health'
'stop_capture'
'post_tool_use'
'activation'
'shared_memory'
'schedules'
'rollback'
'model_routing'
'subagent_start'
'session_start'

======================================================================
FAIL: test_schema_and_python_validation_agree_on_checked_in_declarations (tests.test_adapter_contract.AdapterContractTest) (adapter=PosixPath('/Users/mac/Desktop/Work/kingstack/adapters/codex/adapter.json'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 223, in test_schema_and_python_validation_agree_on_checked_in_declarations
    self.assertEqual(
AssertionError: Items in the second set but not the first:
'skill_catalog'
'health'
'stop_capture'
'post_tool_use'
'activation'
'shared_memory'
'schedules'
'rollback'
'model_routing'
'subagent_start'
'session_start'

======================================================================
FAIL: test_schema_and_python_validation_agree_on_checked_in_declarations (tests.test_adapter_contract.AdapterContractTest) (adapter=PosixPath('/Users/mac/Desktop/Work/kingstack/tests/fixtures/adapters/example/adapter.json'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 223, in test_schema_and_python_validation_agree_on_checked_in_declarations
    self.assertEqual(
AssertionError: Items in the second set but not the first:
'skill_catalog'
'health'
'stop_capture'
'post_tool_use'
'activation'
'shared_memory'
'schedules'
'rollback'
'model_routing'
'subagent_start'
'session_start'

----------------------------------------------------------------------
Ran 19 tests in 0.124s

FAILED (failures=13)
```

### Adversarial GREEN

Command:

```text
PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract -v
```

Unabridged final result:

```text
test_capability_matrix_must_cover_catalog_exactly (tests.test_adapter_contract.AdapterContractTest) ... ok
test_catalog_rejects_boolean_version_and_unstable_ids (tests.test_adapter_contract.AdapterContractTest) ... ok
test_contract_cli_accepts_named_and_synthetic_adapters (tests.test_adapter_contract.AdapterContractTest) ... ok
test_contract_cli_requires_exactly_one_adapter_selector (tests.test_adapter_contract.AdapterContractTest) ... ok
test_every_non_native_state_requires_evidence_and_impact (tests.test_adapter_contract.AdapterContractTest) ... ok
test_model_mapping_rejects_whitespace_only_values (tests.test_adapter_contract.AdapterContractTest) ... ok
test_named_adapter_selector_must_match_loaded_id (tests.test_adapter_contract.AdapterContractTest) ... ok
test_named_adapter_selector_rejects_path_syntax (tests.test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_are_canonical_before_duplicate_and_root_checks (tests.test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_duplicates_absolute_paths_and_home_root (tests.test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_lossy_or_backtracking_spelling (tests.test_adapter_contract.AdapterContractTest) ... ok
test_render_module_must_be_an_importable_shape (tests.test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_reject_unknown_top_level_key (tests.test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_validation_agree_on_checked_in_declarations (tests.test_adapter_contract.AdapterContractTest) ... ok
test_strict_parity_cannot_overstate_degraded_or_unsupported_state (tests.test_adapter_contract.AdapterContractTest) ... ok
test_synthetic_adapter_has_no_first_party_dependency (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unknown_capability_and_status_are_rejected (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unknown_tier_and_unmapped_catalog_tier_are_reported (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unsupported_capability_is_visible (tests.test_adapter_contract.AdapterContractTest) ... ok

----------------------------------------------------------------------
Ran 19 tests in 0.132s

OK
```

### Full regression, CLI, static, and no-live-change proof

The full suite result was:

```text
Ran 50 tests in 10.078s

OK
```

The three valid contract commands returned:

```text
claude adapter contract valid
codex adapter contract valid
example adapter contract valid
```

The named selector `../claude` was rejected by `argparse` with exit 2. The
extension command using `--adapter-path tests/fixtures/adapters/example`
remained valid. `py_compile`, every Task 1 JSON parse, and `git diff --check`
all exited zero.

A second fresh inventory remained byte-identical to the frozen baseline:

```text
8d943deaa440a279452e3af79400c6651722306936d2d90922692810722ddf27  docs/baselines/claude-codex-baseline.json
8d943deaa440a279452e3af79400c6651722306936d2d90922692810722ddf27  <temporary>/live-baseline.json
native homes: real directories, not symlinks
historical top-level directories:
archive-20260820-121406
archive-20260820-122621
snapshot-20260820-092749
snapshot-20260820-092901
snapshot-20260820-093002
snapshot-20260820-093104
snapshot-20260820-094710
snapshot-20260820-101106
snapshot-20260820-105637
snapshot-20260820-113207
adapter runtime current links: none
```

All three checked-in matrices now declare exactly all 13 catalog IDs. Codex's
`before_compaction` entry retains explicit native PreCompact evidence. Current
implementation gaps are marked `degraded` or `unsupported` with false strict
parity and concrete impact rather than being silently omitted. Nothing was
activated, linked, removed, or pushed.

## Independent-review fix round 2 (2026-08-20)

The second review found that POSIX normalization alone still accepted Windows-
ambiguous ownership spellings, the Codex matrix described harness mechanisms as
implemented behavior, and the model-value schema used a permissive whitespace
pattern whose semantics could differ across JSON Schema engines.

### RED

Command:

```text
PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract -v
```

Exact result: 23 tests executed with 20 failures in 0.133 seconds. Existing
contract tests remained green. The failures were:

```text
8 Codex implementation-truth failures
  global_guidance: native, expected degraded|unsupported
  skill_catalog: native, expected degraded|unsupported
  session_start: native, expected degraded|unsupported
  stop_capture: native, expected degraded|unsupported
  before_compaction: native, expected degraded|unsupported
  post_tool_use: native, expected degraded|unsupported
  subagent_start: native, expected degraded|unsupported
  schedules: native, expected degraded|unsupported

3 schema/model-loader grammar failures
  ' padded': schema helper returned no error
  'padded ': schema helper returned no error
  'model/id': schema helper returned no error

8 cross-platform ownership failures
  'hooks\\start': AdapterContractError not raised
  'hooks\\..\\outside': AdapterContractError not raised
  'C:/hooks/start': AdapterContractError not raised
  'C:\\hooks\\start': AdapterContractError not raised
  '\\\\server\\share\\hook': AdapterContractError not raised
  '\\\\?\\C:\\hooks\\start': AdapterContractError not raised
  '\\\\.\\pipe\\kingstack': AdapterContractError not raised
  'hooks:alternate/start': AdapterContractError not raised

1 alias-bypass failure
  ['hooks/start', 'hooks\\start']: AdapterContractError not raised
```

The newline and CRLF model-ID cases already failed closed under the prior
internal full-match implementation. They remained in the unchanged test so the
switch to JSON Schema search semantics could not reopen them.

### Focused GREEN

Command and unabridged result:

```text
$ PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract -v
test_capability_matrix_must_cover_catalog_exactly (tests.test_adapter_contract.AdapterContractTest) ... ok
test_catalog_rejects_boolean_version_and_unstable_ids (tests.test_adapter_contract.AdapterContractTest) ... ok
test_codex_matrix_reports_implementation_truth_not_available_mechanisms (tests.test_adapter_contract.AdapterContractTest) ... ok
test_contract_cli_accepts_named_and_synthetic_adapters (tests.test_adapter_contract.AdapterContractTest) ... ok
test_contract_cli_requires_exactly_one_adapter_selector (tests.test_adapter_contract.AdapterContractTest) ... ok
test_every_non_native_state_requires_evidence_and_impact (tests.test_adapter_contract.AdapterContractTest) ... ok
test_model_mapping_exact_id_grammar_matches_schema_helper (tests.test_adapter_contract.AdapterContractTest) ... ok
test_model_mapping_rejects_whitespace_only_values (tests.test_adapter_contract.AdapterContractTest) ... ok
test_named_adapter_selector_must_match_loaded_id (tests.test_adapter_contract.AdapterContractTest) ... ok
test_named_adapter_selector_rejects_path_syntax (tests.test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_are_canonical_before_duplicate_and_root_checks (tests.test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_duplicates_absolute_paths_and_home_root (tests.test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_lossy_or_backtracking_spelling (tests.test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_windows_ambiguous_spellings (tests.test_adapter_contract.AdapterContractTest) ... ok
test_render_module_must_be_an_importable_shape (tests.test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_reject_unknown_top_level_key (tests.test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_validation_agree_on_checked_in_declarations (tests.test_adapter_contract.AdapterContractTest) ... ok
test_strict_parity_cannot_overstate_degraded_or_unsupported_state (tests.test_adapter_contract.AdapterContractTest) ... ok
test_synthetic_adapter_has_no_first_party_dependency (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unknown_capability_and_status_are_rejected (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unknown_tier_and_unmapped_catalog_tier_are_reported (tests.test_adapter_contract.AdapterContractTest) ... ok
test_unsupported_capability_is_visible (tests.test_adapter_contract.AdapterContractTest) ... ok
test_windows_alias_cannot_bypass_duplicate_ownership (tests.test_adapter_contract.AdapterContractTest) ... ok

----------------------------------------------------------------------
Ran 23 tests in 0.156s

OK
```

The path tests additionally cover Windows reserved device names, trailing dot
or space components, and case-fold aliases. The model tests exercise padded,
newline, CRLF, slash-containing, and valid mixed vendor IDs against both the
schema helper and `load_adapter`.

### Full, CLI, static, and no-live-change proof

```text
$ PYTHONPATH=lib python3 -m unittest discover -s tests -v
Ran 54 tests in 6.490s

OK

$ ./scripts/kingstack check --contract --adapter claude
claude adapter contract valid
$ ./scripts/kingstack check --contract --adapter codex
codex adapter contract valid
$ ./scripts/kingstack check --contract --adapter-path tests/fixtures/adapters/example
example adapter contract valid
```

`py_compile`, every Task 1 JSON parse, and `git diff --check` exited zero. The
fresh native inventory remained byte-identical to the frozen baseline:

```text
8d943deaa440a279452e3af79400c6651722306936d2d90922692810722ddf27  docs/baselines/claude-codex-baseline.json
8d943deaa440a279452e3af79400c6651722306936d2d90922692810722ddf27  <temporary>/live-baseline.json
native homes: real directories, not symlinks
historical count: 10
adapter runtime current links: none
```

Codex now reports all not-yet-staged behavior as unsupported with strict parity
false. Each lifecycle entry says that the native mechanism is available while
the kingstack handler has not been staged or replay-proven. In particular,
PreCompact availability remains documented without claiming that kingstack's
checkpoint behavior exists today. Nothing was activated, linked, removed, or
pushed.

### Schema-search semantics addendum

The implementation was then switched from Python full-match semantics to JSON
Schema search semantics. A focused test demonstrated that the other anchored
contract-ID patterns still accepted a final newline because `$` can match
before a line terminator:

```text
$ PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract.AdapterContractTest.test_schema_search_semantics_reject_line_terminated_contract_ids -v
test_schema_search_semantics_reject_line_terminated_contract_ids (tests.test_adapter_contract.AdapterContractTest) ... FAIL

======================================================================
FAIL: test_schema_search_semantics_reject_line_terminated_contract_ids (tests.test_adapter_contract.AdapterContractTest)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_adapter_contract.py", line 228, in test_schema_search_semantics_reject_line_terminated_contract_ids
    load_adapter(adapter_path)
AssertionError: AdapterContractError not raised

----------------------------------------------------------------------
Ran 1 test in 0.014s

FAILED (failures=1)
```

All contract string-ID patterns now include an ECMA-compatible negative newline
guard. Final focused and full results after that correction:

```text
$ PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract -v
Ran 24 tests in 0.168s

OK

$ PYTHONPATH=lib python3 -m unittest discover -s tests -v
Ran 55 tests in 6.704s

OK

claude adapter contract valid
codex adapter contract valid
example adapter contract valid
```

All compile, JSON parse, diff, and no-live-change checks remained green.

## Independent-review fix round 3 (2026-08-20)

The third review found one remaining grouped ownership-boundary defect: the
contract did not collapse canonically equivalent Unicode, reject control
characters, or recognize Windows COM/LPT device names that use superscript
digits.

### RED

Command:

```text
PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract -v
```

Exact result: 27 tests executed with 13 failures in 0.197 seconds. The failures
were six missing C0/DEL rejections (`U+0000`, LF, CR, tab, `U+001F`, `U+007F`),
six missing superscript device-name rejections (`COM¹`, `com².txt`, `CoM³.log`,
`LPT¹`, `lpt².md`, `LpT³`), and one canonical-storage failure:

```text
FAIL: test_owned_paths_store_nfc_and_unicode_equivalents_collide
AssertionError: Tuples differ: ('é/file',) != ('é/file',)

First differing element 0:
'é/file'
'é/file'

Ran 27 tests in 0.197s
FAILED (failures=13)
```

### GREEN and full verification

```text
$ PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract -v
Ran 27 tests in 0.134s

OK

$ PYTHONPATH=lib python3 -m unittest discover -s tests -v
Ran 58 tests in 7.076s

OK

$ ./scripts/kingstack check --contract --adapter claude
claude adapter contract valid
$ ./scripts/kingstack check --contract --adapter codex
codex adapter contract valid
$ ./scripts/kingstack check --contract --adapter-path tests/fixtures/adapters/example
example adapter contract valid
```

`py_compile`, every Task 1 JSON parse, and `git diff --check` exited zero. The
fresh inventory remained byte-identical to the frozen baseline:

```text
8d943deaa440a279452e3af79400c6651722306936d2d90922692810722ddf27  docs/baselines/claude-codex-baseline.json
8d943deaa440a279452e3af79400c6651722306936d2d90922692810722ddf27  <temporary>/live-baseline.json
native homes: real directories, not symlinks
historical count: 10
adapter runtime current links: none
```

Every accepted ownership string is normalized to NFC before POSIX
canonicalization, canonical storage, and casefold duplicate comparison. C0 and
DEL controls are rejected. Windows device detection now covers ASCII digits and
superscript `¹²³`, including extensions and mixed case. Unicode remains allowed
generally; format controls were not broadened without evidence. Nothing was
activated, linked, removed, or pushed.
