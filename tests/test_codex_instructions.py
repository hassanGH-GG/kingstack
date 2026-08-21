import json
import os
import subprocess
import sys
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

    def test_owned_status_line_uses_only_codex_item_ids(self):
        allowed = set(json.loads((ROOT / "adapters/codex/status-line-items.json").read_text()))
        self.assertNotIn("tokens", allowed)
        self.assertNotIn("cwd", allowed)
        owned = json.loads((ROOT / "adapters/codex/config-owned.json").read_text())
        unknown = [item for item in owned["tui.status_line"] if item not in allowed]
        self.assertEqual(unknown, [])

    def test_codex_run_py_emits_codex_hook_json(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "lib")
        env["KINGSTACK_RUNTIME"] = str(ROOT / "adapters/codex")
        runner = ROOT / "adapters/codex/hooks/run.py"
        started = subprocess.run(
            [sys.executable, str(runner), "SessionStart"],
            input=b"{}",
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(started.returncode, 0, started.stderr.decode())
        payload = json.loads(started.stdout)
        self.assertIn("hookSpecificOutput", payload)
        self.assertNotIn("additionalContext", payload)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("Kingstack policy applies on Codex", payload["hookSpecificOutput"]["additionalContext"])
        stopped = subprocess.run(
            [sys.executable, str(runner), "Stop"],
            input=b"{}",
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(stopped.returncode, 0, stopped.stderr.decode())
        self.assertEqual(json.loads(stopped.stdout), {})
