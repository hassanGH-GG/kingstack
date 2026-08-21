import os
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.project_id import decode_claude_project_slug, identity_for_claude_bank, project_id


class ProjectIdTest(TestCase):
    def test_git_remote_and_worktree_share_identity(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        main = Path(temporary.name) / "main"
        main.mkdir()
        subprocess.run(["git", "init"], cwd=main, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "checkout", "-b", "main"], cwd=main, check=True, stdout=subprocess.DEVNULL)
        (main / "README").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "add", "README"], cwd=main, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "i"], cwd=main, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "remote", "add", "origin", "git@github.com:hassanGH-GG/kingstack.git"], cwd=main, check=True)
        worktree = Path(temporary.name) / "wt"
        subprocess.run(["git", "worktree", "add", str(worktree), "HEAD"], cwd=main, check=True, stdout=subprocess.DEVNULL)
        self.assertEqual(project_id(main), project_id(worktree))
        self.assertRegex(project_id(main), r"^p_[0-9a-f]{16}$")

    def test_basename_collision_is_not_identity(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        a = Path(temporary.name) / "a" / "foo"
        b = Path(temporary.name) / "b" / "foo"
        a.mkdir(parents=True)
        b.mkdir(parents=True)
        self.assertNotEqual(project_id(a), project_id(b))

    def test_claude_slug_decodes_hyphenated_project_names(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        real = Path(temporary.name) / "nbi-monorepo"
        real.mkdir()
        slug = "-" + "-".join(real.parts[1:])
        decoded = decode_claude_project_slug(slug)
        self.assertEqual(decoded, real)
        memory = Path(temporary.name) / "projects" / slug / "memory"
        memory.mkdir(parents=True)
        self.assertEqual(identity_for_claude_bank(memory).id, project_id(real))
