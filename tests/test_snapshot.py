import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

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
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot, verify_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        self.assertEqual(verify_snapshot(snapshot, check_permissions=True), [])
        (self.home / ".claude" / "settings.json").write_bytes(b"mutated\n")
        destination = self.tempdir / "restore-home"

        planned = restore_snapshot(snapshot, destination)
        self.assertIn(destination / ".claude" / "settings.json", planned)
        self.assertFalse((destination / ".claude" / "settings.json").exists())
        restored = restore_snapshot(
            snapshot,
            destination,
            dry_run=False,
            expected_current_hash=current_destination_hash(snapshot, destination),
        )

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
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "live-home"
        self._write(destination / ".claude" / "settings.json", b"unknown\n", 0o600)

        with self.assertRaisesRegex(ValueError, "expected current hash"):
            restore_snapshot(snapshot, destination, dry_run=False)
        self.assertEqual((destination / ".claude" / "settings.json").read_bytes(), b"unknown\n")

    def test_restore_refuses_a_symlinked_destination_parent(self):
        """A restore must not follow a destination symlink outside the selected home."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        external = self.tempdir / "outside-destination"
        destination.mkdir()
        external.mkdir()
        (destination / ".claude").symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(ValueError, "destination directory"):
            restore_snapshot(
                snapshot,
                destination,
                dry_run=False,
                expected_current_hash=current_destination_hash(snapshot, destination),
            )
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

    def test_verify_rejects_denylisted_duplicate_and_extra_manifest_entries(self):
        """A forged manifest must not smuggle auth state or unlisted payloads."""
        from kingstack.snapshot import create_snapshot, verify_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        manifest_path = snapshot / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"].append(dict(manifest["files"][0]))
        manifest["files"][1]["path"] = "claude/hooks/auth.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest_path.chmod(0o600)
        self._write(snapshot / "files" / "claude" / "unlisted.json", b"extra\n", 0o600)

        problems = verify_snapshot(snapshot, check_permissions=True)
        self.assertTrue(any("denylisted" in problem for problem in problems), problems)
        self.assertTrue(any("duplicate" in problem for problem in problems), problems)
        self.assertTrue(any("unexpected snapshot entry" in problem for problem in problems), problems)

    def test_verify_rejects_symlinked_snapshot_storage_and_manifest_ancestors(self):
        """Verification must not follow a snapshot directory or files-tree symlink."""
        from kingstack.snapshot import create_snapshot, verify_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        alias = self.tempdir / "snapshot-alias"
        alias.symlink_to(snapshot, target_is_directory=True)
        self.assertTrue(any("symlink" in problem for problem in verify_snapshot(alias)))

        files = snapshot / "files"
        relocated = snapshot / "stored-files"
        files.rename(relocated)
        files.symlink_to(relocated, target_is_directory=True)
        self.assertTrue(any("symlink" in problem for problem in verify_snapshot(snapshot)))

    def test_restore_requires_expected_hash_for_missing_targets_and_hashes_modes(self):
        """A creation-only restore still needs a state precondition, including modes."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        with self.assertRaisesRegex(ValueError, "expected current hash"):
            restore_snapshot(snapshot, destination, dry_run=False)

        expected = current_destination_hash(snapshot, destination)
        restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=expected)
        before_mode_change = current_destination_hash(snapshot, destination)
        (destination / ".claude" / "settings.json").chmod(0o700)
        self.assertNotEqual(before_mode_change, current_destination_hash(snapshot, destination))

    def test_restore_preflights_late_namespace_before_mutating_early_namespace(self):
        """A bad Codex parent must not permit any earlier Claude replacement."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        destination.mkdir()
        self._write(destination / ".codex", b"not a directory\n", 0o600)
        expected = current_destination_hash(snapshot, destination)

        with self.assertRaisesRegex(ValueError, "destination directory"):
            restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=expected)
        self.assertFalse((destination / ".claude" / "settings.json").exists())

    def test_verify_requires_exact_file_modes_and_null_symlink_mode(self):
        """Private proof rejects narrow modes and symlink modes are deliberately ignored."""
        from kingstack.snapshot import create_snapshot, verify_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
        symlink = next(record for record in manifest["files"] if record["kind"] == "symlink")
        self.assertIsNone(symlink["mode"])
        (snapshot / "files" / "claude" / "settings.json").chmod(0o400)

        problems = verify_snapshot(snapshot, check_permissions=True)
        self.assertTrue(any("permission mismatch" in problem for problem in problems), problems)

    def test_cli_rejects_traversal_ids_and_apply_without_expected_hash(self):
        """CLI identifiers stay direct children and apply cannot bypass its precondition."""
        import subprocess

        created = subprocess.run(
            ["./scripts/kingstack", "snapshot", "--home", str(self.home), "--print-id"],
            cwd=Path(__file__).parents[1], text=True, capture_output=True,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        identifier = created.stdout.strip()
        traversal = subprocess.run(
            ["./scripts/kingstack", "snapshot", "verify", "../" + identifier, "--home", str(self.home)],
            cwd=Path(__file__).parents[1], text=True, capture_output=True,
        )
        self.assertNotEqual(traversal.returncode, 0)
        apply = subprocess.run(
            [
                "./scripts/kingstack", "snapshot", "restore", identifier, "--home", str(self.home),
                "--destination-home", str(self.tempdir / "new-destination"), "--apply",
            ],
            cwd=Path(__file__).parents[1], text=True, capture_output=True,
        )
        self.assertNotEqual(apply.returncode, 0)

    def test_snapshot_creation_rejects_an_existing_or_symlinked_id_path(self):
        """A timing collision must fail instead of reusing or chmodding an existing path."""
        from kingstack.snapshot import create_snapshot
        from kingstack import snapshot as snapshot_module

        fixed_time = snapshot_module.datetime(2026, 8, 20, 12, 0, 0)
        occupied = self.snapshot_root / "snapshot-20260820-120000"
        occupied.parent.mkdir(parents=True)
        external = self.tempdir / "external"
        external.mkdir()
        occupied.symlink_to(external, target_is_directory=True)

        with patch("kingstack.snapshot.datetime") as clock:
            clock.utcnow.return_value = fixed_time
            with self.assertRaisesRegex(ValueError, "already exists|symlinked"):
                create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o755)

    def test_verify_rejects_noncanonical_manifest_aliases_and_malformed_records(self):
        """Equivalent-looking paths and incomplete records must not reach restore logic."""
        from kingstack.snapshot import create_snapshot, verify_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        manifest_path = snapshot / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][0]["path"] = "claude/./agents/read-only.json"
        manifest["files"].append({"path": "claude\\settings.json", "kind": "file"})
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest_path.chmod(0o600)

        problems = verify_snapshot(snapshot, check_permissions=True)
        self.assertTrue(any("invalid snapshot path" in problem for problem in problems), problems)
        self.assertTrue(any("invalid snapshot manifest record" in problem for problem in problems), problems)

    def test_dry_run_leaves_planted_journals_and_sentinels_unchanged(self):
        """Dry-run is observational even if a recovery journal is present or malformed."""
        from kingstack.snapshot import create_snapshot, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        destination.mkdir()
        sentinel = destination / "outside-sentinel"
        self._write(sentinel, b"unchanged\n", 0o640)
        journal = destination / ".kingstack-restore-journal.json"
        journal.write_bytes(b'{"target":"../../outside"}\n')
        journal.chmod(0o600)
        before = (journal.read_bytes(), stat.S_IMODE(journal.stat().st_mode), sentinel.read_bytes(), stat.S_IMODE(sentinel.stat().st_mode))

        restore_snapshot(snapshot, destination, dry_run=True)

        after = (journal.read_bytes(), stat.S_IMODE(journal.stat().st_mode), sentinel.read_bytes(), stat.S_IMODE(sentinel.stat().st_mode))
        self.assertEqual(after, before)

    def test_apply_refuses_unconfined_journal_without_touching_sentinel(self):
        """Malformed recovery metadata cannot name or mutate an outside target."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        destination.mkdir()
        sentinel = self.tempdir / "outside-sentinel"
        self._write(sentinel, b"unchanged\n", 0o640)
        journal = destination / ".kingstack-restore-journal.json"
        journal.write_text(json.dumps({"version": 1, "status": "prepared", "expected": "0" * 64,
                                       "stage": ".kingstack-restore-stage-x", "backup": ".kingstack-restore-backup-x",
                                       "entries": [{"target": "../../outside-sentinel", "backup": "0", "before": {"kind": "missing"}}], "parents": []}), encoding="utf-8")
        journal.chmod(0o600)

        with self.assertRaisesRegex(ValueError, "journal"):
            restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=current_destination_hash(snapshot, destination))
        self.assertEqual(sentinel.read_bytes(), b"unchanged\n")
        self.assertEqual(stat.S_IMODE(sentinel.stat().st_mode), 0o640)

    def test_apply_recovers_a_valid_interrupted_transaction_before_new_work(self):
        """A prepared journal restores its private backup before the next apply validates state."""
        import hashlib
        from kingstack.snapshot import create_snapshot, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        self._write(destination / ".claude" / "settings.json", b"new-partial\n", 0o600)
        backup = destination / ".kingstack-restore-backup-test"
        stage = destination / ".kingstack-restore-stage-test"
        backup.mkdir()
        stage.mkdir()
        self._write(backup / "0", b"old-before-interrupt\n", 0o600)
        before = {"kind": "file", "sha256": hashlib.sha256(b"old-before-interrupt\n").hexdigest(), "mode": "0600"}
        parent_before = {"kind": "dir", "mode": "0755"}
        journal = destination / ".kingstack-restore-journal.json"
        journal.write_text(json.dumps({
            "version": 1, "status": "prepared", "expected": "0" * 64,
            "destination": str(destination.resolve()), "snapshot": snapshot.name,
            "stage": stage.name, "backup": backup.name,
            "entries": [{"target": ".claude/settings.json", "backup": "0", "before": before}],
            "parents": [{"path": ".claude", "before": parent_before}],
        }), encoding="utf-8")
        journal.chmod(0o600)

        with self.assertRaisesRegex(ValueError, "expected current hash"):
            restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash="0" * 64)
        self.assertEqual((destination / ".claude" / "settings.json").read_bytes(), b"old-before-interrupt\n")
        self.assertFalse(journal.exists())
        self.assertFalse(backup.exists())
        self.assertFalse(stage.exists())

    def test_malformed_octal_manifest_mode_is_a_problem_not_an_exception(self):
        """A hostile mode field cannot crash the verifier before reporting invalidity."""
        from kingstack.snapshot import create_snapshot, verify_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        manifest_path = snapshot / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        file_record = next(record for record in manifest["files"] if record["kind"] == "file")
        file_record["mode"] = "not-octal"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest_path.chmod(0o600)

        problems = verify_snapshot(snapshot, check_permissions=True)
        self.assertTrue(any("invalid snapshot manifest file mode" in problem for problem in problems), problems)

    def test_journal_temp_collision_rolls_back_without_touching_destination(self):
        """An exclusive journal-temp failure leaves the pre-apply destination intact."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        self._write(destination / ".claude" / "settings.json", b"old-live\n", 0o600)
        sentinel = destination / "outside-sentinel"
        self._write(sentinel, b"unchanged\n", 0o640)
        temporary = destination / ".kingstack-restore-journal.json.tmp"
        self._write(temporary, b"occupied\n", 0o600)
        expected = current_destination_hash(snapshot, destination)

        with self.assertRaisesRegex(ValueError, "journal temporary"):
            restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=expected)
        self.assertEqual((destination / ".claude" / "settings.json").read_bytes(), b"old-live\n")
        self.assertEqual(sentinel.read_bytes(), b"unchanged\n")
        self.assertEqual(temporary.read_bytes(), b"occupied\n")
