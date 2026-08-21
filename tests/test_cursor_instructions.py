from pathlib import Path
from unittest import TestCase

from kingstack.render import render_bundle
from kingstack.skills import render_skill_files


ROOT = Path(__file__).parents[1]


class CursorInstructionsTest(TestCase):
    def test_cursor_bundle_matches_codex_portable_skill_set(self):
        bundle = render_bundle("cursor", ROOT)
        text = bundle["AGENTS.md"].decode("utf-8")
        self.assertIn("portable capability tier", text)
        self.assertIn("shared curated memory", text.lower())
        self.assertIn("Cross-agent compatibility", text)
        self.assertIn("hooks.json", bundle)
        self.assertIn("hooks/run.py", bundle)
        skills = {path.split("/", 1)[0] for path in render_skill_files("cursor", ROOT)}
        self.assertEqual(len(skills), 53)
        self.assertIn("poteto-mode", skills)
        self.assertIn("king-mode", skills)
        self.assertIn("memory-review", skills)
