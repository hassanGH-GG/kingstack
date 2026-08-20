import os
import shutil
import stat
import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.paths import Paths


class SnapshotTest(TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        self.home = self.tempdir / "source-home"
        self.snapshot_root = self.tempdir / "private-snapshots"
        self._write(self.home / ".claude" / "settings.json", b'{"theme":"dark"}\n', 0o600)
        self._write(self.home / ".claude" / "hooks" / "validate", b"#!/bin/sh\nexit 0\n", 0o700)
        self._write(self.home / ".claude" / "shared" / "SKILL.md", b"shared skill\n", 0o600)
        (self.home / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
        (self.home / ".claude" / "skills" / "example.md").symlink_to("../shared/SKILL.md")
        self._write(self.home / ".claude" / "agents" / "read-only.json", b"{}\n", 0o400)
        self._write(self.home / ".claude" / "projects" / "demo" / "memory" / "note.md", b"memory note\n", 0o600)
        self._write(self.home / ".codex" / "config.toml", b'model = "test"\n', 0o600)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _write(self, path, content, mode):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(mode)

    def test_snapshot_round_trips_files_symlinks_and_private_modes(self):
        """Following a link or broadening a mode would corrupt a private restore."""
        from kingstack.snapshot import create_snapshot, restore_snapshot, verify_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        self.assertEqual(verify_snapshot(snapshot, check_permissions=True), [])
        (self.home / ".claude" / "settings.json").write_bytes(b"mutated\n")
        destination = self.tempdir / "restore-home"

        planned = restore_snapshot(snapshot, destination)
        self.assertIn(destination / ".claude" / "settings.json", planned)
        self.assertFalse((destination / ".claude" / "settings.json").exists())
        restored = restore_snapshot(snapshot, destination, dry_run=False)

        self.assertIn(destination / ".codex" / "config.toml", restored)
        self.assertEqual((destination / ".claude" / "settings.json").read_bytes(), b'{"theme":"dark"}\n')
        self.assertEqual((destination / ".claude" / "hooks" / "validate").read_bytes(), b"#!/bin/sh\nexit 0\n")
        link = destination / ".claude" / "skills" / "example.md"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "../shared/SKILL.md")
        self.assertEqual(stat.S_IMODE((destination / ".claude" / "settings.json").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((destination / ".claude" / "agents" / "read-only.json").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((destination / ".claude" / "hooks" / "validate").stat().st_mode), 0o700)

    def test_snapshot_refuses_a_denylisted_source_path(self):
        """Copying auth state from an otherwise selected directory is forbidden."""
        from kingstack.snapshot import create_snapshot

        self._write(self.home / ".claude" / "hooks" / "auth.json", b"secret\n", 0o600)

        with self.assertRaisesRegex(ValueError, "denylisted"):
            create_snapshot(Paths.for_home(self.home), self.snapshot_root, "unsafe")
        self.assertFalse(self.snapshot_root.exists())

    def test_restore_refuses_unknown_live_file_without_current_hash(self):
        """An existing destination file must not be overwritten without a precondition."""
        from kingstack.snapshot import create_snapshot, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "live-home"
        self._write(destination / ".claude" / "settings.json", b"unknown\n", 0o600)

        with self.assertRaisesRegex(ValueError, "expected current hash"):
            restore_snapshot(snapshot, destination, dry_run=False)
        self.assertEqual((destination / ".claude" / "settings.json").read_bytes(), b"unknown\n")

    def test_restore_refuses_a_symlinked_destination_parent(self):
        """A restore must not follow a destination symlink outside the selected home."""
        from kingstack.snapshot import create_snapshot, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        external = self.tempdir / "outside-destination"
        destination.mkdir()
        external.mkdir()
        (destination / ".claude").symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(ValueError, "symlinked destination directory"):
            restore_snapshot(snapshot, destination, dry_run=False)
        self.assertFalse((external / "settings.json").exists())

    def test_verify_reports_tampered_content_and_permissions(self):
        """A manifest that is readable by others or no longer hashes correctly is invalid."""
        from kingstack.snapshot import create_snapshot, verify_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        saved = snapshot / "files" / "claude" / "settings.json"
        saved.write_bytes(b"tampered\n")
        (snapshot / "manifest.json").chmod(0o644)

        problems = verify_snapshot(snapshot, check_permissions=True)
        self.assertTrue(any("hash mismatch" in problem for problem in problems), problems)
        self.assertTrue(any("permission" in problem for problem in problems), problems)

    def test_cli_prints_snapshot_id_and_verifies_it_by_id(self):
        """The CLI identifier must resolve to the private snapshot it just created."""
        import subprocess

        command = [
            "./scripts/kingstack", "snapshot", "--home", str(self.home), "--label", "before-migration", "--print-id",
        ]
        created = subprocess.run(command, cwd=Path(__file__).parents[1], text=True, capture_output=True)
        self.assertEqual(created.returncode, 0, created.stderr)
        identifier = created.stdout.strip()
        self.assertTrue(identifier.startswith("snapshot-"))
        verified = subprocess.run(
            ["./scripts/kingstack", "snapshot", "verify", identifier, "--home", str(self.home), "--check-permissions"],
            cwd=Path(__file__).parents[1],
            text=True,
            capture_output=True,
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
