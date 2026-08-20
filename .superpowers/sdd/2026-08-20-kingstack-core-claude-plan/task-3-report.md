# Core Task 3 implementation report

Append-only evidence log.

## Implementation result (2026-08-20)

Base: `8ad1306`

- Added the exact four-work-class portable routing policy with no adapter or
  model names.
- Moved native model mappings and deterministic adjacent fallback edges into
  adapter-owned `models.json` documents referenced by each declaration.
- Added an immutable, path-independent routing compiler plus read-only
  `resolve()` and `fallback()` entry points. Decisions include the adapter,
  work class or source tier, chosen tier/model/effort where applicable, and
  evidence/reason.
- Added injected, tier-scoped private availability overrides. Checked-in policy
  and model maps reject availability state and never read a runtime-state path.
- Replaced shared vendor-specific routing prose with portable work classes,
  explicit model/effort reporting, one adjacent availability fallback, and the
  unchanged context thresholds. Claude model names, `/model`, `/clear`, and its
  ruler path now live only in the Claude appendix.
- Updated Codex's capability matrix from unsupported to emulated strict parity
  now that its portable resolver and rendered guidance are behaviorally proven.
- Preserved pure in-memory bundle rendering. No destination writer, staging
  tree, release materialization, activation, native-home write, or schedule
  change was added.

### Initial RED

Command:

```text
PYTHONPATH=lib python3 -m unittest tests.test_routing -v
```

Unabridged output before any production/config/prose implementation:

```text
test_routing (unittest.loader._FailedTest) ... ERROR

======================================================================
ERROR: test_routing (unittest.loader._FailedTest)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_routing
Traceback (most recent call last):
  File "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/unittest/loader.py", line 154, in loadTestsFromName
    module = __import__(module_name)
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 7, in <module>
    from kingstack.routing import (
ModuleNotFoundError: No module named 'kingstack.routing'


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

The missing routing module was the intended failure and occurred before any
production file was created.

### Adversarial selector RED

After the first GREEN, a malformed-selector case proved that an unhashable work
class leaked `TypeError` rather than the stable routing boundary.

```text
test_availability_overrides_reject_ambiguous_and_malformed_records (tests.test_routing.RoutingTest)
Two private choices for a tier or malformed values must fail. ... ok
test_checked_in_policy_is_exactly_portable (tests.test_routing.RoutingTest)
A vendor token or extra policy field must make this contract fail. ... ok
test_fallback_graph_rejects_duplicates_ambiguity_nonadjacency_and_cycles (tests.test_routing.RoutingTest)
Any graph that permits zero, two, or cyclic fallback choices must fail. ... ok
test_fallback_is_one_adjacent_step_with_a_stable_reason (tests.test_routing.RoutingTest)
Skipping a tier, using a vendor-global override, or varying output must fail. ... ok
test_model_map_must_exactly_match_declaration_and_known_tiers (tests.test_routing.RoutingTest)
A missing, extra, malformed, or declaration-divergent tier must fail. ... ok
test_policy_rejects_unknown_keys_types_and_nonportable_values (tests.test_routing.RoutingTest)
Schema drift or model syntax in shared policy must fail at compile time. ... ok
test_private_availability_override_is_injected_and_tier_scoped (tests.test_routing.RoutingTest)
Ignoring or leaking a runtime-only alternate model must fail. ... ok
test_resolve_maps_both_adapters_and_returns_explainable_immutable_data (tests.test_routing.RoutingTest)
A wrong model, effort, tier, class, or missing evidence must fail. ... ok
test_unknown_work_class_and_tier_fail_visibly (tests.test_routing.RoutingTest)
Silently defaulting an unknown selector must fail. ... ERROR

======================================================================
ERROR: test_unknown_work_class_and_tier_fail_visibly (tests.test_routing.RoutingTest)
Silently defaulting an unknown selector must fail.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 151, in test_unknown_work_class_and_tier_fail_visibly
    resolve("codex", [], root=ROOT)
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 322, in resolve
    return load_routing(adapter, root).resolve(work_class, availability_overrides)
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 201, in resolve
    if work_class not in self.policy:
TypeError: unhashable type: 'list'

----------------------------------------------------------------------
Ran 9 tests in 0.028s

FAILED (errors=1)
```

The minimal fix validates selector type/grammar before lookup.

### Focused GREEN

Command:

```text
PYTHONPATH=lib python3 -m unittest tests.test_routing -v
```

Unabridged final output:

```text
test_availability_overrides_reject_ambiguous_and_malformed_records (tests.test_routing.RoutingTest)
Two private choices for a tier or malformed values must fail. ... ok
test_checked_in_policy_is_exactly_portable (tests.test_routing.RoutingTest)
A vendor token or extra policy field must make this contract fail. ... ok
test_fallback_graph_rejects_duplicates_ambiguity_nonadjacency_and_cycles (tests.test_routing.RoutingTest)
Any graph that permits zero, two, or cyclic fallback choices must fail. ... ok
test_fallback_is_one_adjacent_step_with_a_stable_reason (tests.test_routing.RoutingTest)
Skipping a tier, using a vendor-global override, or varying output must fail. ... ok
test_model_map_must_exactly_match_declaration_and_known_tiers (tests.test_routing.RoutingTest)
A missing, extra, malformed, or declaration-divergent tier must fail. ... ok
test_policy_rejects_unknown_keys_types_and_nonportable_values (tests.test_routing.RoutingTest)
Schema drift or model syntax in shared policy must fail at compile time. ... ok
test_private_availability_override_is_injected_and_tier_scoped (tests.test_routing.RoutingTest)
Ignoring or leaking a runtime-only alternate model must fail. ... ok
test_resolve_maps_both_adapters_and_returns_explainable_immutable_data (tests.test_routing.RoutingTest)
A wrong model, effort, tier, class, or missing evidence must fail. ... ok
test_unknown_work_class_and_tier_fail_visibly (tests.test_routing.RoutingTest)
Silently defaulting an unknown selector must fail. ... ok

----------------------------------------------------------------------
Ran 9 tests in 0.084s

OK
```

### Focused routing, contract, and render regression

Command:

```text
PYTHONPATH=lib python3 -m unittest tests.test_routing tests.test_adapter_contract tests.test_instruction_render -v
```

Result: 51 tests ran, all passed. The render regression retains the frozen
Task 2 baseline and removes only the old routing section plus the new Claude
appendix before byte-comparing the complete unchanged remainder.

### Full suite

Command:

```text
PYTHONPATH=lib python3 -m unittest discover -s tests -v
```

Unabridged final output:

```text
test_capability_matrix_must_cover_catalog_exactly (test_adapter_contract.AdapterContractTest) ... ok
test_catalog_rejects_boolean_version_and_unstable_ids (test_adapter_contract.AdapterContractTest) ... ok
test_codex_matrix_reports_implementation_truth_not_available_mechanisms (test_adapter_contract.AdapterContractTest) ... ok
test_contract_cli_accepts_named_and_synthetic_adapters (test_adapter_contract.AdapterContractTest) ... ok
test_contract_cli_requires_exactly_one_adapter_selector (test_adapter_contract.AdapterContractTest) ... ok
test_every_non_native_state_requires_evidence_and_impact (test_adapter_contract.AdapterContractTest) ... ok
test_model_mapping_exact_id_grammar_matches_schema_helper (test_adapter_contract.AdapterContractTest) ... ok
test_model_mapping_rejects_whitespace_only_values (test_adapter_contract.AdapterContractTest) ... ok
test_named_adapter_selector_must_match_loaded_id (test_adapter_contract.AdapterContractTest) ... ok
test_named_adapter_selector_rejects_path_syntax (test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_are_canonical_before_duplicate_and_root_checks (test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_c0_and_del_controls (test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_duplicates_absolute_paths_and_home_root (test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_lossy_or_backtracking_spelling (test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_superscript_windows_device_names (test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_reject_windows_ambiguous_spellings (test_adapter_contract.AdapterContractTest) ... ok
test_owned_paths_store_nfc_and_unicode_equivalents_collide (test_adapter_contract.AdapterContractTest) ... ok
test_render_module_must_be_an_importable_shape (test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_reject_unknown_top_level_key (test_adapter_contract.AdapterContractTest) ... ok
test_schema_and_python_validation_agree_on_checked_in_declarations (test_adapter_contract.AdapterContractTest) ... ok
test_schema_search_semantics_reject_line_terminated_contract_ids (test_adapter_contract.AdapterContractTest) ... ok
test_strict_parity_cannot_overstate_degraded_or_unsupported_state (test_adapter_contract.AdapterContractTest) ... ok
test_synthetic_adapter_has_no_first_party_dependency (test_adapter_contract.AdapterContractTest) ... ok
test_unknown_capability_and_status_are_rejected (test_adapter_contract.AdapterContractTest) ... ok
test_unknown_tier_and_unmapped_catalog_tier_are_reported (test_adapter_contract.AdapterContractTest) ... ok
test_unsupported_capability_is_visible (test_adapter_contract.AdapterContractTest) ... ok
test_windows_alias_cannot_bypass_duplicate_ownership (test_adapter_contract.AdapterContractTest) ... ok
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
test_claude_render_changes_only_the_intentional_routing_section (test_instruction_render.InstructionRenderTest) ... ok
test_cli_rejects_output_conflicts_unknown_paths_and_mismatch (test_instruction_render.InstructionRenderTest) ... ok
test_declaration_dispatches_synthetic_provider_without_core_change (test_instruction_render.InstructionRenderTest) ... ok
test_duplicate_missing_and_unlisted_fragments_are_rejected (test_instruction_render.InstructionRenderTest) ... ok
test_frozen_fixture_matches_recorded_baseline_hash (test_instruction_render.InstructionRenderTest) ... ok
test_invalid_utf8_and_newline_discipline_are_rejected (test_instruction_render.InstructionRenderTest) ... ok
test_late_source_directory_swap_is_detected (test_instruction_render.InstructionRenderTest) ... ok
test_missing_or_invalid_provider_entrypoint_is_rejected (test_instruction_render.InstructionRenderTest) ... ok
test_mutable_staging_api_and_production_references_are_absent (test_instruction_render.InstructionRenderTest) ... ok
test_order_lists_every_fragment_once (test_instruction_render.InstructionRenderTest) ... ok
test_provider_output_must_be_bytes_canonical_and_owned (test_instruction_render.InstructionRenderTest) ... ok
test_provider_output_reuses_full_portable_path_contract (test_instruction_render.InstructionRenderTest) ... ok
test_provider_output_stores_nfc_and_rejects_portable_aliases (test_instruction_render.InstructionRenderTest) ... ok
test_render_and_all_cli_selectors_write_nothing (test_instruction_render.InstructionRenderTest) ... ok
test_symlinked_sources_and_adapter_traversal_are_rejected (test_instruction_render.InstructionRenderTest) ... ok
test_capture_excludes_sensitive_paths_at_every_depth (test_inventory.InventoryTest)
Hashing a secret in an included directory would publish its fingerprint. ... ok
test_capture_is_deterministic_and_redacts_config_values (test_inventory.InventoryTest)
Changing a config scalar must never expose it in the public report. ... ok
test_capture_records_symlink_mode_and_file_hash (test_inventory.InventoryTest)
Dereferencing a symlink or losing its executable mode corrupts a baseline. ... ok
test_capture_redacts_absolute_symlink_targets (test_inventory.InventoryTest)
An absolute symlink target would disclose a home path in the report. ... ok
test_capture_redacts_path_shaped_json_key_names (test_inventory.InventoryTest)
A path-shaped JSON key must not reveal a home path as report metadata. ... ok
test_cli_writes_fixture_inventory_and_rejects_agent_home_output (test_inventory.InventoryTest)
A CLI regression must not write a report under a protected agent home. ... ok
test_committed_atomic_write_survives_temp_unlink_error_after_cleanup (test_inventory.InventoryTest) ... ok
test_write_public_report_is_byte_deterministic_and_rejects_private_destinations (test_inventory.InventoryTest)
A public report must be repeatable and never land in agent-private storage. ... ok
test_write_public_report_refuses_symlinked_parent_and_existing_file (test_inventory.InventoryTest) ... ok
test_write_public_report_supports_real_macos_mktemp_var_alias (test_inventory.InventoryTest) ... ok
test_defaults_are_agent_neutral_and_runtime_is_outside_repo (test_paths.PathsTest) ... ok
test_availability_overrides_reject_ambiguous_and_malformed_records (test_routing.RoutingTest)
Two private choices for a tier or malformed values must fail. ... ok
test_checked_in_policy_is_exactly_portable (test_routing.RoutingTest)
A vendor token or extra policy field must make this contract fail. ... ok
test_fallback_graph_rejects_duplicates_ambiguity_nonadjacency_and_cycles (test_routing.RoutingTest)
Any graph that permits zero, two, or cyclic fallback choices must fail. ... ok
test_fallback_is_one_adjacent_step_with_a_stable_reason (test_routing.RoutingTest)
Skipping a tier, using a vendor-global override, or varying output must fail. ... ok
test_model_map_must_exactly_match_declaration_and_known_tiers (test_routing.RoutingTest)
A missing, extra, malformed, or declaration-divergent tier must fail. ... ok
test_policy_rejects_unknown_keys_types_and_nonportable_values (test_routing.RoutingTest)
Schema drift or model syntax in shared policy must fail at compile time. ... ok
test_private_availability_override_is_injected_and_tier_scoped (test_routing.RoutingTest)
Ignoring or leaking a runtime-only alternate model must fail. ... ok
test_resolve_maps_both_adapters_and_returns_explainable_immutable_data (test_routing.RoutingTest)
A wrong model, effort, tier, class, or missing evidence must fail. ... ok
test_unknown_work_class_and_tier_fail_visibly (test_routing.RoutingTest)
Silently defaulting an unknown selector must fail. ... ok

----------------------------------------------------------------------
Ran 82 tests in 13.298s

OK
```

### Static, CLI, and foreign-name evidence

Commands covered `py_compile`, every Task 3 JSON document, `git diff --check`,
both exact foreign-name scans, three contract selectors, and both pure bundle
manifests. Unabridged output:

```text
py_compile: clean
json: core/routing/policy.json clean
json: adapters/claude/models.json clean
json: adapters/codex/models.json clean
json: adapters/claude/adapter.json clean
json: adapters/codex/adapter.json clean
git diff --check: clean
claude foreign-name scan: clean
codex foreign-name scan: clean
claude adapter contract valid
codex adapter contract valid
example adapter contract valid
{
  "adapter": "claude",
  "files": [
    {
      "path": "CLAUDE.md",
      "sha256": "0792f1a7fd19f92db0d04a27ca47927bc37114ca8ab07a11e9b00c01b8d01107",
      "size": 10337
    }
  ],
  "schema_version": 1
}
{
  "adapter": "codex",
  "files": [
    {
      "path": "AGENTS.md",
      "sha256": "4bb4d923aa0fed97867a5020c2072776787c05cc0521bee23eac5872cfa010df",
      "size": 9887
    }
  ],
  "schema_version": 1
}
```

The exact scans were:

```text
! ./scripts/kingstack render --adapter claude --print-file CLAUDE.md | rg -i 'gpt-5\.6-(sol|terra|luna)'
! ./scripts/kingstack render --adapter codex --print-file AGENTS.md | rg -i '\b(haiku|sonnet|opus|fable)\b'
```

### Native no-change evidence

Fresh hashes were compared to the previously approved baseline values, native
home types were checked without following links, and both possible adapter
activation links were checked explicitly. Unabridged output:

```text
/Users/mac/.claude/CLAUDE.md: unchanged sha256=7a6f34e0ff3777279053bb63713dfc109761d508f18fef0316279e9a74fdab2e
/Users/mac/.claude/settings.json: unchanged sha256=d68a1b364130ec36f9bde97e6926f02040d455b217352e367da6aa5b51c8477b
/Users/mac/.codex/config.toml: unchanged sha256=ef83efb8a9b49180aae027805422ac039888b08bff8671a8c2038ef22cc18b14
/Users/mac/.claude: real Directory
/Users/mac/.codex: real Directory
/Users/mac/.kingstack/adapters/claude/current: absent (no activation link)
/Users/mac/.kingstack/adapters/codex/current: absent (no activation link)
native/live type-link proof: clean
```

No path under `~/.claude`, `~/.codex`, or `~/.kingstack` was created,
rewritten, renamed, linked, activated, or removed. Nothing was pushed.

## Independent review fix round 1 (2026-08-20)

Base: `8ce2975`

The review reproduced two validation-boundary failures: non-string unknown
keys could escape as diagnostic-formatting `TypeError`, and the waiting branch
returned before validating caller-supplied availability overrides. The fix
validates key types before formatting and validates overrides before the
no-model early return. Valid routing decisions and rendered bytes are unchanged.

### RED

Command:

```text
PYTHONPATH=lib python3 -m unittest tests.test_routing -v
```

Unabridged output before the production fix:

```text
test_availability_overrides_reject_ambiguous_and_malformed_records (tests.test_routing.RoutingTest)
Two private choices for a tier or malformed values must fail. ... ok
test_checked_in_policy_is_exactly_portable (tests.test_routing.RoutingTest)
A vendor token or extra policy field must make this contract fail. ... ok
test_fallback_graph_rejects_duplicates_ambiguity_nonadjacency_and_cycles (tests.test_routing.RoutingTest)
Any graph that permits zero, two, or cyclic fallback choices must fail. ... ok
test_fallback_is_one_adjacent_step_with_a_stable_reason (tests.test_routing.RoutingTest)
Skipping a tier, using a vendor-global override, or varying output must fail. ... ok
test_model_map_must_exactly_match_declaration_and_known_tiers (tests.test_routing.RoutingTest)
A missing, extra, malformed, or declaration-divergent tier must fail. ... ok
test_non_string_unknown_keys_raise_stable_routing_errors (tests.test_routing.RoutingTest)
Diagnostic formatting must never leak TypeError for malformed keys. ... test_policy_rejects_unknown_keys_types_and_nonportable_values (tests.test_routing.RoutingTest)
Schema drift or model syntax in shared policy must fail at compile time. ... ok
test_private_availability_override_is_injected_and_tier_scoped (tests.test_routing.RoutingTest)
Ignoring or leaking a runtime-only alternate model must fail. ... ok
test_resolve_maps_both_adapters_and_returns_explainable_immutable_data (tests.test_routing.RoutingTest)
A wrong model, effort, tier, class, or missing evidence must fail. ... ok
test_unknown_work_class_and_tier_fail_visibly (tests.test_routing.RoutingTest)
Silently defaulting an unknown selector must fail. ... ok
test_waiting_validates_malformed_and_ambiguous_availability_overrides (tests.test_routing.RoutingTest)
The no-model branch must not bypass caller-supplied validation. ...

======================================================================
ERROR: test_non_string_unknown_keys_raise_stable_routing_errors (tests.test_routing.RoutingTest) (label='policy route')
Diagnostic formatting must never leak TypeError for malformed keys.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 238, in test_non_string_unknown_keys_raise_stable_routing_errors
    operation()
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 196, in <lambda>
    lambda: routing_from_documents(
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 287, in routing_from_documents
    policy = _validate_policy(policy_document)
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 64, in _validate_policy
    _require_exact_keys(route, {"tier", "effort"}, "policy work class '{}'".format(work_class))
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 49, in _require_exact_keys
    details.append("unknown keys {}".format(", ".join(extra)))
TypeError: sequence item 0: expected str instance, int found

======================================================================
ERROR: test_non_string_unknown_keys_raise_stable_routing_errors (tests.test_routing.RoutingTest) (label='model top level')
Diagnostic formatting must never leak TypeError for malformed keys.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 238, in test_non_string_unknown_keys_raise_stable_routing_errors
    operation()
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 204, in <lambda>
    lambda: routing_from_documents(
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 288, in routing_from_documents
    model_tiers, fallbacks = _validate_model_map(model_document, declaration)
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 95, in _validate_model_map
    _require_exact_keys(document, MODEL_MAP_KEYS, "adapter model map")
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 49, in _require_exact_keys
    details.append("unknown keys {}".format(", ".join(extra)))
TypeError: sequence item 0: expected str instance, int found

======================================================================
ERROR: test_non_string_unknown_keys_raise_stable_routing_errors (tests.test_routing.RoutingTest) (label='fallback record')
Diagnostic formatting must never leak TypeError for malformed keys.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 238, in test_non_string_unknown_keys_raise_stable_routing_errors
    operation()
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 212, in <lambda>
    lambda: routing_from_documents(
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 288, in routing_from_documents
    model_tiers, fallbacks = _validate_model_map(model_document, declaration)
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 126, in _validate_model_map
    _require_exact_keys(record, FALLBACK_KEYS, label)
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 49, in _require_exact_keys
    details.append("unknown keys {}".format(", ".join(extra)))
TypeError: sequence item 0: expected str instance, int found

======================================================================
ERROR: test_non_string_unknown_keys_raise_stable_routing_errors (tests.test_routing.RoutingTest) (label='availability override')
Diagnostic formatting must never leak TypeError for malformed keys.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 238, in test_non_string_unknown_keys_raise_stable_routing_errors
    operation()
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 220, in <lambda>
    lambda: resolve(
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 329, in resolve
    return load_routing(adapter, root).resolve(work_class, availability_overrides)
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 223, in resolve
    overrides = _validate_overrides(availability_overrides)
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 173, in _validate_overrides
    _require_exact_keys(record, OVERRIDE_KEYS, label)
  File "/Users/mac/Desktop/Work/kingstack/lib/kingstack/routing.py", line 49, in _require_exact_keys
    details.append("unknown keys {}".format(", ".join(extra)))
TypeError: sequence item 0: expected str instance, int found

======================================================================
FAIL: test_waiting_validates_malformed_and_ambiguous_availability_overrides (tests.test_routing.RoutingTest) (message='model ID')
The no-model branch must not bypass caller-supplied validation.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 338, in test_waiting_validates_malformed_and_ambiguous_availability_overrides
    resolve(
AssertionError: RoutingError not raised

======================================================================
FAIL: test_waiting_validates_malformed_and_ambiguous_availability_overrides (tests.test_routing.RoutingTest) (message='ambiguous')
The no-model branch must not bypass caller-supplied validation.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/mac/Desktop/Work/kingstack/tests/test_routing.py", line 338, in test_waiting_validates_malformed_and_ambiguous_availability_overrides
    resolve(
AssertionError: RoutingError not raised

----------------------------------------------------------------------
Ran 11 tests in 0.035s

FAILED (failures=2, errors=4)
```

### GREEN

Command:

```text
PYTHONPATH=lib python3 -m unittest tests.test_routing -v
```

Unabridged output after the minimal production fix:

```text
test_availability_overrides_reject_ambiguous_and_malformed_records (tests.test_routing.RoutingTest)
Two private choices for a tier or malformed values must fail. ... ok
test_checked_in_policy_is_exactly_portable (tests.test_routing.RoutingTest)
A vendor token or extra policy field must make this contract fail. ... ok
test_fallback_graph_rejects_duplicates_ambiguity_nonadjacency_and_cycles (tests.test_routing.RoutingTest)
Any graph that permits zero, two, or cyclic fallback choices must fail. ... ok
test_fallback_is_one_adjacent_step_with_a_stable_reason (tests.test_routing.RoutingTest)
Skipping a tier, using a vendor-global override, or varying output must fail. ... ok
test_model_map_must_exactly_match_declaration_and_known_tiers (tests.test_routing.RoutingTest)
A missing, extra, malformed, or declaration-divergent tier must fail. ... ok
test_non_string_unknown_keys_raise_stable_routing_errors (tests.test_routing.RoutingTest)
Diagnostic formatting must never leak TypeError for malformed keys. ... ok
test_policy_rejects_unknown_keys_types_and_nonportable_values (tests.test_routing.RoutingTest)
Schema drift or model syntax in shared policy must fail at compile time. ... ok
test_private_availability_override_is_injected_and_tier_scoped (tests.test_routing.RoutingTest)
Ignoring or leaking a runtime-only alternate model must fail. ... ok
test_resolve_maps_both_adapters_and_returns_explainable_immutable_data (tests.test_routing.RoutingTest)
A wrong model, effort, tier, class, or missing evidence must fail. ... ok
test_unknown_work_class_and_tier_fail_visibly (tests.test_routing.RoutingTest)
Silently defaulting an unknown selector must fail. ... ok
test_waiting_validates_malformed_and_ambiguous_availability_overrides (tests.test_routing.RoutingTest)
The no-model branch must not bypass caller-supplied validation. ... ok

----------------------------------------------------------------------
Ran 11 tests in 0.017s

OK
```

### Fix-round verification

- Focused routing + contract + render: 53/53 passed.
- Full suite: 84/84 passed.
- `py_compile`, five Task 3 JSON parses, `git diff --check`, both foreign-name
  scans, three contract CLI selectors, and both pure render manifests passed.
- Claude and Codex manifest hashes remained
  `0792f1a7fd19f92db0d04a27ca47927bc37114ca8ab07a11e9b00c01b8d01107`
  and `4bb4d923aa0fed97867a5020c2072776787c05cc0521bee23eac5872cfa010df`.
- Live Claude guidance/settings and Codex config hashes remained unchanged;
  both native homes remained real directories and both adapter `current` links
  remained absent. No live path was changed and nothing was pushed.
