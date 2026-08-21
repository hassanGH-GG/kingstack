from pathlib import Path
from unittest import TestCase

from kingstack.docs_hygiene import hygiene_errors


ROOT = Path(__file__).parents[1]


class DocsHygieneTest(TestCase):
    def test_every_tracked_markdown_file_is_classified(self):
        self.assertEqual(hygiene_errors(ROOT), [])
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("This repository *is* `~/.claude`", readme)
        self.assertIn("~/Desktop/Work/kingstack", readme)
