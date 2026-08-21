import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


def run_git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def git_result(repo: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def remote_refs(repo: Path) -> str:
    return run_git(
        repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/remotes",
    )


class BootstrapTest(TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp()).resolve()
        self.origin = self.tempdir / "origin.git"
        self.source = self.tempdir / "source"
        self.destination = self.tempdir / "kingstack"
        self.runtime = self.tempdir / "runtime"
        self.home = self.tempdir / "home"
        self.claude_home = self.home / ".claude"
        self.codex_home = self.home / ".codex"

        subprocess.run(
            ["git", "init", "--bare", str(self.origin)], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "init", "-b", "main", str(self.source)], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        run_git(self.source, "config", "user.email", "test@example.com")
        run_git(self.source, "config", "user.name", "Test User")
        (self.source / "docs").mkdir()
        (self.source / "docs/.gitkeep").write_text("", encoding="utf-8")
        run_git(self.source, "add", "docs/.gitkeep")
        run_git(self.source, "commit", "-m", "initial")
        run_git(self.source, "tag", "v-test")
        run_git(self.source, "remote", "add", "origin", str(self.origin))
        run_git(self.source, "push", "-u", "origin", "main", "--tags")

        self.claude_home.mkdir(parents=True)
        self.codex_home.mkdir(parents=True)
        (self.claude_home / "settings.json").write_text(
            json.dumps({"api": {"token": "top-secret-value"}}), encoding="utf-8",
        )
        (self.codex_home / "config.toml").write_text(
            'model = "test"\napi_key = "other-secret"\n', encoding="utf-8",
        )
        memory = self.claude_home / "projects/demo/memory"
        memory.mkdir(parents=True)
        (memory / "MEMORY.md").write_text("# memory\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _bootstrap(self, **overrides):
        from kingstack.bootstrap import bootstrap

        arguments = {
            "source_repo": self.source,
            "destination": self.destination,
            "runtime": self.runtime,
            "baseline_homes": [self.claude_home, self.codex_home],
        }
        arguments.update(overrides)
        return bootstrap(**arguments)

    def _make_unpushed_commit(self):
        (self.source / "local.txt").write_text("local\n", encoding="utf-8")
        run_git(self.source, "add", "local.txt")
        run_git(self.source, "commit", "-m", "local")

    def test_dirty_source_is_always_refused_without_writes(self):
        from kingstack.bootstrap import BootstrapError

        (self.source / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        for allow_unpushed in (False, True):
            with self.subTest(allow_unpushed=allow_unpushed):
                with self.assertRaises(BootstrapError):
                    self._bootstrap(allow_unpushed=allow_unpushed)
                self.assertFalse(self.destination.exists())
                self.assertFalse(self.runtime.exists())

    def test_unpushed_history_requires_explicit_permission(self):
        from kingstack.bootstrap import BootstrapError

        self._make_unpushed_commit()
        with self.assertRaises(BootstrapError):
            self._bootstrap()
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.runtime.exists())

        result = self._bootstrap(allow_unpushed=True)
        self.assertEqual(result["source"]["ahead"], 1)

    def test_clone_preserves_head_origin_tags_and_writes_only_redacted_baseline(self):
        result = self._bootstrap()

        self.assertEqual(
            run_git(self.destination, "rev-parse", "HEAD"),
            run_git(self.source, "rev-parse", "HEAD"),
        )
        self.assertEqual(
            run_git(self.destination, "remote", "get-url", "origin"),
            str(self.origin),
        )
        self.assertIn("v-test", run_git(self.destination, "tag").splitlines())
        self.assertEqual(
            run_git(self.destination, "rev-parse", "--abbrev-ref", "@{upstream}"),
            run_git(self.source, "rev-parse", "--abbrev-ref", "@{upstream}"),
        )
        self.assertEqual(remote_refs(self.destination), remote_refs(self.source))
        self.assertEqual(run_git(self.destination, "fsck", "--full"), "")
        self.assertEqual(
            run_git(self.destination, "status", "--short", "--untracked-files=all"),
            "?? docs/baselines/claude-codex-baseline.json",
        )

        public = self.destination / "docs/baselines/claude-codex-baseline.json"
        private = self.runtime / "bootstrap/manifest.json"
        self.assertEqual(json.loads(private.read_text(encoding="utf-8")), result)
        encoded = public.read_text(encoding="utf-8")
        self.assertNotIn(str(self.home), encoded)
        self.assertNotIn("top-secret-value", encoded)
        self.assertNotIn("other-secret", encoded)
        self.assertEqual(stat.S_IMODE(self.runtime.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(private.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)

    def test_dry_run_reports_exact_writes_without_creating_any_path(self):
        result = self._bootstrap(dry_run=True)

        self.assertTrue(result["dry_run"])
        self.assertEqual(
            result["would_write"],
            [
                str(self.destination.absolute()),
                str(self.destination.absolute() / "docs/baselines/claude-codex-baseline.json"),
                str(self.runtime.absolute()),
                str(self.runtime.absolute() / "bootstrap"),
                str(self.runtime.absolute() / "bootstrap/manifest.json"),
            ],
        )
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.runtime.exists())

    def test_existing_runtime_is_tightened_without_touching_its_contents(self):
        self.runtime.mkdir(mode=0o755)
        self.runtime.chmod(0o755)
        sentinel = self.runtime / "historical-snapshot"
        sentinel.write_text("keep\n", encoding="utf-8")

        self._bootstrap()

        self.assertEqual(stat.S_IMODE(self.runtime.stat().st_mode), 0o700)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")

    def test_symlinked_runtime_is_refused_without_following_it(self):
        external = self.tempdir / "external"
        external.mkdir()
        self.runtime.symlink_to(external, target_is_directory=True)

        from kingstack.bootstrap import BootstrapError

        with self.assertRaises(BootstrapError):
            self._bootstrap()
        self.assertFalse(self.destination.exists())
        self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o755)

    def test_destination_and_runtime_cannot_overlap_native_homes(self):
        from kingstack.bootstrap import BootstrapError

        cases = [
            (self.claude_home / "kingstack", self.runtime),
            (self.codex_home / "kingstack", self.runtime),
            (self.destination, self.claude_home / "runtime"),
            (self.destination, self.codex_home / "runtime"),
            (self.destination, self.home),
        ]
        for destination, runtime in cases:
            with self.subTest(destination=destination, runtime=runtime):
                with self.assertRaisesRegex(BootstrapError, "overlap"):
                    self._bootstrap(destination=destination, runtime=runtime)
                self.assertFalse((self.claude_home / "kingstack").exists())
                self.assertFalse((self.codex_home / "kingstack").exists())
                self.assertFalse((self.claude_home / "runtime").exists())
                self.assertFalse((self.codex_home / "runtime").exists())

    def test_baseline_home_parent_alias_cannot_hide_native_destination(self):
        from kingstack.bootstrap import BootstrapError

        alias = self.tempdir / "home-alias"
        alias.symlink_to(self.home, target_is_directory=True)
        native_destination = self.claude_home / "nested-kingstack"

        with self.assertRaisesRegex(BootstrapError, "overlap|symlink"):
            self._bootstrap(
                destination=native_destination,
                baseline_homes=[alias / ".claude", alias / ".codex"],
            )

        self.assertFalse(native_destination.exists())
        self.assertFalse(self.runtime.exists())

    def test_destination_parent_swap_during_source_check_never_redirects_clone(self):
        from kingstack import bootstrap as bootstrap_module
        from kingstack.bootstrap import BootstrapError

        safe_parent = self.tempdir / "safe-parent"
        safe_parent.mkdir()
        original_parent = self.tempdir / "safe-parent-original"
        external = self.tempdir / "external-parent"
        external.mkdir()
        destination = safe_parent / "kingstack"
        original_source_state = bootstrap_module._source_state

        def swap_parent(source_repo):
            state = original_source_state(source_repo)
            safe_parent.rename(original_parent)
            safe_parent.symlink_to(external, target_is_directory=True)
            return state

        with patch("kingstack.bootstrap._source_state", side_effect=swap_parent):
            with self.assertRaisesRegex(BootstrapError, "changed|symlink"):
                self._bootstrap(destination=destination)

        self.assertFalse((external / "kingstack").exists())
        self.assertFalse((original_parent / "kingstack").exists())
        self.assertFalse(self.runtime.exists())

    def test_symlinked_destination_parent_is_refused_without_external_write(self):
        from kingstack.bootstrap import BootstrapError

        external = self.tempdir / "external-destination"
        external.mkdir()
        linked_parent = self.tempdir / "linked-destination"
        linked_parent.symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(BootstrapError, "symlink"):
            self._bootstrap(destination=linked_parent / "kingstack")
        self.assertEqual(list(external.iterdir()), [])

    def test_symlinked_runtime_parent_is_refused_without_external_write(self):
        from kingstack.bootstrap import BootstrapError

        external = self.tempdir / "external-runtime"
        external.mkdir()
        linked_parent = self.tempdir / "linked-runtime"
        linked_parent.symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(BootstrapError, "symlink"):
            self._bootstrap(runtime=linked_parent / "runtime")
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(external.iterdir()), [])

    def test_cloned_symlinked_baseline_parent_never_overwrites_external_file(self):
        from kingstack.bootstrap import BootstrapError

        external = self.tempdir / "external-baseline"
        external.mkdir()
        sentinel = external / "claude-codex-baseline.json"
        sentinel.write_text("external-sentinel\n", encoding="utf-8")
        (self.source / "docs/baselines").symlink_to(external, target_is_directory=True)
        run_git(self.source, "add", "docs/baselines")
        run_git(self.source, "commit", "-m", "adversarial baseline link")

        with self.assertRaisesRegex(BootstrapError, "symlink"):
            self._bootstrap(allow_unpushed=True)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "external-sentinel\n")

    def test_existing_cloned_baseline_is_never_overwritten(self):
        from kingstack.bootstrap import BootstrapError

        baseline_dir = self.source / "docs/baselines"
        baseline_dir.mkdir()
        baseline = baseline_dir / "claude-codex-baseline.json"
        baseline.write_text("tracked-sentinel\n", encoding="utf-8")
        run_git(self.source, "add", "docs/baselines/claude-codex-baseline.json")
        run_git(self.source, "commit", "-m", "tracked baseline sentinel")

        with self.assertRaisesRegex(BootstrapError, "exists"):
            self._bootstrap(allow_unpushed=True)
        cloned = self.destination / "docs/baselines/claude-codex-baseline.json"
        self.assertEqual(cloned.read_text(encoding="utf-8"), "tracked-sentinel\n")

    def test_manifest_publication_race_never_overwrites_contender(self):
        from kingstack.bootstrap import BootstrapError, _write_private_manifest

        private_dir = self.runtime / "bootstrap"
        private_dir.mkdir(parents=True)
        manifest = private_dir / "manifest.json"
        real_link = os.link

        def racing_link(source, destination, **keywords):
            descriptor = os.open(
                destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
                dir_fd=keywords["dst_dir_fd"],
            )
            with os.fdopen(descriptor, "wb") as contender:
                contender.write(b'{"contender": true}\n')
            return real_link(source, destination, **keywords)

        with patch("kingstack.inventory.os.link", side_effect=racing_link):
            with self.assertRaisesRegex(BootstrapError, "exists"):
                _write_private_manifest(manifest, {"bootstrap": True})

        self.assertEqual(manifest.read_bytes(), b'{"contender": true}\n')
        self.assertEqual([path.name for path in private_dir.iterdir()], ["manifest.json"])

    def test_private_manifest_commit_survives_owned_parent_close_error(self):
        from kingstack import inventory as inventory_module
        from kingstack.bootstrap import _write_private_manifest

        private_dir = self.runtime / "bootstrap"
        private_dir.mkdir(parents=True)
        manifest = private_dir / "manifest.json"
        original_open = inventory_module.open_directory_no_symlinks
        original_close = os.close
        owned_parent = []

        def record_parent(path, *arguments, **keywords):
            descriptor = original_open(path, *arguments, **keywords)
            if Path(path) == private_dir:
                owned_parent.append(descriptor)
            return descriptor

        def close_with_commit_error(descriptor):
            original_close(descriptor)
            if owned_parent and descriptor == owned_parent[0] and manifest.exists():
                raise OSError("injected owned-parent close error after commit")

        with patch(
            "kingstack.inventory.open_directory_no_symlinks",
            side_effect=record_parent,
        ), patch("kingstack.inventory.os.close", side_effect=close_with_commit_error):
            _write_private_manifest(manifest, {"bootstrap": True})

        self.assertEqual(
            json.loads(manifest.read_text(encoding="utf-8")), {"bootstrap": True},
        )

    def test_parent_change_after_manifest_never_returns_failure_with_success_record(self):
        from kingstack import bootstrap as bootstrap_module
        from kingstack.bootstrap import BootstrapError

        safe_parent = self.tempdir / "publish-parent"
        safe_parent.mkdir()
        original_parent = self.tempdir / "publish-parent-original"
        replacement_parent = self.tempdir / "publish-parent-replacement"
        replacement_parent.mkdir()
        destination = safe_parent / "kingstack"
        manifest = self.runtime / "bootstrap/manifest.json"
        original_writer = bootstrap_module._write_private_manifest

        def publish_then_change_parent(path, value):
            original_writer(path, value)
            safe_parent.rename(original_parent)
            safe_parent.symlink_to(replacement_parent, target_is_directory=True)

        failure = None
        with patch(
            "kingstack.bootstrap._write_private_manifest",
            side_effect=publish_then_change_parent,
        ):
            try:
                self._bootstrap(destination=destination)
            except BootstrapError as error:
                failure = error

        if failure is not None:
            self.assertFalse(manifest.exists(), "a failed run left a success manifest")
            safe_parent.unlink()
            original_parent.rename(safe_parent)
            self._bootstrap(destination=destination)

        self.assertTrue(manifest.is_file())

    def test_parent_descriptor_close_error_cannot_turn_committed_success_into_failure(self):
        from kingstack import bootstrap as bootstrap_module

        manifest = self.runtime / "bootstrap/manifest.json"
        original_open = bootstrap_module.open_directory_no_symlinks
        original_close = os.close
        held_parent = []

        def record_parent(path, *arguments, **keywords):
            descriptor = original_open(path, *arguments, **keywords)
            if Path(path) == self.destination.parent:
                held_parent.append(descriptor)
            return descriptor

        def close_with_late_error(descriptor):
            original_close(descriptor)
            if held_parent and descriptor == held_parent[0] and manifest.exists():
                raise OSError("injected close error after success publication")

        with patch(
            "kingstack.bootstrap.open_directory_no_symlinks",
            side_effect=record_parent,
        ), patch("kingstack.bootstrap.os.close", side_effect=close_with_late_error):
            result = self._bootstrap()

        self.assertEqual(json.loads(manifest.read_text(encoding="utf-8")), result)

    def test_clone_with_no_source_upstream_has_no_manufactured_upstream_or_refs(self):
        run_git(self.source, "checkout", "-b", "feature/no-upstream")
        self._make_unpushed_commit()
        self.assertNotEqual(git_result(self.source, "rev-parse", "@{upstream}").returncode, 0)

        self._bootstrap(allow_unpushed=True)

        self.assertNotEqual(
            git_result(self.destination, "rev-parse", "@{upstream}").returncode, 0,
        )
        self.assertEqual(remote_refs(self.destination), remote_refs(self.source))
        self.assertNotIn("refs/remotes/origin/feature/no-upstream", remote_refs(self.destination))

    def test_existing_destination_is_refused_without_mutation(self):
        from kingstack.bootstrap import BootstrapError

        self.destination.mkdir()
        sentinel = self.destination / "sentinel"
        sentinel.write_text("keep\n", encoding="utf-8")
        with self.assertRaises(BootstrapError):
            self._bootstrap()
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
        self.assertFalse(self.runtime.exists())
