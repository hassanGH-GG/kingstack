import json
import os
import stat
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase

from kingstack.hooks.claude import normalize, run_event
from kingstack.hooks.dispatch import HookError, handle


ROOT = Path(__file__).parents[1]
PRESERVE = (
    "PRESERVE VERBATIM in the summary, these outrank narrative: (1) the current "
    "finish condition, done means, exactly as last stated; (2) every file path "
    "edited or created this session and whether it is committed and pushed; "
    "(3) open decisions and anything Hassan corrected, in his words; (4) any "
    "command or step that was about to run next; (5) unpushed or uncommitted "
    "state named in the transcript. Drop pleasantries and process narration "
    "first, never these."
)
CONTRACT = (ROOT / "adapters/claude/hooks/poteto-mode-context.md").read_text(
    encoding="utf-8"
)


def write_transcript(path, prompts):
    rows = []
    for text in prompts:
        rows.append(
            {
                "type": "user",
                "promptSource": "typed",
                "message": {"content": text},
            }
        )
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class HookContractTest(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.runtime = Path(self.temporary.name) / "runtime"
        self.runtime.mkdir()
        (self.runtime / "hooks").mkdir()
        (self.runtime / "hooks" / "poteto-mode-context.md").write_text(
            CONTRACT, encoding="utf-8"
        )
        (self.runtime / "logs" / "compaction-checkpoints").mkdir(parents=True)
        self.yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    def envelope(self, event, payload, session_id="session-123", project=None):
        return {
            "event": event,
            "agent": "claude",
            "session_id": session_id,
            "project": project or str(self.runtime),
            "payload": payload,
        }

    def test_session_start_injects_contract_pending_count_and_usage(self):
        inbox = self.runtime / "memory-review.md"
        inbox.write_text(
            "# Memory review inbox\n\n- [ ] 2026-08-20 10:00 | plugins | goal | do the thing | 2 prompts | abcdef12 | /tmp/t.jsonl\n",
            encoding="utf-8",
        )
        os.utime(inbox, (1_724_000_000, 1_724_000_000))
        (self.runtime / "usage-ledger.csv").write_text(
            "date,model,x,turns,a,b,c,y,usd\n{},haiku,x,4,1000,1000,2000,y,12\n".format(
                self.yesterday
            ),
            encoding="utf-8",
        )
        result = handle(
            self.envelope("SessionStart", {}),
            self.runtime,
        )
        context = result["additionalContext"]
        self.assertIn("pstack (poteto-mode)", context)
        self.assertIn("<memory_inbox>1 memory candidate(s) are waiting", context)
        self.assertIn("<usage>yesterday:", context)
        self.assertIn("4 turns", context)

    def test_stop_captures_latest_correction_and_never_blocks(self):
        transcript = self.runtime / "transcript.jsonl"
        write_transcript(
            transcript,
            ["build the adapter", "no, keep the live homes read-only"],
        )
        result = handle(
            self.envelope(
                "Stop",
                {"transcript_path": str(transcript)},
                session_id="abcdef12-session",
                project=str(self.runtime / "plugins"),
            ),
            self.runtime,
        )
        self.assertEqual(result.get("blocked"), False)
        inbox = (self.runtime / "memory-review.md").read_text(encoding="utf-8")
        self.assertIn("correction", inbox)
        self.assertIn("keep the live homes read-only", inbox)
        self.assertIn("abcdef12", inbox)

        code, output = run_event("Stop", "{", self.runtime)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), {})

    def test_pre_compact_writes_checkpoint_and_preserve_directive(self):
        transcript = self.runtime / "transcript.jsonl"
        write_transcript(transcript, ["finish the hook core"])
        result = handle(
            self.envelope(
                "PreCompact",
                {"transcript_path": str(transcript)},
                session_id="12345678-session",
            ),
            self.runtime,
        )
        self.assertEqual(result["additionalContext"], PRESERVE)
        checkpoint = (
            self.runtime / "logs/compaction-checkpoints/12345678.md"
        ).read_text(encoding="utf-8")
        self.assertIn("session 12345678", checkpoint)
        self.assertIn("finish the hook core", checkpoint)

    def test_post_tool_use_warns_only_above_the_frozen_threshold(self):
        small = handle(
            self.envelope(
                "PostToolUse",
                {"tool_name": "Read", "tool_response": "x" * 29999},
            ),
            self.runtime,
        )
        large = handle(
            self.envelope(
                "PostToolUse",
                {"tool_name": "Read", "tool_response": "x" * 30000},
            ),
            self.runtime,
        )
        self.assertEqual(small, {})
        self.assertIn("Read result ~29KB", large["systemMessage"])
        self.assertIn("haiku subagent", large["systemMessage"])

    def test_subagent_start_reports_model_effort_role_and_inherit_smell(self):
        named = handle(
            self.envelope(
                "SubagentStart",
                {
                    "role": "builder",
                    "model": "sonnet",
                    "effort": "medium",
                    "task": "render the adapter",
                },
            ),
            self.runtime,
        )
        inherited = handle(
            self.envelope(
                "SubagentStart",
                {"task": "quick look"},
            ),
            self.runtime,
        )
        self.assertEqual(
            named["systemMessage"],
            "↳ spawn [builder] render the adapter · model=sonnet effort=medium",
        )
        self.assertIn("model=inherit", inherited["systemMessage"])
        self.assertIn("⚠ no model set", inherited["systemMessage"])

    def test_claude_normalizer_maps_native_payloads_only(self):
        event = normalize(
            "SubagentStart",
            {
                "session_id": "session-123",
                "cwd": "/work/plugins",
                "tool_input": {
                    "description": "render the adapter",
                    "model": "sonnet",
                    "effort": "medium",
                    "subagent_type": "builder",
                },
            },
        )
        self.assertEqual(event["event"], "SubagentStart")
        self.assertEqual(event["agent"], "claude")
        self.assertEqual(event["project"], "/work/plugins")
        self.assertEqual(event["payload"]["role"], "builder")
        self.assertEqual(event["payload"]["task"], "render the adapter")
        with self.assertRaises(HookError):
            handle({"event": "SessionStart"}, self.runtime)

    def test_handlers_write_only_under_the_injected_runtime(self):
        before = {}
        live = Path.home() / ".claude"
        for path in (
            live / "memory-review.md",
            live / "memory-review.error.log",
        ):
            if path.exists():
                before[path] = (path.stat().st_mtime_ns, path.stat().st_size)
        handle(
            self.envelope(
                "Stop",
                {"transcript_path": str(self.runtime / "missing.jsonl")},
            ),
            self.runtime,
        )
        for path, fingerprint in before.items():
            self.assertEqual(
                (path.stat().st_mtime_ns, path.stat().st_size),
                fingerprint,
            )
        self.assertFalse((self.runtime / "memory-review.md").exists())
        self.assertTrue((self.runtime / "memory-review.error.log").exists())
