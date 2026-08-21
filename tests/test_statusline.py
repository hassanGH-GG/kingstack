import json
import tempfile
from unittest import TestCase

from kingstack.statusline import context_tokens, render_status, short_model, subagent_models


class StatuslineTest(TestCase):
    def test_prefers_payload_window_and_shows_effort_and_subagents(self):
        handle = tempfile.NamedTemporaryFile("w", delete=False)
        handle.write(
            json.dumps(
                {
                    "isSidechain": False,
                    "message": {
                        "model": "claude-opus-4-6",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Task",
                                "input": {"model": "claude-haiku-4-5", "prompt": "scan"},
                            }
                        ],
                        "usage": {"input_tokens": 1000, "cache_read_input_tokens": 160000},
                    },
                }
            )
            + "\n"
        )
        handle.close()
        line = render_status(
            {
                "transcript_path": handle.name,
                "workspace": {"current_dir": "/tmp/kingstack"},
                "model": {"display_name": "Opus", "id": "claude-opus-4-6"},
                "effort": {"level": "medium"},
                "context_window": {
                    "context_window_size": 200000,
                    "used_percentage": 24,
                    "current_usage": {
                        "input_tokens": 8000,
                        "cache_read_input_tokens": 40000,
                    },
                },
                "cost": {"total_cost_usd": 1.25},
            }
        )
        self.assertIn("model opus", line)
        self.assertIn("effort medium", line)
        self.assertIn("ctx 48k (24%)", line)
        self.assertIn("session $1.25", line)
        self.assertIn("subagents haiku", line)
        self.assertNotIn("/clear", line)
        self.assertEqual(short_model("claude-fable-5-thinking-high"), "fable")
        self.assertEqual(subagent_models({"transcript_path": handle.name}, "opus"), ["haiku"])

    def test_transcript_fallback_skips_sidechain_usage(self):
        handle = tempfile.NamedTemporaryFile("w", delete=False)
        handle.write(
            json.dumps(
                {
                    "isSidechain": False,
                    "message": {"usage": {"input_tokens": 20000, "cache_read_input_tokens": 0}},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "isSidechain": True,
                    "message": {
                        "model": "claude-sonnet-4-6",
                        "usage": {"input_tokens": 2000, "cache_read_input_tokens": 0},
                    },
                }
            )
            + "\n"
        )
        handle.close()
        self.assertEqual(context_tokens(handle.name), 20000)
        line = render_status(
            {
                "transcript_path": handle.name,
                "workspace": {"current_dir": "/tmp/demo"},
                "model": {"display_name": "opus"},
                "cost": {},
            }
        )
        self.assertIn("ctx 20k", line)
        self.assertIn("subagents sonnet", line)

    def test_missing_transcript_is_quiet(self):
        line = render_status(
            {
                "transcript_path": "",
                "workspace": {"current_dir": "/tmp/demo"},
                "model": {"display_name": "terra"},
                "effort": {"level": "low"},
                "cost": {},
            }
        )
        self.assertIn("demo", line)
        self.assertIn("model terra", line)
        self.assertIn("effort low", line)
        self.assertNotIn("ctx", line)
        self.assertNotIn("subagents", line)
