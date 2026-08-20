import io
import os
import shutil
import stat
import tempfile
from contextlib import redirect_stderr
from datetime import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from kingstack.paths import Paths


class ArchiveTest(TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        self.home = self.tempdir / "source-home"
        self.archive_root = self.tempdir / "private-archives"
        self._write(self.home / ".claude" / "settings.json", b'{"theme":"dark"}\n', 0o644)
        self._write(self.home / ".claude" / "hooks" / "validate", b"#!/bin/sh\nexit 0\n", 0o755)
        self._write(self.home / ".claude" / "shared" / "SKILL.md", b"shared skill\n", 0o600)
        (self.home / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
        (self.home / ".claude" / "skills" / "example.md").symlink_to("../shared/SKILL.md")
        self._write(self.home / ".codex" / "config.toml", b'model = "test"\n', 0o640)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _write(self, path, content, mode):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(mode)

    def test_capture_preserves_selected_bytes_relative_links_and_private_modes(self):
        """Changing copied bytes, link text, or private mode must fail this test."""
        from kingstack.archive import create_archive, verify_archive

        archive = create_archive(Paths.for_home(self.home), self.archive_root, "before-migration")

        self.assertEqual((archive / "files" / "claude" / "settings.json").read_bytes(), b'{"theme":"dark"}\n')
        link = archive / "files" / "claude" / "skills" / "example.md"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "../shared/SKILL.md")
        self.assertEqual(stat.S_IMODE((archive / "files" / "claude" / "settings.json").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((archive / "files" / "claude" / "hooks" / "validate").stat().st_mode), 0o700)
        self.assertEqual(verify_archive(archive, check_permissions=True), [])

    def test_denied_auth_path_is_rejected(self):
        """Allowing auth material into an archive must fail this test."""
        from kingstack.archive import create_archive

        self._write(self.home / ".claude" / "hooks" / "auth.json", b"secret\n", 0o600)

        with self.assertRaisesRegex(ValueError, "denylisted"):
            create_archive(Paths.for_home(self.home), self.archive_root, "unsafe")
        self.assertFalse(self.archive_root.exists())

    def test_capture_makes_every_intermediate_directory_private_under_a_broad_umask(self):
        """Leaving an intermediate directory group-readable must fail this test."""
        from kingstack.archive import create_archive, verify_archive

        self._write(self.home / ".claude" / "projects" / "demo" / "memory" / "note.md", b"note\n", 0o600)
        previous_umask = os.umask(0o022)
        try:
            archive = create_archive(Paths.for_home(self.home), self.archive_root, "nested")
        finally:
            os.umask(previous_umask)
        self.assertEqual(verify_archive(archive, check_permissions=True), [])

    def test_source_change_aborts_without_publication(self):
        """Publishing an archive after its source changes must fail this test."""
        from kingstack.archive import SourceChanged, create_archive

        def mutate_source():
            self._write(self.home / ".claude" / "settings.json", b"changed after copy\n", 0o644)

        with self.assertRaises(SourceChanged):
            create_archive(Paths.for_home(self.home), self.archive_root, "race", after_copy=mutate_source)
        self.assertEqual(list(self.archive_root.glob("archive-*")), [])

    def test_existing_archive_id_is_never_replaced(self):
        """Replacing a matching timestamp directory must fail this test."""
        from kingstack import archive as archive_module
        from kingstack.archive import create_archive

        fixed_time = datetime(2026, 8, 20, 12, 0, 0)
        occupied = self.archive_root / "archive-20260820-120000"
        occupied.mkdir(parents=True)
        sentinel = occupied / "sentinel"
        sentinel.write_bytes(b"keep")

        with patch.object(archive_module, "datetime") as clock:
            clock.utcnow.return_value = fixed_time
            with self.assertRaisesRegex(ValueError, "already exists"):
                create_archive(Paths.for_home(self.home), self.archive_root, "collision")
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_archive_cli_has_no_apply_or_restore_command(self):
        """Adding a mutating archive subcommand must fail this test."""
        from kingstack.cli import main

        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as apply:
                main(["archive", "apply", "archive-20260820-120000"])
            with self.assertRaises(SystemExit) as restore:
                main(["archive", "restore", "archive-20260820-120000"])
        self.assertNotEqual(apply.exception.code, 0)
        self.assertNotEqual(restore.exception.code, 0)
