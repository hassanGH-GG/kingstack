import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

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

    def copy_render_inputs(self):
        for relative in ("adapters", "core"):
            shutil.copytree(ROOT / relative, self.sandbox / relative)

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

    def test_wrong_trailing_newline_discipline_is_rejected(self):
        self.copy_render_inputs()
        fragment = self.sandbox / "core/instructions/00-identity.md"
        fragment.write_bytes(fragment.read_bytes() + b"\n")
        with self.assertRaisesRegex(RenderError, "one trailing newline"):
            render_instructions("claude", self.sandbox)

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

    def test_staging_refuses_existing_output_collision(self):
        self.copy_render_inputs()
        output = self.sandbox / ".staging/claude"
        output.mkdir(parents=True)
        (output / "unexpected").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(RenderError, "not empty"):
            write_staged_instructions("claude", output, self.sandbox)
        self.assertEqual((output / "unexpected").read_text(encoding="utf-8"), "keep")

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
