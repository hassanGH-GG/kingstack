import json
import os
import shutil
import stat
import tempfile
import hashlib
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

    def _plant_journal(
        self,
        snapshot,
        destination,
        *,
        status="prepared",
        target=".claude/settings.json",
        before=None,
        parent_before=None,
        backup_payload=None,
        backup_symlink=None,
        staged_payload=b"staged\n",
    ):
        """Plant a complete v1 recovery journal accepted by the prior implementation."""
        destination.mkdir(parents=True, exist_ok=True)
        stage = destination / ".kingstack-restore-stage-valid"
        backup = destination / ".kingstack-restore-backup-valid"
        stage.mkdir(mode=0o700)
        backup.mkdir(mode=0o700)
        if staged_payload is not None:
            self._write(stage / "0", staged_payload, 0o600)
        if backup_payload is not None:
            self._write(backup / "0", backup_payload, 0o600)
        elif backup_symlink is not None:
            (backup / "0").symlink_to(backup_symlink)
        if before is None:
            before = {"kind": "missing"}
        if parent_before is None:
            parent_before = {"kind": "dir", "mode": "0755"}
        payload = {
            "version": 1,
            "status": status,
            "expected": "0" * 64,
            "destination": str(destination.resolve()),
            "snapshot": snapshot.name,
            "stage": stage.name,
            "backup": backup.name,
            "entries": [{"target": target, "backup": "0", "before": before}],
            "parents": [{"path": ".claude", "before": parent_before}],
        }
        journal = destination / ".kingstack-restore-journal.json"
        journal.write_text(json.dumps(payload), encoding="utf-8")
        journal.chmod(0o600)
        return journal, stage, backup

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

    def test_dry_run_with_complete_pending_journal_is_byte_for_byte_read_only(self):
        """Even a valid pending transaction is only reported, never recovered by dry-run."""
        from kingstack.snapshot import create_snapshot, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        destination.mkdir()
        stage = destination / ".kingstack-restore-stage-valid"
        backup = destination / ".kingstack-restore-backup-valid"
        stage.mkdir()
        backup.mkdir()
        journal = destination / ".kingstack-restore-journal.json"
        payload = {
            "version": 1, "status": "prepared", "expected": "0" * 64,
            "destination": str(destination.resolve()), "snapshot": snapshot.name,
            "stage": stage.name, "backup": backup.name, "entries": [], "parents": [],
        }
        journal.write_text(json.dumps(payload), encoding="utf-8")
        journal.chmod(0o600)
        before = (journal.read_bytes(), stat.S_IMODE(journal.stat().st_mode), stage.stat().st_mtime_ns, backup.stat().st_mtime_ns)

        restore_snapshot(snapshot, destination, dry_run=True)

        after = (journal.read_bytes(), stat.S_IMODE(journal.stat().st_mode), stage.stat().st_mtime_ns, backup.stat().st_mtime_ns)
        self.assertEqual(after, before)

    def test_apply_refuses_symlinked_valid_journal_backup_without_outside_mutation(self):
        """A syntactically valid journal cannot redirect recovery through a backup symlink."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        self._write(destination / ".claude" / "settings.json", b"partial-new\n", 0o600)
        outside = self.tempdir / "outside"
        outside.mkdir()
        sentinel = outside / "sentinel"
        self._write(sentinel, b"unchanged\n", 0o640)
        old = b"old-before-interrupt\n"
        self._write(outside / "0", old, 0o600)
        stage = destination / ".kingstack-restore-stage-valid"
        stage.mkdir(mode=0o700)
        self._write(stage / "0", b"staged-new\n", 0o600)
        backup = destination / ".kingstack-restore-backup-valid"
        backup.symlink_to(outside, target_is_directory=True)
        before = {
            "kind": "file",
            "sha256": hashlib.sha256(old).hexdigest(),
            "mode": "0600",
        }
        journal = destination / ".kingstack-restore-journal.json"
        journal.write_text(json.dumps({
            "version": 1, "status": "prepared", "expected": "0" * 64,
            "destination": str(destination.resolve()), "snapshot": snapshot.name,
            "stage": stage.name, "backup": backup.name,
            "entries": [{"target": ".claude/settings.json", "backup": "0", "before": before}],
            "parents": [{"path": ".claude", "before": {"kind": "dir", "mode": "0755"}}],
        }), encoding="utf-8")
        journal.chmod(0o600)

        with self.assertRaisesRegex(ValueError, "journal"):
            restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=current_destination_hash(snapshot, destination))
        self.assertEqual(sentinel.read_bytes(), b"unchanged\n")
        self.assertEqual(stat.S_IMODE(sentinel.stat().st_mode), 0o640)

    def test_verify_reports_control_character_and_bad_type_records(self):
        """Hostile JSON types, NULs, and control characters must never escape verification."""
        from kingstack.snapshot import create_snapshot, verify_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        manifest_path = snapshot / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"].append({"path": "claude/evil\u0000name", "kind": [], "sha256": [], "mode": [], "target": {}})
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest_path.chmod(0o600)

        problems = verify_snapshot(snapshot, check_permissions=True)
        self.assertTrue(problems)
        self.assertTrue(any("invalid" in problem or "denylisted" in problem for problem in problems), problems)

    def test_recovery_unlink_stays_anchored_during_post_validation_parent_rebind(self):
        """Rebinding a validated target parent cannot redirect the actual rollback unlink."""
        from kingstack import snapshot as snapshot_module
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        self._write(destination / ".claude" / "settings.json", b"partial-new\n", 0o600)
        self._plant_journal(snapshot, destination, before={"kind": "missing"})
        outside = self.tempdir / "outside"
        outside.mkdir()
        sentinel = outside / "settings.json"
        self._write(sentinel, b"outside-sentinel\n", 0o640)
        relocated = destination / ".claude-relocated"
        real_validate = snapshot_module._validate_journal_physical
        rebound = False

        def validate_and_keep_descriptors(*args, **kwargs):
            nonlocal rebound
            result = real_validate(*args, **kwargs)
            rebound = True
            (destination / ".claude").rename(relocated)
            (destination / ".claude").symlink_to(outside, target_is_directory=True)
            return result

        expected = current_destination_hash(snapshot, destination)
        with patch("kingstack.snapshot._validate_journal_physical", side_effect=validate_and_keep_descriptors):
            with self.assertRaises(ValueError):
                restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=expected)

        self.assertTrue(rebound)
        self.assertEqual(sentinel.read_bytes(), b"outside-sentinel\n")
        self.assertEqual(stat.S_IMODE(sentinel.stat().st_mode), 0o640)

    def test_apply_refuses_full_journal_with_symlinked_target_ancestor(self):
        """A complete journal cannot traverse a target ancestor symlink during recovery."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        destination.mkdir()
        outside = self.tempdir / "outside"
        outside.mkdir()
        sentinel = outside / "settings.json"
        self._write(sentinel, b"outside-sentinel\n", 0o640)
        (destination / ".claude").symlink_to(outside, target_is_directory=True)
        self._plant_journal(snapshot, destination, before={"kind": "missing"}, parent_before={"kind": "missing"})

        with self.assertRaisesRegex(ValueError, "journal"):
            restore_snapshot(
                snapshot,
                destination,
                dry_run=False,
                expected_current_hash=current_destination_hash(snapshot, destination),
            )
        self.assertEqual(sentinel.read_bytes(), b"outside-sentinel\n")

    def test_apply_refuses_full_journal_with_symlinked_backup_entry(self):
        """A backup entry must physically match its recorded before-state before rollback."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        self._write(destination / ".claude" / "settings.json", b"partial-new\n", 0o600)
        outside = self.tempdir / "outside"
        outside.mkdir()
        sentinel = outside / "sentinel"
        self._write(sentinel, b"outside-sentinel\n", 0o640)
        before = {
            "kind": "file",
            "sha256": hashlib.sha256(b"old-before\n").hexdigest(),
            "mode": "0600",
        }
        self._plant_journal(snapshot, destination, before=before, backup_symlink=sentinel)

        with self.assertRaisesRegex(ValueError, "journal"):
            restore_snapshot(
                snapshot,
                destination,
                dry_run=False,
                expected_current_hash=current_destination_hash(snapshot, destination),
            )
        self.assertEqual(sentinel.read_bytes(), b"outside-sentinel\n")
        self.assertTrue((destination / ".kingstack-restore-journal.json").exists())

    def test_valid_prepared_journal_with_missing_parents_recovers_then_applies(self):
        """A journal published before parent creation remains recoverable after a crash."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        destination.mkdir()
        expected = current_destination_hash(snapshot, destination)
        journal, stage, backup = self._plant_journal(
            snapshot,
            destination,
            before={"kind": "missing"},
            parent_before={"kind": "missing"},
        )
        self.assertFalse((destination / ".claude").exists())

        restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=expected)

        self.assertEqual((destination / ".claude" / "settings.json").read_bytes(), b'{"theme":"dark"}\n')
        self.assertFalse(journal.exists())
        self.assertFalse(stage.exists())
        self.assertFalse(backup.exists())

    def test_apply_refuses_journal_temp_symlink_without_outside_mutation(self):
        """The exclusive descriptor-relative journal temporary never follows a static symlink."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        self._write(destination / ".claude" / "settings.json", b"old-live\n", 0o600)
        outside = self.tempdir / "outside-sentinel"
        self._write(outside, b"outside-sentinel\n", 0o640)
        temporary = destination / ".kingstack-restore-journal.json.tmp"
        temporary.symlink_to(outside)
        expected = current_destination_hash(snapshot, destination)

        with self.assertRaisesRegex(ValueError, "journal temporary"):
            restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=expected)
        self.assertTrue(temporary.is_symlink())
        self.assertEqual(outside.read_bytes(), b"outside-sentinel\n")
        self.assertEqual((destination / ".claude" / "settings.json").read_bytes(), b"old-live\n")

    def test_manifest_mode_type_and_each_control_path_are_rejected_independently(self):
        """Unhashable modes and every C0/C1 control path produce verifier problems."""
        from kingstack.snapshot import create_snapshot, verify_snapshot

        for field, value in (("mode", []), ("path", "claude/bad\x00name"),
                             ("path", "claude/bad\x1fname"), ("path", "claude/bad\x7fname"),
                             ("path", "claude/bad\x85name")):
            with self.subTest(field=field, value=repr(value)):
                root = self.tempdir / ("snapshots-" + str(len(list(self.tempdir.iterdir()))))
                snapshot = create_snapshot(Paths.for_home(self.home), root, "before-migration")
                manifest_path = snapshot / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                record = next(item for item in manifest["files"] if item["kind"] == "file")
                record[field] = value
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                manifest_path.chmod(0o600)

                problems = verify_snapshot(snapshot, check_permissions=True)
                self.assertTrue(any("invalid" in problem for problem in problems), problems)

    def test_journal_status_mode_and_each_control_path_raise_controlled_value_error(self):
        """Malformed journal types and controls never escape as TypeError or OSError."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        cases = [
            ("status", []),
            ("mode", []),
            ("target", ".claude/bad\x00name"),
            ("target", ".claude/bad\x1fname"),
            ("target", ".claude/bad\x7fname"),
            ("target", ".claude/bad\x85name"),
        ]
        for index, (field, value) in enumerate(cases):
            with self.subTest(field=field, value=repr(value)):
                destination = self.tempdir / ("journal-home-" + str(index))
                destination.mkdir()
                journal, _, _ = self._plant_journal(snapshot, destination)
                payload = json.loads(journal.read_text(encoding="utf-8"))
                if field == "status":
                    payload["status"] = value
                elif field == "mode":
                    payload["entries"][0]["before"] = {
                        "kind": "file", "sha256": "0" * 64, "mode": value,
                    }
                else:
                    payload["entries"][0]["target"] = value
                journal.write_text(json.dumps(payload), encoding="utf-8")
                journal.chmod(0o600)

                with self.assertRaisesRegex(ValueError, "journal"):
                    restore_snapshot(
                        snapshot,
                        destination,
                        dry_run=False,
                        expected_current_hash=current_destination_hash(snapshot, destination),
                    )

    def test_expected_hash_bad_type_raises_controlled_value_error(self):
        """An unhashable expected hash is rejected before membership or filesystem mutation."""
        from kingstack.snapshot import create_snapshot, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        with self.assertRaisesRegex(ValueError, "expected current hash"):
            restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=["not-a-hash"])
        self.assertFalse(destination.exists())

    def test_creation_refuses_source_root_rebind_without_reading_replacement(self):
        """Source reads remain on the opened root descriptor after its pathname is rebound."""
        from kingstack.snapshot import create_snapshot

        outside = self.tempdir / "outside-claude"
        shutil.copytree(self.home / ".claude", outside, symlinks=True)
        self._write(outside / "settings.json", b"outside-secret\n", 0o600)
        relocated = self.home / ".claude-relocated"
        real_mkdir = os.mkdir
        rebound = False

        def rebind_after_snapshot_mkdir(path, *args, **kwargs):
            nonlocal rebound
            result = real_mkdir(path, *args, **kwargs)
            if not rebound and Path(os.fspath(path)).name.startswith("snapshot-"):
                rebound = True
                (self.home / ".claude").rename(relocated)
                (self.home / ".claude").symlink_to(outside, target_is_directory=True)
            return result

        with patch("kingstack.snapshot.os.mkdir", side_effect=rebind_after_snapshot_mkdir):
            with self.assertRaisesRegex(ValueError, "source root changed"):
                create_snapshot(Paths.for_home(self.home), self.snapshot_root, "source-rebind")

        self.assertTrue(rebound)
        self.assertEqual((outside / "settings.json").read_bytes(), b"outside-secret\n")
        self.assertFalse(any(self.snapshot_root.glob("snapshot-*")))

    def test_creation_refuses_destination_root_rebind_without_writing_replacement(self):
        """Snapshot writes remain on the opened destination descriptor after pathname rebind."""
        from kingstack.snapshot import create_snapshot

        self.snapshot_root.mkdir(mode=0o700)
        relocated = self.tempdir / "private-snapshots-relocated"
        outside = self.tempdir / "outside-snapshot-root"
        outside.mkdir()
        sentinel = outside / "sentinel"
        self._write(sentinel, b"outside-sentinel\n", 0o640)
        real_mkdir = os.mkdir
        rebound = False

        def rebind_after_snapshot_mkdir(path, *args, **kwargs):
            nonlocal rebound
            result = real_mkdir(path, *args, **kwargs)
            if not rebound and Path(os.fspath(path)).name.startswith("snapshot-"):
                rebound = True
                self.snapshot_root.rename(relocated)
                self.snapshot_root.symlink_to(outside, target_is_directory=True)
            return result

        with patch("kingstack.snapshot.os.mkdir", side_effect=rebind_after_snapshot_mkdir):
            with self.assertRaisesRegex(ValueError, "destination root changed|symlinked"):
                create_snapshot(Paths.for_home(self.home), self.snapshot_root, "destination-rebind")

        self.assertTrue(rebound)
        self.assertEqual(sentinel.read_bytes(), b"outside-sentinel\n")
        self.assertEqual(sorted(path.name for path in outside.iterdir()), ["sentinel"])
        self.assertFalse(any(relocated.glob("snapshot-*")))

    def test_creation_never_succeeds_after_nested_snapshot_directory_relocation(self):
        """Relocating an opened files/claude directory cannot publish an invalid snapshot."""
        from kingstack import snapshot as snapshot_module
        from kingstack.snapshot import create_snapshot, verify_snapshot

        outside = self.tempdir / "outside-snapshot-data"
        outside.mkdir()
        sentinel = outside / "sentinel"
        self._write(sentinel, b"outside-sentinel\n", 0o640)
        real_copy = snapshot_module._copy_source_entry
        real_unlink = os.unlink
        real_rmdir = os.rmdir
        real_fsync = os.fsync
        relocated = False
        events = []

        def identity(descriptor):
            details = os.fstat(descriptor)
            return details.st_dev, details.st_ino

        def relocate_open_claude_directory(*args, **kwargs):
            nonlocal relocated
            destination_parent_fd = args[1]
            path_text = args[3]
            if not relocated and path_text == "claude/settings.json":
                files_fd = os.open(
                    "..", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=destination_parent_fd,
                )
                try:
                    os.rename(
                        "claude", "claude-relocated",
                        src_dir_fd=files_fd, dst_dir_fd=files_fd,
                    )
                finally:
                    os.close(files_fd)
                relocated = True
            return real_copy(*args, **kwargs)

        def traced_unlink(name, *args, **kwargs):
            parent_fd = kwargs.get("dir_fd")
            self.assertIsNotNone(parent_fd)
            events.append(("unlink", os.fspath(name), identity(parent_fd)))
            return real_unlink(name, *args, **kwargs)

        def traced_rmdir(name, *args, **kwargs):
            parent_fd = kwargs.get("dir_fd")
            self.assertIsNotNone(parent_fd)
            events.append(("rmdir", os.fspath(name), identity(parent_fd)))
            return real_rmdir(name, *args, **kwargs)

        def traced_fsync(descriptor):
            events.append(("fsync", "", identity(descriptor)))
            return real_fsync(descriptor)

        created = None
        with patch(
            "kingstack.snapshot._copy_source_entry",
            side_effect=relocate_open_claude_directory,
        ), patch("kingstack.snapshot.os.unlink", side_effect=traced_unlink), \
                patch("kingstack.snapshot.os.rmdir", side_effect=traced_rmdir), \
                patch("kingstack.snapshot.os.fsync", side_effect=traced_fsync):
            try:
                created = create_snapshot(
                    Paths.for_home(self.home), self.snapshot_root,
                    "nested-destination-relocation",
                )
            except ValueError:
                pass

        self.assertTrue(relocated)
        if created is not None:
            self.assertEqual(
                verify_snapshot(created, check_permissions=True),
                [],
                "snapshot creation returned success for an invalid named tree",
            )
            self.assertEqual(
                (created / "files" / "claude" / "settings.json").read_bytes(),
                b'{"theme":"dark"}\n',
            )
        self.assertEqual(list(self.snapshot_root.iterdir()), [])
        self.assertEqual(sentinel.read_bytes(), b"outside-sentinel\n")
        self.assertEqual(stat.S_IMODE(sentinel.stat().st_mode), 0o640)
        deletion_indexes = [
            index for index, event in enumerate(events)
            if event[0] in {"unlink", "rmdir"}
        ]
        self.assertTrue(deletion_indexes, events)
        for index in deletion_indexes:
            self.assertLess(index + 1, len(events), events)
            self.assertEqual(events[index + 1][0], "fsync", events[index:index + 2])
            self.assertEqual(events[index + 1][2], events[index][2])

    def test_interruption_after_backup_rename_is_recovered_to_before_state(self):
        """A crash after target-to-backup rename leaves a durable prepared rollback."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        self._write(destination / ".claude" / "settings.json", b"old-live\n", 0o600)
        expected = current_destination_hash(snapshot, destination)
        real_rename = os.rename
        real_replace = os.replace
        interrupted = False

        def maybe_interrupt(operation):
            def wrapper(source, target, *args, **kwargs):
                nonlocal interrupted
                result = operation(source, target, *args, **kwargs)
                source_name = Path(os.fspath(source)).name
                target_name = Path(os.fspath(target)).name
                if not interrupted and target_name.isdigit() and not source_name.isdigit():
                    interrupted = True
                    raise KeyboardInterrupt("injected after backup rename")
                return result
            return wrapper

        with patch("kingstack.snapshot.os.rename", side_effect=maybe_interrupt(real_rename)), \
                patch("kingstack.snapshot.os.replace", side_effect=maybe_interrupt(real_replace)):
            with self.assertRaises(KeyboardInterrupt):
                restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=expected)
        self.assertTrue(interrupted)

        with self.assertRaisesRegex(ValueError, "expected current hash"):
            restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash="0" * 64)
        self.assertEqual((destination / ".claude" / "settings.json").read_bytes(), b"old-live\n")
        self.assertFalse((destination / ".kingstack-restore-journal.json").exists())

    def test_interruptions_around_committed_journal_recover_correct_side(self):
        """Prepared crashes roll back, while durably committed crashes retain restored bytes."""
        from kingstack import snapshot as snapshot_module
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        for after_write in (False, True):
            with self.subTest(after_write=after_write):
                destination = self.tempdir / ("commit-home-" + str(after_write))
                self._write(destination / ".claude" / "settings.json", b"old-live\n", 0o600)
                expected = current_destination_hash(snapshot, destination)
                real_write = snapshot_module._write_journal

                def interrupt_committed(*args, **kwargs):
                    transaction = args[-1]
                    if transaction["status"] == "committed" and not after_write:
                        raise KeyboardInterrupt("injected before committed journal")
                    result = real_write(*args, **kwargs)
                    if transaction["status"] == "committed" and after_write:
                        raise KeyboardInterrupt("injected after committed journal")
                    return result

                with patch("kingstack.snapshot._write_journal", side_effect=interrupt_committed):
                    with self.assertRaises(KeyboardInterrupt):
                        restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=expected)

                with self.assertRaisesRegex(ValueError, "expected current hash"):
                    restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash="0" * 64)
                wanted = b'{"theme":"dark"}\n' if after_write else b"old-live\n"
                self.assertEqual((destination / ".claude" / "settings.json").read_bytes(), wanted)
                self.assertFalse((destination / ".kingstack-restore-journal.json").exists())

    def test_committed_recovery_never_cleans_up_when_restored_content_is_absent(self):
        """A committed journal remains recoverable if its claimed target is missing."""
        from kingstack import snapshot as snapshot_module
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        self._write(destination / ".claude" / "settings.json", b"old-live\n", 0o600)
        expected = current_destination_hash(snapshot, destination)
        real_write = snapshot_module._write_journal

        def interrupt_after_commit(*args, **kwargs):
            result = real_write(*args, **kwargs)
            if args[-1]["status"] == "committed":
                raise KeyboardInterrupt("injected after committed journal")
            return result

        with patch("kingstack.snapshot._write_journal", side_effect=interrupt_after_commit):
            with self.assertRaises(KeyboardInterrupt):
                restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=expected)
        journal = destination / ".kingstack-restore-journal.json"
        backup_dirs = list(destination.glob(".kingstack-restore-backup-*"))
        self.assertTrue(journal.exists())
        (destination / ".claude" / "settings.json").unlink()

        with self.assertRaisesRegex(ValueError, "committed|journal"):
            restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash="0" * 64)
        self.assertTrue(journal.exists())
        self.assertTrue(all(path.exists() for path in backup_dirs))

    def test_committed_recovery_finishes_after_backup_cleanup_crash(self):
        """Committed after-state is sufficient once a durable backup cleanup has happened."""
        from kingstack import snapshot as snapshot_module
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        self._write(destination / ".claude" / "settings.json", b"old-live\n", 0o600)
        expected = current_destination_hash(snapshot, destination)
        real_remove = snapshot_module._remove_tree_if_identity
        interrupted = False

        def interrupt_after_backup_cleanup(parent_fd, name, identity):
            nonlocal interrupted
            result = real_remove(parent_fd, name, identity)
            if not interrupted and name.startswith(".kingstack-restore-backup-"):
                interrupted = True
                raise KeyboardInterrupt("injected after durable backup cleanup")
            return result

        with patch(
            "kingstack.snapshot._remove_tree_if_identity",
            side_effect=interrupt_after_backup_cleanup,
        ):
            with self.assertRaises(KeyboardInterrupt):
                restore_snapshot(
                    snapshot,
                    destination,
                    dry_run=False,
                    expected_current_hash=expected,
                )
        self.assertTrue(interrupted)
        journal = destination / ".kingstack-restore-journal.json"
        self.assertTrue(journal.exists())
        self.assertFalse(any(destination.glob(".kingstack-restore-backup-*")))

        with self.assertRaisesRegex(ValueError, "expected current hash"):
            restore_snapshot(
                snapshot,
                destination,
                dry_run=False,
                expected_current_hash="0" * 64,
            )
        self.assertEqual(
            (destination / ".claude" / "settings.json").read_bytes(),
            b'{"theme":"dark"}\n',
        )
        self.assertFalse(journal.exists())

    def test_cleanup_refuses_transaction_directory_created_after_validation(self):
        """An absent transaction directory cannot be rebound to attacker data for cleanup."""
        from kingstack import snapshot as snapshot_module
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        self._write(destination / ".claude" / "settings.json", b"old-live\n", 0o600)
        expected = current_destination_hash(snapshot, destination)
        real_write = snapshot_module._write_journal

        def interrupt_after_commit(*args, **kwargs):
            result = real_write(*args, **kwargs)
            if args[-1]["status"] == "committed":
                raise KeyboardInterrupt("injected after committed journal")
            return result

        with patch("kingstack.snapshot._write_journal", side_effect=interrupt_after_commit):
            with self.assertRaises(KeyboardInterrupt):
                restore_snapshot(
                    snapshot,
                    destination,
                    dry_run=False,
                    expected_current_hash=expected,
                )
        journal_path = destination / ".kingstack-restore-journal.json"
        transaction = json.loads(journal_path.read_text(encoding="utf-8"))
        stage = destination / transaction["stage"]
        shutil.rmtree(stage)
        replacement_sentinel = stage / "sentinel"
        real_validate = snapshot_module._validate_journal_physical

        def replace_after_validation(*args, **kwargs):
            context = real_validate(*args, **kwargs)
            stage.mkdir(mode=0o700)
            self._write(replacement_sentinel, b"attacker-data\n", 0o600)
            return context

        with patch(
            "kingstack.snapshot._validate_journal_physical",
            side_effect=replace_after_validation,
        ):
            with self.assertRaises(ValueError):
                restore_snapshot(
                    snapshot,
                    destination,
                    dry_run=False,
                    expected_current_hash="0" * 64,
                )
        self.assertEqual(replacement_sentinel.read_bytes(), b"attacker-data\n")
        self.assertTrue(journal_path.exists())

    def test_prepared_cleanup_retains_journal_after_validated_stage_relocation(self):
        """A relocated validated stage is emptied durably without discarding recovery state."""
        from kingstack import snapshot as snapshot_module
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(
            Paths.for_home(self.home), self.snapshot_root, "before-migration"
        )
        destination = self.tempdir / "restore-home"
        self._write(
            destination / ".claude" / "settings.json", b"partial-new\n", 0o600
        )
        old = b"old-before-interrupt\n"
        before = {
            "kind": "file",
            "sha256": hashlib.sha256(old).hexdigest(),
            "mode": "0600",
        }
        journal, stage, backup = self._plant_journal(
            snapshot, destination, before=before, backup_payload=old
        )
        outside = self.tempdir / "outside-transaction-data"
        outside.mkdir()
        sentinel = outside / "sentinel"
        self._write(sentinel, b"outside-sentinel\n", 0o640)
        relocated_stage = outside / stage.name
        expected = current_destination_hash(snapshot, destination)
        real_validate = snapshot_module._validate_journal_physical
        real_unlink = os.unlink
        real_fsync = os.fsync
        stage_identity = None
        relocated = False
        events = []

        def identity(descriptor):
            details = os.fstat(descriptor)
            return details.st_dev, details.st_ino

        def relocate_stage_after_validation(*args, **kwargs):
            nonlocal relocated, stage_identity
            context = real_validate(*args, **kwargs)
            if not relocated:
                stage_identity = identity(context["stage_fd"])
                stage.rename(relocated_stage)
                relocated = True
            return context

        def traced_unlink(name, *args, **kwargs):
            parent_fd = kwargs.get("dir_fd")
            self.assertIsNotNone(parent_fd)
            events.append(("unlink", os.fspath(name), identity(parent_fd)))
            return real_unlink(name, *args, **kwargs)

        def traced_fsync(descriptor):
            events.append(("fsync", "", identity(descriptor)))
            return real_fsync(descriptor)

        with patch(
            "kingstack.snapshot._validate_journal_physical",
            side_effect=relocate_stage_after_validation,
        ), patch("kingstack.snapshot.os.unlink", side_effect=traced_unlink), \
                patch("kingstack.snapshot.os.fsync", side_effect=traced_fsync):
            with self.assertRaises(ValueError):
                restore_snapshot(
                    snapshot,
                    destination,
                    dry_run=False,
                    expected_current_hash=expected,
                )

        self.assertTrue(relocated)
        self.assertEqual(
            (destination / ".claude" / "settings.json").read_bytes(), old
        )
        self.assertTrue(journal.exists(), "incomplete cleanup discarded its journal")
        self.assertTrue(backup.exists())
        self.assertTrue(relocated_stage.is_dir())
        self.assertEqual(
            list(relocated_stage.iterdir()), [],
            "relocated staged payload survived cleanup",
        )
        self.assertEqual(sentinel.read_bytes(), b"outside-sentinel\n")
        self.assertEqual(stat.S_IMODE(sentinel.stat().st_mode), 0o640)
        self.assertFalse(any(event[1] == journal.name for event in events))
        stage_unlink = next(
            index for index, event in enumerate(events)
            if event == ("unlink", "0", stage_identity)
        )
        self.assertEqual(events[stage_unlink + 1], ("fsync", "", stage_identity))

    def test_nested_mutations_use_dir_fds_and_fsync_every_renamed_parent(self):
        """Every actual rename is descriptor-relative and synced in both affected parents."""
        from kingstack.snapshot import create_snapshot, current_destination_hash, restore_snapshot

        snapshot = create_snapshot(Paths.for_home(self.home), self.snapshot_root, "before-migration")
        destination = self.tempdir / "restore-home"
        self._write(destination / ".claude" / "settings.json", b"old-live\n", 0o600)
        expected = current_destination_hash(snapshot, destination)
        events = []
        real_rename = os.rename
        real_fsync = os.fsync
        real_mkdir = os.mkdir
        real_fchmod = os.fchmod

        def inode(descriptor):
            details = os.fstat(descriptor)
            return details.st_dev, details.st_ino

        def traced_rename(source, target, *args, **kwargs):
            source_fd = kwargs.get("src_dir_fd")
            target_fd = kwargs.get("dst_dir_fd")
            self.assertIsNotNone(source_fd)
            self.assertIsNotNone(target_fd)
            source_identity = os.stat(source, dir_fd=source_fd, follow_symlinks=False)
            events.append(("rename", os.fspath(source), os.fspath(target), inode(source_fd), inode(target_fd),
                           (source_identity.st_dev, source_identity.st_ino)))
            return real_rename(source, target, *args, **kwargs)

        def traced_fsync(descriptor):
            events.append(("fsync", inode(descriptor)))
            return real_fsync(descriptor)

        def traced_mkdir(path, *args, **kwargs):
            parent_fd = kwargs.get("dir_fd")
            self.assertIsNotNone(parent_fd)
            result = real_mkdir(path, *args, **kwargs)
            child = os.stat(path, dir_fd=parent_fd, follow_symlinks=False)
            events.append(("mkdir", os.fspath(path), inode(parent_fd), (child.st_dev, child.st_ino)))
            return result

        def traced_fchmod(descriptor, mode):
            events.append(("chmod", inode(descriptor), mode))
            return real_fchmod(descriptor, mode)

        with patch("kingstack.snapshot.os.rename", side_effect=traced_rename), \
                patch("kingstack.snapshot.os.fsync", side_effect=traced_fsync), \
                patch("kingstack.snapshot.os.mkdir", side_effect=traced_mkdir), \
                patch("kingstack.snapshot.os.fchmod", side_effect=traced_fchmod):
            restore_snapshot(snapshot, destination, dry_run=False, expected_current_hash=expected)

        rename_indexes = [index for index, event in enumerate(events) if event[0] == "rename"]
        self.assertTrue(rename_indexes, events)
        for position, event_index in enumerate(rename_indexes):
            event = events[event_index]
            stop = rename_indexes[position + 1] if position + 1 < len(rename_indexes) else len(events)
            sync_events = [item[1] for item in events[event_index + 1:stop] if item[0] == "fsync"]
            synced = set(sync_events)
            self.assertIn(event[3], synced, (event, events[event_index + 1:stop]))
            self.assertIn(event[4], synced, (event, events[event_index + 1:stop]))
            if event[3] != event[4]:
                self.assertEqual(
                    sync_events[:2],
                    [event[4], event[3]],
                    (event, events[event_index + 1:stop]),
                )
            if event[2] == ".kingstack-restore-journal.json":
                already_synced = {item[1] for item in events[:event_index] if item[0] == "fsync"}
                self.assertIn(event[5], already_synced, events[:event_index])
        for event_index, event in enumerate(events):
            if event[0] == "mkdir":
                first_rename = next((index for index in rename_indexes if index > event_index), len(events))
                synced = {item[1] for item in events[event_index + 1:first_rename] if item[0] == "fsync"}
                self.assertIn(event[2], synced, (event, events[event_index + 1:first_rename]))
                self.assertIn(event[3], synced, (event, events[event_index + 1:first_rename]))
            elif event[0] == "chmod":
                first_rename = next((index for index in rename_indexes if index > event_index), len(events))
                synced = {item[1] for item in events[event_index + 1:first_rename] if item[0] == "fsync"}
                self.assertIn(event[1], synced, (event, events[event_index + 1:first_rename]))
