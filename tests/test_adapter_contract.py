import io
import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import TestCase

from kingstack.adapter_contract import (
    ADAPTER_SCHEMA,
    AdapterContractError,
    CapabilityMatrix,
    CapabilityState,
    compare_capabilities,
    load_adapter,
    load_capability_catalog,
    _schema_errors,
    validate_adapter,
)
from kingstack.cli import _load_selected_adapter, main


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests/fixtures"
CATALOG_PATH = ROOT / "core/capabilities/catalog.json"
EXACT_FIELDS = {
    "id",
    "contract_version",
    "render_module",
    "native_home",
    "owned_paths",
    "model_tiers",
    "capability_matrix",
}


class AdapterContractTest(TestCase):
    def catalog(self):
        return load_capability_catalog(CATALOG_PATH)

    def write_adapter(self, payload):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(directory))
        path = directory / "adapter.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        (directory / "capabilities.json").write_bytes(
            (FIXTURES / "adapters/example/capabilities.json").read_bytes()
        )
        return path

    def valid_payload(self):
        return json.loads(
            (FIXTURES / "adapters/example/adapter.json").read_text(encoding="utf-8")
        )

    def test_synthetic_adapter_has_no_first_party_dependency(self):
        adapter = load_adapter(FIXTURES / "adapters/example/adapter.json")

        self.assertEqual(validate_adapter(adapter, self.catalog()), [])
        self.assertNotIn("claude", adapter.render_module)
        self.assertNotIn("codex", adapter.render_module)
        self.assertEqual(set(adapter.raw), EXACT_FIELDS)

    def test_unsupported_capability_is_visible(self):
        matrix = CapabilityMatrix(
            adapter_id="example",
            states=(
                CapabilityState(
                    capability="before_compaction",
                    status="unsupported",
                    evidence="The example harness exposes no pre-compaction event.",
                    impact="A session cannot preserve state immediately before compaction.",
                    strict_parity=False,
                ),
            ),
        )

        report = compare_capabilities({"before_compaction"}, matrix)

        self.assertEqual(report.unsupported, {"before_compaction"})
        self.assertFalse(report.strict_parity)

    def test_schema_and_python_reject_unknown_top_level_key(self):
        payload = self.valid_payload()
        payload["vendor"] = "example"

        with self.assertRaisesRegex(AdapterContractError, "unknown propert"):
            load_adapter(self.write_adapter(payload))

    def test_owned_paths_reject_duplicates_absolute_paths_and_home_root(self):
        invalid_sets = (
            (["hooks/start", "hooks/start"], "duplicate"),
            (["/tmp/start"], "relative"),
            (["."], "home root"),
            ([""], "empty"),
            (["../escape"], "backtracking"),
        )
        for owned_paths, message in invalid_sets:
            with self.subTest(owned_paths=owned_paths):
                payload = self.valid_payload()
                payload["owned_paths"] = owned_paths
                path = self.write_adapter(payload)
                with self.assertRaisesRegex(AdapterContractError, message):
                    load_adapter(path)

    def test_owned_paths_are_canonical_before_duplicate_and_root_checks(self):
        payload = self.valid_payload()
        payload["owned_paths"] = ["hooks/start", "hooks/./start"]
        with self.assertRaisesRegex(AdapterContractError, "duplicate"):
            load_adapter(self.write_adapter(payload))

        payload["owned_paths"] = ["./hooks/./start"]
        declaration = load_adapter(self.write_adapter(payload))
        self.assertEqual(declaration.owned_paths, ("hooks/start",))

        for path in (".", "./", "./."):
            with self.subTest(root=path):
                payload["owned_paths"] = [path]
                with self.assertRaisesRegex(AdapterContractError, "home root"):
                    load_adapter(self.write_adapter(payload))

    def test_owned_paths_reject_lossy_or_backtracking_spelling(self):
        for path, message in (
            ("hooks/start/", "trailing"),
            ("hooks//start", "empty"),
            ("../start", "backtracking"),
            ("hooks/../start", "backtracking"),
        ):
            with self.subTest(path=path):
                payload = self.valid_payload()
                payload["owned_paths"] = [path]
                with self.assertRaisesRegex(AdapterContractError, message):
                    load_adapter(self.write_adapter(payload))

    def test_owned_paths_reject_windows_ambiguous_spellings(self):
        for path in (
            r"hooks\start",
            r"hooks\..\outside",
            "C:/hooks/start",
            r"C:\hooks\start",
            r"\\server\share\hook",
            r"\\?\C:\hooks\start",
            r"\\.\pipe\kingstack",
            "hooks:alternate/start",
            "NUL",
            "hooks/CON.txt",
            "hooks/trailing.",
            "hooks/trailing ",
        ):
            with self.subTest(path=path):
                payload = self.valid_payload()
                payload["owned_paths"] = [path]
                with self.assertRaisesRegex(
                    AdapterContractError, "portable|Windows|drive|backslash"
                ):
                    load_adapter(self.write_adapter(payload))

    def test_windows_alias_cannot_bypass_duplicate_ownership(self):
        payload = self.valid_payload()
        payload["owned_paths"] = ["hooks/start", r"hooks\start"]

        with self.assertRaisesRegex(AdapterContractError, "backslash|portable"):
            load_adapter(self.write_adapter(payload))

        payload["owned_paths"] = ["Hooks/start", "hooks/start"]
        with self.assertRaisesRegex(AdapterContractError, "duplicate"):
            load_adapter(self.write_adapter(payload))

    def test_render_module_must_be_an_importable_shape(self):
        for value in ("claude", "bad-module.name", ".leading.dot", "trailing.dot."):
            with self.subTest(value=value):
                payload = self.valid_payload()
                payload["render_module"] = value
                with self.assertRaisesRegex(AdapterContractError, "render_module"):
                    load_adapter(self.write_adapter(payload))

    def test_unknown_tier_and_unmapped_catalog_tier_are_reported(self):
        payload = self.valid_payload()
        payload["model_tiers"] = {"economical": "example-small", "mystery": "x"}
        adapter = load_adapter(self.write_adapter(payload))

        errors = validate_adapter(adapter, self.catalog())

        self.assertTrue(any("unknown model tier 'mystery'" in error for error in errors))
        self.assertTrue(any("unmapped model tier 'balanced'" in error for error in errors))
        self.assertTrue(any("unmapped model tier 'frontier'" in error for error in errors))

    def test_model_mapping_rejects_whitespace_only_values(self):
        payload = self.valid_payload()
        payload["model_tiers"]["balanced"] = " \t "

        with self.assertRaisesRegex(AdapterContractError, "model_tiers"):
            load_adapter(self.write_adapter(payload))

    def test_model_mapping_exact_id_grammar_matches_schema_helper(self):
        adapter_schema = json.loads(ADAPTER_SCHEMA.read_text(encoding="utf-8"))
        model_schema = adapter_schema["properties"]["model_tiers"]["oneOf"][0]
        invalid_values = (" padded", "padded ", "model\n", "model\r\n", "model/id")

        for value in invalid_values:
            with self.subTest(value=repr(value)):
                self.assertTrue(_schema_errors({"balanced": value}, model_schema))
                payload = self.valid_payload()
                payload["model_tiers"]["balanced"] = value
                with self.assertRaisesRegex(AdapterContractError, "model_tiers"):
                    load_adapter(self.write_adapter(payload))

        self.assertEqual(
            _schema_errors(
                {"balanced": "gpt-5.6_terra", "frontier": "Opus-5"},
                model_schema,
            ),
            [],
        )

    def test_schema_search_semantics_reject_line_terminated_contract_ids(self):
        payload = self.valid_payload()
        payload["id"] = "example\n"
        adapter_path = self.write_adapter(payload)
        matrix = json.loads(
            (adapter_path.parent / "capabilities.json").read_text(encoding="utf-8")
        )
        matrix["adapter_id"] = "example\n"
        (adapter_path.parent / "capabilities.json").write_text(
            json.dumps(matrix), encoding="utf-8"
        )

        with self.assertRaisesRegex(AdapterContractError, "required pattern"):
            load_adapter(adapter_path)

    def test_unknown_capability_and_status_are_rejected(self):
        for mutation, message in (
            (("capability", "invented"), "unknown capability"),
            (("status", "partial"), "status"),
        ):
            with self.subTest(mutation=mutation):
                payload = self.valid_payload()
                matrix_path = self.write_adapter(payload).parent / "capabilities.json"
                matrix = json.loads(
                    (FIXTURES / "adapters/example/capabilities.json").read_text(
                        encoding="utf-8"
                    )
                )
                matrix["capabilities"][0][mutation[0]] = mutation[1]
                matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
                if mutation[0] == "status":
                    with self.assertRaisesRegex(AdapterContractError, message):
                        load_adapter(matrix_path.parent / "adapter.json")
                else:
                    declaration = load_adapter(matrix_path.parent / "adapter.json")
                    errors = validate_adapter(declaration, self.catalog())
                    self.assertTrue(any(message in error for error in errors))

    def test_every_non_native_state_requires_evidence_and_impact(self):
        for field in ("evidence", "impact"):
            with self.subTest(field=field):
                payload = self.valid_payload()
                adapter_path = self.write_adapter(payload)
                matrix = json.loads(
                    (FIXTURES / "adapters/example/capabilities.json").read_text(
                        encoding="utf-8"
                    )
                )
                matrix["capabilities"][0][field] = ""
                (adapter_path.parent / "capabilities.json").write_text(
                    json.dumps(matrix), encoding="utf-8"
                )
                with self.assertRaisesRegex(AdapterContractError, field):
                    load_adapter(adapter_path)

    def test_strict_parity_cannot_overstate_degraded_or_unsupported_state(self):
        payload = self.valid_payload()
        adapter_path = self.write_adapter(payload)
        matrix = json.loads(
            (FIXTURES / "adapters/example/capabilities.json").read_text(
                encoding="utf-8"
            )
        )
        matrix["capabilities"][0]["strict_parity"] = True
        (adapter_path.parent / "capabilities.json").write_text(
            json.dumps(matrix), encoding="utf-8"
        )

        with self.assertRaisesRegex(AdapterContractError, "strict_parity"):
            load_adapter(adapter_path)

    def test_schema_and_python_validation_agree_on_checked_in_declarations(self):
        for adapter_path in (
            ROOT / "adapters/claude/adapter.json",
            ROOT / "adapters/codex/adapter.json",
            FIXTURES / "adapters/example/adapter.json",
        ):
            with self.subTest(adapter=adapter_path):
                declaration = load_adapter(adapter_path)
                self.assertEqual(validate_adapter(declaration, self.catalog()), [])
                self.assertEqual(
                    {state.capability for state in declaration.capability_matrix.states},
                    set(self.catalog().capabilities),
                )

    def test_codex_matrix_reports_implementation_truth_not_available_mechanisms(self):
        declaration = load_adapter(ROOT / "adapters/codex/adapter.json")
        states = {
            state.capability: state
            for state in declaration.capability_matrix.states
        }
        not_yet_staged = {
            "global_guidance",
            "skill_catalog",
            "session_start",
            "stop_capture",
            "before_compaction",
            "post_tool_use",
            "subagent_start",
            "schedules",
        }

        for capability in not_yet_staged:
            with self.subTest(capability=capability):
                self.assertIn(states[capability].status, {"degraded", "unsupported"})
                self.assertFalse(states[capability].strict_parity)
                self.assertIn("not", states[capability].evidence.lower())

    def test_capability_matrix_must_cover_catalog_exactly(self):
        payload = self.valid_payload()
        adapter_path = self.write_adapter(payload)
        matrix_path = adapter_path.parent / "capabilities.json"
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        matrix["capabilities"] = matrix["capabilities"][:-1]
        matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
        declaration = load_adapter(adapter_path)
        errors = validate_adapter(declaration, self.catalog())
        self.assertTrue(any("missing capability" in error for error in errors))

        matrix = json.loads(
            (FIXTURES / "adapters/example/capabilities.json").read_text(encoding="utf-8")
        )
        matrix["capabilities"].append(
            {
                "capability": "invented",
                "status": "unsupported",
                "evidence": "The fixture does not define this capability.",
                "impact": "It cannot participate in strict parity.",
                "strict_parity": False,
            }
        )
        matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
        declaration = load_adapter(adapter_path)
        errors = validate_adapter(declaration, self.catalog())
        self.assertTrue(any("unknown capability 'invented'" in error for error in errors))

    def test_contract_cli_accepts_named_and_synthetic_adapters(self):
        commands = (
            ["check", "--contract", "--adapter", "claude"],
            ["check", "--contract", "--adapter", "codex"],
            [
                "check",
                "--contract",
                "--adapter-path",
                "tests/fixtures/adapters/example",
            ],
        )
        for command in commands:
            with self.subTest(command=command):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(command), 0)
                self.assertIn("contract valid", output.getvalue())

    def test_contract_cli_requires_exactly_one_adapter_selector(self):
        commands = (
            ["check", "--contract"],
            ["check", "--contract", "--adapter", "claude", "--adapter-path", "."],
        )
        for command in commands:
            with self.subTest(command=command):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        main(command)
                self.assertEqual(raised.exception.code, 2)

    def test_named_adapter_selector_rejects_path_syntax(self):
        for selector in ("../claude", "claude/other", ".", "claude.json"):
            with self.subTest(selector=selector):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        main(["check", "--contract", "--adapter", selector])
                self.assertEqual(raised.exception.code, 2)

    def test_named_adapter_selector_must_match_loaded_id(self):
        temporary_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(temporary_root))
        adapter_directory = temporary_root / "adapters/expected"
        adapter_directory.mkdir(parents=True)
        payload = self.valid_payload()
        payload["id"] = "different"
        payload["capability_matrix"] = dict(
            json.loads(
                (FIXTURES / "adapters/example/capabilities.json").read_text(
                    encoding="utf-8"
                )
            ),
            adapter_id="different",
        )
        (adapter_directory / "adapter.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

        with self.assertRaisesRegex(AdapterContractError, "selector 'expected'"):
            _load_selected_adapter(temporary_root, "expected", None)

    def test_catalog_rejects_boolean_version_and_unstable_ids(self):
        valid = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        mutations = (
            (("contract_version",), True, "contract_version"),
            (("model_tiers", 0), "Bad Tier", "model tier"),
            (("capabilities", 0, "id"), "bad-capability", "capability ID"),
        )
        for path_parts, value, message in mutations:
            with self.subTest(path=path_parts):
                document = json.loads(json.dumps(valid))
                target = document
                for part in path_parts[:-1]:
                    target = target[part]
                target[path_parts[-1]] = value
                path = self.write_adapter(self.valid_payload()).parent / "catalog.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaisesRegex(AdapterContractError, message):
                    load_capability_catalog(path)
