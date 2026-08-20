import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import MappingProxyType
from unittest import TestCase
from unittest.mock import patch

import kingstack.render as render_module
from kingstack.render import RenderError, render_bundle, render_instructions


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests/fixtures"
GOLDEN_SHA256 = "7a6f34e0ff3777279053bb63713dfc109761d508f18fef0316279e9a74fdab2e"


class InstructionRenderTest(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.sandbox = Path(self.temporary_directory.name) / "kingstack"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def copy_render_inputs(self, destination=None):
        destination = destination or self.sandbox
        for relative in ("adapters", "core"):
            shutil.copytree(ROOT / relative, destination / relative)
        provider_source = ROOT / "lib/kingstack"
        provider_destination = destination / "lib/kingstack"
        provider_destination.parent.mkdir(parents=True)
        shutil.copytree(
            provider_source,
            provider_destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    def install_example_adapter(self):
        self.copy_render_inputs()
        shutil.copytree(
            FIXTURES / "adapters/example", self.sandbox / "adapters/example"
        )

    def snapshot_tree(self, root):
        if not root.exists():
            return ()
        rows = []
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                rows.append((relative, "link", os.readlink(path)))
            elif path.is_file():
                rows.append((relative, "file", path.read_bytes()))
            else:
                rows.append((relative, "dir", b""))
        return tuple(rows)

    def run_render_cli(self, *arguments, root=None):
        case_root = root or ROOT
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(case_root / "lib")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, "-m", "kingstack.cli", "render", *arguments],
            cwd=str(case_root),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_frozen_fixture_matches_recorded_baseline_hash(self):
        fixture = FIXTURES / "claude-baseline/CLAUDE.md"
        baseline = json.loads(
            (ROOT / "docs/baselines/claude-codex-baseline.json").read_text(
                encoding="utf-8"
            )
        )
        record = next(
            item for item in baseline["claude"]["records"] if item["path"] == "CLAUDE.md"
        )
        digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
        self.assertEqual(digest, GOLDEN_SHA256)
        self.assertEqual(record["sha256"], GOLDEN_SHA256)

    def test_claude_render_changes_only_the_intentional_routing_section(self):
        bundle = render_bundle("claude", ROOT)
        expected = (FIXTURES / "claude-baseline/CLAUDE.md").read_text(
            encoding="utf-8"
        )
        live = (Path.home() / ".claude/CLAUDE.md").read_bytes()
        actual = bundle["CLAUDE.md"].decode("utf-8")

        baseline_prefix, marker, baseline_tail = expected.partition(
            "\n# Model and effort routing\n"
        )
        _, next_marker, baseline_suffix = baseline_tail.partition("\n# kingstack is a repo\n")
        actual_prefix, actual_marker, actual_tail = actual.partition(
            "\n# Model and effort routing\n"
        )
        _, actual_next_marker, actual_suffix = actual_tail.partition("\n# kingstack is a repo\n")
        actual_memory, appendix_marker, _ = actual_suffix.partition(
            "\n# Claude model routing\n"
        )

        self.assertTrue(marker and next_marker and actual_marker and actual_next_marker)
        self.assertTrue(appendix_marker)
        self.assertEqual(actual_prefix, baseline_prefix)
        self.assertEqual(actual_memory, baseline_suffix)
        self.assertNotEqual(bundle["CLAUDE.md"], live)
        self.assertEqual(render_instructions("claude", ROOT), actual)

    def test_order_lists_every_fragment_once(self):
        order = json.loads(
            (ROOT / "core/instructions/order.json").read_text(encoding="utf-8")
        )
        fragments = {path.name for path in (ROOT / "core/instructions").glob("*.md")}
        self.assertEqual(len(order), len(set(order)))
        self.assertEqual(set(order), fragments)

    def test_duplicate_missing_and_unlisted_fragments_are_rejected(self):
        cases = ("duplicate", "missing", "unlisted")
        for index, case in enumerate(cases):
            with self.subTest(case=case):
                case_root = Path(self.temporary_directory.name) / "fragment-case-{}".format(index)
                self.copy_render_inputs(case_root)
                order_path = case_root / "core/instructions/order.json"
                order = json.loads(order_path.read_text(encoding="utf-8"))
                if case == "duplicate":
                    order.append(order[0])
                    order_path.write_text(json.dumps(order), encoding="utf-8")
                elif case == "missing":
                    (case_root / "core/instructions/00-identity.md").unlink()
                else:
                    (case_root / "core/instructions/99-unlisted.md").write_text(
                        "# Unlisted\n", encoding="utf-8"
                    )
                with self.assertRaisesRegex(RenderError, case):
                    render_bundle("claude", case_root)

    def test_invalid_utf8_and_newline_discipline_are_rejected(self):
        cases = (
            (b"\xff\n", "UTF-8"),
            (b"# Double\n\n", "one trailing newline"),
            (b"# CRLF\r\n", "terminal LF"),
            (b"# Mixed\n\r\n", "terminal LF"),
        )
        for index, (content, message) in enumerate(cases):
            with self.subTest(content=content):
                case_root = Path(self.temporary_directory.name) / "text-case-{}".format(index)
                self.copy_render_inputs(case_root)
                (case_root / "core/instructions/00-identity.md").write_bytes(content)
                with self.assertRaisesRegex(RenderError, message):
                    render_bundle("claude", case_root)

    def test_symlinked_sources_and_adapter_traversal_are_rejected(self):
        targets = (
            ("core/instructions/order.json", b"[]"),
            ("core/instructions/00-identity.md", b"# External\n"),
            ("adapters/claude/instructions-appendix.md", b"\n# External\n"),
            ("lib/kingstack/adapters/claude.py", b"def render(*args): return {}\n"),
        )
        for index, (relative, content) in enumerate(targets):
            with self.subTest(relative=relative):
                case_root = Path(self.temporary_directory.name) / "symlink-case-{}".format(index)
                self.copy_render_inputs(case_root)
                source = case_root / relative
                external = Path(self.temporary_directory.name) / "external-{}".format(index)
                external.write_bytes(content)
                source.unlink()
                source.symlink_to(external)
                with self.assertRaisesRegex(RenderError, "symbolic link"):
                    render_bundle("claude", case_root)

        with self.assertRaisesRegex(RenderError, "stable adapter ID"):
            render_bundle("../claude", ROOT)

    def test_late_source_directory_swap_is_detected(self):
        self.copy_render_inputs()
        instructions = self.sandbox / "core/instructions"
        displaced = self.sandbox / "core/instructions.displaced"
        external = Path(self.temporary_directory.name) / "external-instructions"
        shutil.copytree(instructions, external)
        (external / "00-identity.md").write_text("# Injected\n", encoding="utf-8")
        real_open = os.open
        swapped = False

        def swap_before_fragment_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if path == "00-identity.md" and dir_fd is not None and not swapped:
                swapped = True
                instructions.rename(displaced)
                instructions.symlink_to(external, target_is_directory=True)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        with patch("kingstack.render.os.open", side_effect=swap_before_fragment_open):
            with self.assertRaisesRegex(RenderError, "changed during render"):
                render_bundle("claude", self.sandbox)
        self.assertTrue(swapped)
        self.assertEqual(
            (external / "00-identity.md").read_text(encoding="utf-8"), "# Injected\n"
        )

    def test_declaration_dispatches_synthetic_provider_without_core_change(self):
        self.install_example_adapter()

        bundle = render_bundle("example", self.sandbox)

        self.assertIsInstance(bundle, MappingProxyType)
        self.assertEqual(list(bundle), ["GUIDANCE.md", "hooks/session-start"])
        self.assertTrue(bundle["GUIDANCE.md"].startswith(b"# Standing rule"))
        self.assertEqual(bundle["hooks/session-start"], b"sample-agent-start\n")
        with self.assertRaises(TypeError):
            bundle["GUIDANCE.md"] = b"changed"

    def test_provider_output_must_be_bytes_canonical_and_owned(self):
        cases = (
            ("return {'GUIDANCE.md': 'text'}", "bytes"),
            ("return {'../escape': b'bad'}", "backtracking"),
            ("return {'unowned': b'bad'}", "not covered"),
        )
        for index, (statement, message) in enumerate(cases):
            with self.subTest(statement=statement):
                case_root = Path(self.temporary_directory.name) / "provider-case-{}".format(index)
                self.copy_render_inputs(case_root)
                shutil.copytree(FIXTURES / "adapters/example", case_root / "adapters/example")
                (case_root / "adapters/example/sample_agent/render.py").write_text(
                    "def render(root, declaration, shared_sources):\n    {}\n".format(statement),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(RenderError, message):
                    render_bundle("example", case_root)

    def test_provider_output_reuses_full_portable_path_contract(self):
        invalid_paths = (
            ("hooks/CON", "device"),
            ("hooks/aux.txt", "device"),
            ("hooks/file.", "ambiguous"),
            ("hooks/file ", "ambiguous"),
            ("hooks/bad:name", "portable to Windows"),
            ("C:/escape", "drive prefix"),
            (r"\\server\share", "backslashes"),
            (r"hooks\file", "backslashes"),
            ("hooks/bad\nname", "control"),
        )
        for index, (output_path, message) in enumerate(invalid_paths):
            with self.subTest(output_path=output_path):
                case_root = Path(self.temporary_directory.name) / "portable-case-{}".format(index)
                self.copy_render_inputs(case_root)
                shutil.copytree(FIXTURES / "adapters/example", case_root / "adapters/example")
                declaration_path = case_root / "adapters/example/adapter.json"
                declaration = json.loads(declaration_path.read_text(encoding="utf-8"))
                declaration["owned_paths"] = ["GUIDANCE.md", "hooks"]
                declaration_path.write_text(json.dumps(declaration), encoding="utf-8")
                (case_root / "adapters/example/sample_agent/render.py").write_text(
                    "def render(root, declaration, shared_sources):\n"
                    "    return {{{!r}: b'bad'}}\n".format(output_path),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(RenderError, message):
                    render_bundle("example", case_root)

    def test_provider_output_stores_nfc_and_rejects_portable_aliases(self):
        self.install_example_adapter()
        declaration_path = self.sandbox / "adapters/example/adapter.json"
        declaration = json.loads(declaration_path.read_text(encoding="utf-8"))
        declaration["owned_paths"] = ["GUIDANCE.md", "hooks"]
        declaration_path.write_text(json.dumps(declaration), encoding="utf-8")
        provider = self.sandbox / "adapters/example/sample_agent/render.py"
        provider.write_text(
            "def render(root, declaration, shared_sources):\n"
            "    return {'hooks/e\\u0301': b'nfc'}\n",
            encoding="utf-8",
        )

        bundle = render_bundle("example", self.sandbox)

        self.assertEqual(list(bundle), ["hooks/é"])

        for paths in (("hooks/File", "hooks/file"), ("hooks/é", "hooks/e\u0301")):
            with self.subTest(paths=paths):
                provider.write_text(
                    "def render(root, declaration, shared_sources):\n"
                    "    return {{{!r}: b'a', {!r}: b'b'}}\n".format(*paths),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(RenderError, "duplicate"):
                    render_bundle("example", self.sandbox)

    def test_missing_or_invalid_provider_entrypoint_is_rejected(self):
        self.install_example_adapter()
        provider = self.sandbox / "adapters/example/sample_agent/render.py"
        provider.write_text("VALUE = 1\n", encoding="utf-8")
        with self.assertRaisesRegex(RenderError, "callable render"):
            render_bundle("example", self.sandbox)

    def test_render_and_all_cli_selectors_write_nothing(self):
        self.copy_render_inputs()
        before = self.snapshot_tree(self.sandbox)

        bundle = render_bundle("claude", self.sandbox)
        manifest = self.run_render_cli("--adapter", "claude", "--manifest", root=self.sandbox)
        printed = self.run_render_cli(
            "--adapter", "claude", "--print-file", "CLAUDE.md", root=self.sandbox
        )
        self.assertEqual(before, self.snapshot_tree(self.sandbox))

        equal_file = Path(self.temporary_directory.name) / "expected.md"
        equal_file.write_bytes(bundle["CLAUDE.md"])
        checked = self.run_render_cli(
            "--adapter", "claude", "--check-file", "CLAUDE.md",
            "--equals", str(equal_file), root=self.sandbox,
        )

        self.assertEqual(manifest.returncode, 0, manifest.stderr.decode())
        document = json.loads(manifest.stdout)
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["adapter"], "claude")
        self.assertEqual(len(document["skills"]), 65)
        self.assertEqual(
            document["files"],
            [
                {
                    "path": path,
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
                for path, content in bundle.items()
            ],
        )
        self.assertEqual(printed.returncode, 0, printed.stderr.decode())
        self.assertEqual(printed.stdout, bundle["CLAUDE.md"])
        self.assertEqual(checked.returncode, 0, checked.stderr.decode())
        self.assertEqual(before, self.snapshot_tree(self.sandbox))

    def test_cli_rejects_output_conflicts_unknown_paths_and_mismatch(self):
        conflict = self.run_render_cli(
            "--adapter", "claude", "--manifest", "--print-file", "CLAUDE.md"
        )
        output = self.run_render_cli(
            "--adapter", "claude", "--output", ".staging/claude"
        )
        traversal = self.run_render_cli(
            "--adapter", "claude", "--print-file", "../CLAUDE.md"
        )
        unknown = self.run_render_cli(
            "--adapter", "claude", "--print-file", "UNKNOWN.md"
        )
        missing_equals = self.run_render_cli(
            "--adapter", "claude", "--check-file", "CLAUDE.md"
        )
        mismatch_path = Path(self.temporary_directory.name) / "mismatch"
        mismatch_path.write_bytes(b"different\n")
        mismatch = self.run_render_cli(
            "--adapter", "claude", "--check-file", "CLAUDE.md",
            "--equals", str(mismatch_path),
        )

        for result in (conflict, output, traversal, unknown, missing_equals):
            self.assertEqual(result.returncode, 2, result.stderr.decode())
        self.assertEqual(mismatch.returncode, 1, mismatch.stderr.decode())

    def test_mutable_staging_api_and_production_references_are_absent(self):
        self.assertFalse(hasattr(render_module, "write_staged_instructions"))
        production = (ROOT / "lib/kingstack/render.py").read_text(encoding="utf-8")
        cli = (ROOT / "lib/kingstack/cli.py").read_text(encoding="utf-8")
        self.assertNotIn(".staging", production)
        self.assertNotIn("write_staged_instructions", production + cli)
