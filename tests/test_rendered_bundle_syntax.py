import json
import subprocess
from pathlib import Path
from unittest import TestCase

from kingstack.adapter_contract import load_adapter
from kingstack.render import render_bundle
from kingstack.skills import _frontmatter


ROOT = Path(__file__).parents[1]


class RenderedBundleSyntaxTest(TestCase):
    def test_claude_bundle_bytes_are_syntactically_valid_without_publication(self):
        declaration = load_adapter(ROOT / "adapters/claude/adapter.json")
        bundle = render_bundle("claude", ROOT)
        self.assertIn("hooks/run.py", bundle)
        self.assertIn("hooks/session-start.sh", bundle)
        for path, content in bundle.items():
            self.assertTrue(
                any(path == owned or path.startswith(owned + "/") for owned in declaration.owned_paths),
                path,
            )
            suffix = Path(path).suffix
            if suffix == ".sh":
                parsed = subprocess.run(
                    ["bash", "-n"],
                    input=content,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.assertEqual(parsed.returncode, 0, parsed.stderr.decode())
            elif suffix == ".py":
                compile(content, path, "exec")
            elif suffix == ".json":
                json.loads(content.decode("utf-8"))
            elif path.endswith("/SKILL.md") or path == "CLAUDE.md":
                text = content.decode("utf-8")
                if path.endswith("/SKILL.md"):
                    _frontmatter(content, path)
                self.assertTrue(text.endswith("\n"))
                self.assertNotIn("\r", text)
