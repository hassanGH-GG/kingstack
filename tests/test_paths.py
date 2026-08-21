from pathlib import Path
from unittest import TestCase

from kingstack.paths import Paths


class PathsTest(TestCase):
    def test_defaults_are_agent_neutral_and_runtime_is_outside_repo(self):
        p = Paths.for_home(Path("/Users/test"))
        self.assertEqual(p.repo, Path("/Users/test/Desktop/Work/kingstack"))
        self.assertEqual(p.runtime, Path("/Users/test/.kingstack"))
        self.assertEqual(p.claude_home, Path("/Users/test/.claude"))
        self.assertEqual(p.codex_home, Path("/Users/test/.codex"))
        self.assertFalse(p.runtime.is_relative_to(p.repo))
