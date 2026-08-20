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
        self.tempdir = Path(tempfile.mkdtemp()).resolve()
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

    def test_source_swap_to_symlink_never_changes_its_target(self):
        """Following a raced source link and chmodding its target must fail this test."""
        from kingstack import archive as archive_module
        from kingstack.archive import SourceChanged, create_archive

        source = Paths.for_home(self.home).claude_home / "settings.json"
        external = self.tempdir / "external-sentinel"
        self._write(external, b"outside bytes\n", 0o640)
        original_assert = archive_module._assert_source_matches

        def swap_after_validation(path, record):
            original_assert(path, record)
            if path == source:
                source.unlink()
                source.symlink_to(external)

        with patch.object(archive_module, "_assert_source_matches", side_effect=swap_after_validation):
            with self.assertRaises(SourceChanged):
                create_archive(Paths.for_home(self.home), self.archive_root, "raced-link")

        self.assertEqual(external.read_bytes(), b"outside bytes\n")
        self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o640)
        self.assertEqual(list(self.archive_root.glob("archive-*")), [])

    def test_nested_sensitive_component_variants_are_rejected(self):
        """Missing a sensitive component or prefix variant must fail this test."""
        from kingstack.archive import create_archive

        for variant in (
            "auth", "session", "sessions", "transcript", "transcripts",
            "credentials-backup", "keychain-store",
        ):
            with self.subTest(variant=variant):
                home = self.tempdir / ("variant-" + variant)
                self._write(home / ".claude" / "settings.json", b"{}\n", 0o600)
                self._write(home / ".claude" / "hooks" / variant / "token", b"secret\n", 0o600)
                with self.assertRaisesRegex(ValueError, "denylisted"):
                    create_archive(Paths.for_home(home), self.tempdir / ("archives-" + variant), "unsafe")

    def test_verify_reports_a_non_object_manifest(self):
        """Calling dict methods on a JSON array must fail this test."""
        from kingstack.archive import create_archive, verify_archive

        archive = create_archive(Paths.for_home(self.home), self.archive_root, "malformed")
        manifest = archive / "manifest.json"
        manifest.write_text("[]\n", encoding="utf-8")
        manifest.chmod(0o600)

        self.assertEqual(verify_archive(archive), ["invalid archive manifest"])

    def test_symlinked_archive_destination_is_rejected_without_touching_target(self):
        """Resolving a destination symlink and chmodding its target must fail this test."""
        from kingstack.archive import create_archive

        external = self.tempdir / "external-destination"
        external.mkdir(mode=0o750)
        external.chmod(0o750)
        sentinel = external / "sentinel"
        self._write(sentinel, b"outside bytes\n", 0o640)
        requested = self.tempdir / "requested-archives"
        requested.symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(ValueError, "symlinked archive destination"):
            create_archive(Paths.for_home(self.home), requested, "destination-link")

        self.assertEqual(sentinel.read_bytes(), b"outside bytes\n")
        self.assertEqual(stat.S_IMODE(sentinel.stat().st_mode), 0o640)
        self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o750)
        self.assertTrue(requested.is_symlink())
        self.assertEqual(list(external.glob("archive-*")), [])

    def test_symlinked_destination_parent_is_rejected_without_creation(self):
        """Traversing a symlinked parent before making an archive directory must fail this test."""
        from kingstack.archive import create_archive

        external = self.tempdir / "external-parent"
        external.mkdir(mode=0o750)
        external.chmod(0o750)
        sentinel = external / "sentinel"
        self._write(sentinel, b"outside bytes\n", 0o640)
        parent_link = self.tempdir / "archive-parent-link"
        parent_link.symlink_to(external, target_is_directory=True)
        requested = parent_link / "archives"

        with self.assertRaisesRegex(ValueError, "symlinked archive destination"):
            create_archive(Paths.for_home(self.home), requested, "parent-link")

        self.assertEqual(sentinel.read_bytes(), b"outside bytes\n")
        self.assertEqual(stat.S_IMODE(sentinel.stat().st_mode), 0o640)
        self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o750)
        self.assertFalse((external / "archives").exists())

    def test_destination_parent_rebind_after_validation_cannot_escape_anchor(self):
        """Reopening a rebinding parent by path and writing outside must fail this test."""
        from kingstack import archive as archive_module
        from kingstack.archive import create_archive

        anchored_parent = self.tempdir / "anchored-parent"
        anchored_parent.mkdir(mode=0o750)
        external = self.tempdir / "external-parent"
        external.mkdir(mode=0o750)
        external.chmod(0o750)
        sentinel = external / "sentinel"
        self._write(sentinel, b"outside bytes\n", 0o640)
        requested = anchored_parent / "archives"
        detached_parent = self.tempdir / "detached-parent"
        original_validate = archive_module._archive_destination

        def rebind_after_validation(destination):
            validated = original_validate(destination)
            anchored_parent.rename(detached_parent)
            anchored_parent.symlink_to(external, target_is_directory=True)
            return validated

        with patch.object(archive_module, "_archive_destination", side_effect=rebind_after_validation):
            with self.assertRaisesRegex(ValueError, "archive destination changed"):
                create_archive(Paths.for_home(self.home), requested, "late-rebind")

        self.assertEqual(sentinel.read_bytes(), b"outside bytes\n")
        self.assertEqual(stat.S_IMODE(sentinel.stat().st_mode), 0o640)
        self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o750)
        self.assertFalse((external / "archives").exists())
        self.assertEqual(list((detached_parent / "archives").glob("archive-*")), [])

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
