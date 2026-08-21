from pathlib import Path
from unittest import TestCase

from kingstack.parity import rendered_parity
from kingstack.skills import load_catalog


ROOT = Path(__file__).parents[1]


class ClaudeParityTest(TestCase):
    def test_rendered_claude_parity_fails_on_one_intentional_mismatch(self):
        report = rendered_parity("claude", ROOT)
        broken = dict(report["ids"])
        broken["skill:how"] = {"state": "missing", "where": "none"}
        broken["skill:invented"] = {"state": "missing", "where": "none"}
        mismatches = [
            name
            for name, row in broken.items()
            if row["state"] not in {"in_bundle", "live_preserved"}
        ]
        self.assertIn("skill:how", mismatches)
        self.assertIn("skill:invented", mismatches)

    def test_rendered_claude_parity_covers_the_frozen_capability_ids(self):
        report = rendered_parity("claude", ROOT)
        catalog = load_catalog(ROOT)
        required = {
            "skill:{}".format(name) for name in catalog.available_names("claude")
        }
        required.update(
            {
                "agent:poteto-agent",
                "agent:comment-sicko",
                "hook:session_start",
                "hook:stop_capture",
                "hook:before_compaction",
                "hook:post_tool_use",
                "hook:subagent_start",
                "policy:compaction-200k",
                "policy:effort-medium",
                "policy:pstack-4612556",
                "skill:king-mode",
                "skill:memory-review",
            }
        )
        required.update("command:{}".format(name) for name in report["commands"])
        required.update("schedule:{}".format(name) for name in report["schedules"])
        required.update("sweep:{}".format(name) for name in report["sweeps"])
        required.update("instruction:{}".format(name) for name in report["instructions"])
        live_only = {
            "agent:poteto-agent",
            "agent:comment-sicko",
            "policy:compaction-200k",
            "policy:effort-medium",
        }
        live_only.update(
            "skill:{}".format(name)
            for name in catalog.available_names("claude")
            if catalog.owner(name) == "plugin-manager"
        )
        self.assertEqual(len(catalog.available_names("claude")), 66)
        self.assertEqual(len(report["commands"]), 16)
        self.assertEqual(len(report["schedules"]), 3)
        self.assertEqual(len(report["sweeps"]), 4)
        missing = [
            name
            for name in sorted(required - live_only)
            if report["ids"].get(name, {}).get("state")
            not in {"in_bundle", "live_preserved"}
        ]
        self.assertEqual(missing, [])
        self.assertTrue(report["ok"])
