import json
import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.statusline import context_tokens, render_status


class StatuslineTest(TestCase):
    def test_reads_newest_usage_and_warns_when_fat(self):
        handle = tempfile.NamedTemporaryFile("w", delete=False)
        handle.write(
            json.dumps({"message": {"usage": {"input_tokens": 1000, "cache_read_input_tokens": 160000}}})
            + "\n"
        )
        handle.close()
        self.assertEqual(context_tokens(handle.name), 161000)
        line = render_status(
            {
                "transcript_path": handle.name,
                "workspace": {"current_dir": "/tmp/kingstack"},
                "model": {"display_name": "opus"},
                "cost": {"total_cost_usd": 1.25},
            }
        )
        self.assertIn("ctx 161k", line)
        self.assertIn("/clear", line)
        self.assertIn("session $1.25", line)

    def test_missing_transcript_is_quiet(self):
        line = render_status(
            {
                "transcript_path": "",
                "workspace": {"current_dir": "/tmp/demo"},
                "model": {"display_name": "terra"},
                "cost": {},
            }
        )
        self.assertIn("demo", line)
        self.assertNotIn("ctx", line)
