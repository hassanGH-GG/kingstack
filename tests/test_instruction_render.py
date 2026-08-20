import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from kingstack.render import RenderError, render_instructions, write_staged_instructions


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

    def test_claude_render_is_byte_identical_to_baseline(self):
        actual = render_instructions("claude", ROOT)
        expected = (FIXTURES / "claude-baseline/CLAUDE.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(actual, expected)

    def test_order_lists_every_fragment_once(self):
        order = json.loads(
            (ROOT / "core/instructions/order.json").read_text(encoding="utf-8")
        )
        fragments = {path.name for path in (ROOT / "core/instructions").glob("*.md")}
        self.assertEqual(len(order), len(set(order)))
        self.assertEqual(set(order), fragments)

    def test_duplicate_order_entry_is_rejected(self):
        self.copy_render_inputs()
        order_path = self.sandbox / "core/instructions/order.json"
        order = json.loads(order_path.read_text(encoding="utf-8"))
        order.append(order[0])
        order_path.write_text(json.dumps(order), encoding="utf-8")
        with self.assertRaisesRegex(RenderError, "duplicate"):
            render_instructions("claude", self.sandbox)

    def test_unlisted_fragment_is_rejected(self):
        self.copy_render_inputs()
        (self.sandbox / "core/instructions/99-unlisted.md").write_text(
            "# Unlisted\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(RenderError, "unlisted"):
            render_instructions("claude", self.sandbox)

    def test_ordered_fragment_missing_from_disk_is_rejected(self):
        self.copy_render_inputs()
        (self.sandbox / "core/instructions/00-identity.md").unlink()
        with self.assertRaisesRegex(RenderError, "missing fragments"):
            render_instructions("claude", self.sandbox)

    def test_invalid_utf8_fragment_is_rejected(self):
        self.copy_render_inputs()
        fragment = self.sandbox / "core/instructions/00-identity.md"
        fragment.write_bytes(b"\xff\n")
        with self.assertRaisesRegex(RenderError, "UTF-8"):
            render_instructions("claude", self.sandbox)

    def test_symlinked_order_fragment_and_appendix_are_rejected(self):
        targets = (
            ("core/instructions/order.json", b"[]"),
            ("core/instructions/00-identity.md", b"# External\n"),
            ("adapters/claude/instructions-appendix.md", b"\n# External\n"),
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
                    render_instructions("claude", case_root)

    def test_wrong_trailing_newline_discipline_is_rejected(self):
        self.copy_render_inputs()
        fragment = self.sandbox / "core/instructions/00-identity.md"
        fragment.write_bytes(fragment.read_bytes() + b"\n")
        with self.assertRaisesRegex(RenderError, "one trailing newline"):
            render_instructions("claude", self.sandbox)

    def test_crlf_and_mixed_terminal_newlines_are_rejected(self):
        for index, content in enumerate((b"# CRLF\r\n", b"# Mixed\n\r\n", b"# Mixed\r\n\n")):
            with self.subTest(content=content):
                case_root = Path(self.temporary_directory.name) / "newline-case-{}".format(index)
                self.copy_render_inputs(case_root)
                fragment = case_root / "core/instructions/00-identity.md"
                fragment.write_bytes(content)
                with self.assertRaisesRegex(RenderError, "terminal LF"):
                    render_instructions("claude", case_root)

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
                render_instructions("claude", self.sandbox)
        self.assertTrue(swapped)
        self.assertEqual((external / "00-identity.md").read_text(encoding="utf-8"), "# Injected\n")

    def test_adapter_path_traversal_is_rejected(self):
        with self.assertRaisesRegex(RenderError, "stable adapter ID"):
            render_instructions("../claude", ROOT)

    def test_adapter_directory_symlink_is_rejected(self):
        self.copy_render_inputs()
        external = Path(self.temporary_directory.name) / "external-claude"
        shutil.copytree(self.sandbox / "adapters/claude", external)
        shutil.rmtree(self.sandbox / "adapters/claude")
        (self.sandbox / "adapters/claude").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(RenderError, "symbolic link"):
            render_instructions("claude", self.sandbox)

    def test_staging_refuses_a_symlink_component(self):
        self.copy_render_inputs()
        outside = Path(self.temporary_directory.name) / "outside"
        outside.mkdir()
        (self.sandbox / ".staging").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RenderError, "symbolic link"):
            write_staged_instructions("claude", self.sandbox / ".staging/claude", self.sandbox)
        self.assertEqual(list(outside.iterdir()), [])

    def test_staging_regular_file_collision_is_a_render_error(self):
        self.copy_render_inputs()
        staging = self.sandbox / ".staging"
        staging.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(RenderError, "not a directory"):
            write_staged_instructions("claude", staging / "claude", self.sandbox)
        self.assertEqual(staging.read_text(encoding="utf-8"), "keep")

    def test_cli_regular_file_collision_returns_two_without_traceback(self):
        case_root = Path(self.temporary_directory.name) / "cli-collision"
        self.copy_render_inputs(case_root)
        shutil.copytree(ROOT / "lib", case_root / "lib")
        (case_root / ".staging").write_text("keep", encoding="utf-8")
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(case_root / "lib")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "kingstack.cli",
                "render",
                "--adapter",
                "claude",
                "--output",
                ".staging/claude",
            ],
            cwd=str(case_root),
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("is not a directory", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual((case_root / ".staging").read_text(encoding="utf-8"), "keep")

    def test_late_staging_directory_swap_cannot_publish_externally(self):
        self.copy_render_inputs()
        output = self.sandbox / ".staging/claude"
        output.mkdir(parents=True)
        displaced = self.sandbox / ".staging/claude.displaced"
        outside = Path(self.temporary_directory.name) / "outside-late-swap"
        outside.mkdir()
        real_open = os.open
        swapped = False

        def swap_before_output_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if (
                path == "CLAUDE.md"
                and dir_fd is not None
                and flags & os.O_CREAT
                and not swapped
            ):
                swapped = True
                output.rename(displaced)
                output.symlink_to(outside, target_is_directory=True)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        with patch("kingstack.render.os.open", side_effect=swap_before_output_open):
            with self.assertRaisesRegex(RenderError, "changed during render"):
                write_staged_instructions("claude", output, self.sandbox)
        self.assertTrue(swapped)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(list(displaced.iterdir()), [])

    def test_staging_refuses_existing_output_collision(self):
        self.copy_render_inputs()
        output = self.sandbox / ".staging/claude"
        output.mkdir(parents=True)
        (output / "unexpected").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(RenderError, "not empty"):
            write_staged_instructions("claude", output, self.sandbox)
        self.assertEqual((output / "unexpected").read_text(encoding="utf-8"), "keep")

    def test_existing_instruction_collision_is_preserved(self):
        self.copy_render_inputs()
        output = self.sandbox / ".staging/claude"
        output.mkdir(parents=True)
        existing = output / "CLAUDE.md"
        existing.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(RenderError, "not empty"):
            write_staged_instructions("claude", output, self.sandbox)
        self.assertEqual(existing.read_text(encoding="utf-8"), "keep")

    def test_staging_writes_only_the_adapter_owned_instruction_file(self):
        self.copy_render_inputs()
        output = self.sandbox / ".staging/claude"
        written = write_staged_instructions("claude", output, self.sandbox)
        self.assertEqual(written, (output / "CLAUDE.md").resolve())
        self.assertEqual(
            {path.name for path in output.iterdir()},
            {"CLAUDE.md"},
        )
        self.assertEqual(written.read_text(encoding="utf-8"), render_instructions("claude", self.sandbox))
