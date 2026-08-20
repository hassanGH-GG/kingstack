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
        self.tempdir = Path(tempfile.mkdtemp()).resolve()
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

    def test_capture_excludes_sensitive_paths_at_every_depth(self):
        """Hashing a secret in an included directory would publish its fingerprint."""
        from kingstack.inventory import capture_baseline

        excluded = [
            "hooks/auth.json", "hooks/sessions/state.json", "skills/cache/entry",
            "agents/history/session.json", "scripts/logs/run.log", "hooks/downloads/file",
            "skills/browser/data", "agents/credentials.txt", "agents/transcript.jsonl",
            "agents/database.sqlite",
        ]
        for relative in excluded:
            path = self.home / ".claude" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("must-not-be-fingerprinted", encoding="utf-8")

        report = capture_baseline(Paths.for_home(self.home))
        encoded = json.dumps(report, sort_keys=True)
        paths = [record["path"] for record in report["claude"]["records"]]

        self.assertNotIn("must-not-be-fingerprinted", encoded)
        self.assertNotIn(
            hashlib.sha256(b"must-not-be-fingerprinted").hexdigest(), encoded,
        )
        for relative in excluded:
            self.assertNotIn(relative, paths)

    def test_capture_redacts_absolute_symlink_targets(self):
        """An absolute symlink target would disclose a home path in the report."""
        from kingstack.inventory import capture_baseline

        targets = {
            "absolute-target.md": "/Users/test/private/SKILL.md",
            "unc-target.md": r"\\server\share\secret",
            "rooted-backslash-target.md": r"\Users\test\private",
        }
        for name, target in targets.items():
            (self.home / ".claude" / "skills" / name).symlink_to(target)

        report = capture_baseline(Paths.for_home(self.home))
        records = {record["path"]: record for record in report["claude"]["records"]}

        encoded = json.dumps(report, sort_keys=True)
        for name, target in targets.items():
            with self.subTest(target=target):
                self.assertEqual(records["skills/" + name]["target"], "<redacted>")
                self.assertNotIn(target, encoded)

    def test_capture_redacts_path_shaped_json_key_names(self):
        """A path-shaped JSON key must not reveal a home path as report metadata."""
        from kingstack.inventory import capture_baseline

        (self.home / ".claude" / "settings.json").write_text(
            json.dumps({"/Users/test/private": {"token": "top-secret-value"}}),
            encoding="utf-8",
        )

        report = capture_baseline(Paths.for_home(self.home))

        self.assertEqual(report["claude"]["config_keys"], ["<redacted>.token"])
        self.assertNotIn("/Users/test/private", json.dumps(report, sort_keys=True))

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

    def test_write_public_report_refuses_symlinked_parent_and_existing_file(self):
        from kingstack.inventory import capture_baseline, write_public_report

        baseline = capture_baseline(Paths.for_home(self.home))
        external = self.tempdir / "external"
        external.mkdir()
        sentinel = external / "report.json"
        sentinel.write_text("external-sentinel\n", encoding="utf-8")
        linked_parent = self.tempdir / "linked-parent"
        linked_parent.symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(ValueError, "symlink"):
            write_public_report(baseline, linked_parent / "report.json")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "external-sentinel\n")

        existing = self.tempdir / "existing.json"
        existing.write_text("existing-sentinel\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "exists"):
            write_public_report(baseline, existing)
        self.assertEqual(existing.read_text(encoding="utf-8"), "existing-sentinel\n")

        external_file = external / "external-file.json"
        external_file.write_text("symlink-target-sentinel\n", encoding="utf-8")
        linked_file = self.tempdir / "linked-file.json"
        linked_file.symlink_to(external_file)
        with self.assertRaisesRegex(ValueError, "exists"):
            write_public_report(baseline, linked_file)
        self.assertEqual(
            external_file.read_text(encoding="utf-8"), "symlink-target-sentinel\n",
        )

    def test_write_public_report_supports_real_macos_mktemp_var_alias(self):
        from kingstack.inventory import capture_baseline, write_public_report

        raw_directory = Path(
            subprocess.run(
                ["mktemp", "-d"], check=True, text=True, stdout=subprocess.PIPE,
            ).stdout.strip()
        )
        self.addCleanup(shutil.rmtree, raw_directory, True)
        output = raw_directory / "baseline.json"

        write_public_report(capture_baseline(Paths.for_home(self.home)), output)

        self.assertTrue(output.is_file())
        self.assertTrue(str(raw_directory).startswith("/var/"))

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
