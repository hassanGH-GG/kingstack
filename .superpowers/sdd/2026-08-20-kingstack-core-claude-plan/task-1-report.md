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
