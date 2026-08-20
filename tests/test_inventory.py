import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.paths import Paths


FIXTURE_HOME = Path(__file__).parent / "fixtures" / "inventory-home"


class InventoryTest(TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        shutil.copytree(FIXTURE_HOME, self.tempdir / "home", symlinks=True)
        self.home = self.tempdir / "home"

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_capture_is_deterministic_and_redacts_config_values(self):
        """Changing a config scalar must never expose it in the public report."""
        from kingstack.inventory import capture_baseline

        paths = Paths.for_home(self.home)
        a = capture_baseline(paths)
        b = capture_baseline(paths)
        encoded = json.dumps(a, sort_keys=True)

        self.assertEqual(a, b)
        self.assertNotIn("top-secret-value", encoded)
        self.assertNotIn("/Users/test/private", encoded)
        self.assertIn("api.token", a["claude"]["config_keys"])
        self.assertIn("model.api_key", a["codex"]["config_keys"])
        self.assertIn("projects.<redacted>.trust_level", a["codex"]["config_keys"])
        self.assertEqual(a["counts"]["memory_banks"], 1)

    def test_capture_records_symlink_mode_and_file_hash(self):
        """Dereferencing a symlink or losing its executable mode corrupts a baseline."""
        from kingstack.inventory import capture_baseline

        report = capture_baseline(Paths.for_home(self.home))
        records = {record["path"]: record for record in report["claude"]["records"]}

        self.assertEqual(records["skills/example.md"]["kind"], "symlink")
        self.assertEqual(records["skills/example.md"]["target"], "../shared/SKILL.md")
        self.assertEqual(records["hooks/validate"]["mode"], "0755")
        self.assertEqual(
            records["hooks/validate"]["sha256"],
            hashlib.sha256(b"#!/bin/sh\nexit 0\n").hexdigest(),
        )

    def test_write_public_report_is_byte_deterministic_and_rejects_private_destinations(self):
        """A public report must be repeatable and never land in agent-private storage."""
        from kingstack.inventory import capture_baseline, write_public_report

        baseline = capture_baseline(Paths.for_home(self.home))
        first = self.tempdir / "first.json"
        second = self.tempdir / "second.json"
        write_public_report(baseline, first)
        write_public_report(baseline, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertNotIn(str(self.home), first.read_text(encoding="utf-8"))

        with self.assertRaises(ValueError):
            write_public_report(baseline, self.home / ".claude" / "report.json")
        with self.assertRaises(ValueError):
            write_public_report(
                baseline,
                self.home / ".claude" / "projects" / "demo" / "memory" / "report.json",
            )

    def test_cli_writes_fixture_inventory_and_rejects_agent_home_output(self):
        """A CLI regression must not write a report under a protected agent home."""
        output = self.tempdir / "inventory.json"
        command = ["./scripts/kingstack", "inventory", "--home", str(self.home), "--output", str(output)]

        result = subprocess.run(command, cwd=Path(__file__).parents[1], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.exists())

        denied = subprocess.run(
            command[:-1] + [str(self.home / ".codex" / "inventory.json")],
            cwd=Path(__file__).parents[1],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(denied.returncode, 0)
        self.assertFalse((self.home / ".codex" / "inventory.json").exists())
