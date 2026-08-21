import json
from pathlib import Path
from unittest import TestCase

from kingstack.render import render_bundle


ROOT = Path(__file__).parents[1]


class CodexInstructionsTest(TestCase):
    def test_agents_md_covers_shared_policy_and_avoids_claude_commands(self):
        bundle = render_bundle("codex", ROOT)
        text = bundle["AGENTS.md"].decode("utf-8")
        self.assertIn("portable capability tier", text)
        self.assertIn("shared curated memory", text.lower())
        self.assertIn("~/Desktop/Work/kingstack", text)
        self.assertNotIn("/model", text)
        self.assertIn("Cross-agent compatibility", text)
        self.assertIn("hooks.json", bundle)
        self.assertIn("hooks/run.py", bundle)
        self.assertIn("config-owned.json", bundle)

    def test_hooks_json_is_a_codex_sequence_not_a_string(self):
        bundle = render_bundle("codex", ROOT)
        hooks = json.loads(bundle["hooks.json"].decode("utf-8"))
        events = ("SessionStart", "Stop", "PreCompact", "PostToolUse", "SubagentStart")
        for event in events:
            groups = hooks["hooks"][event]
            self.assertIsInstance(groups, list, event)
            command = groups[0]["hooks"][0]["command"]
            self.assertEqual(groups[0]["hooks"][0]["type"], "command")
            self.assertIn("hooks/run.py", command)
            self.assertIn(event, command)
