import json
import os
import stat
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase

from kingstack.hooks.claude import normalize, run_event
from kingstack.hooks.cursor import format_output as cursor_format
from kingstack.hooks.cursor import normalize as cursor_normalize
from kingstack.hooks.cursor import run_event as cursor_run_event
from kingstack.hooks.dispatch import HookError, handle


ROOT = Path(__file__).parents[1]
PRESERVE = (
    "PRESERVE VERBATIM in the summary, these outrank narrative: (1) the current "
    "finish condition, done means, exactly as last stated; (2) every file path "
    "edited or created this session and whether it is committed and pushed; "
    "(3) open decisions and anything Hassan corrected, in his words; (4) any "
    "command or step that was about to run next; (5) unpushed or uncommitted "
    "state named in the transcript. Drop pleasantries and process narration "
    "first, never these. (6) headroom archive ids and "
    "`kingstack headroom retrieve <id>`; drop raw tool blobs, keep the digest."
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
        self.assertNotIn("<identity>", context)
        self.assertNotIn("<headroom>", context)

    def test_session_start_personal_identity_and_live_headroom_ids(self):
        os.environ["KINGSTACK_IDENTITY"] = "personal"
        store = self.runtime / "headroom-store"
        store.mkdir()
        (store / "live.json").write_text(
            json.dumps({"ids": ["abcdabcdabcdabcd"]}) + "\n", encoding="utf-8"
        )
        os.environ["KINGSTACK_HEADROOM_ROOT"] = str(store)
        self.addCleanup(os.environ.pop, "KINGSTACK_IDENTITY", None)
        self.addCleanup(os.environ.pop, "KINGSTACK_HEADROOM_ROOT", None)
        context = handle(self.envelope("SessionStart", {}), self.runtime)["additionalContext"]
        self.assertIn("personal identity", context)
        self.assertIn("Do not run king-mode", context)
        self.assertIn("abcdabcdabcdabcd", context)

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

    def test_stop_skips_one_prompt_health_probes(self):
        transcript = self.runtime / "probe.jsonl"
        write_transcript(transcript, ["kingstack working ?"])
        handle(
            self.envelope(
                "Stop",
                {"transcript_path": str(transcript)},
                session_id="8ae5dbe3-session",
                project=str(self.runtime / "plugins"),
            ),
            self.runtime,
        )
        inbox = self.runtime / "memory-review.md"
        self.assertFalse(inbox.exists())
        write_transcript(transcript, ["say hello in exactly one word"])
        handle(
            self.envelope(
                "Stop",
                {"transcript_path": str(transcript)},
                session_id="9363ac24-session",
                project=str(self.runtime / "hexfy"),
            ),
            self.runtime,
        )
        self.assertFalse(inbox.exists())
        write_transcript(
            transcript,
            ["is kingstack working? prove it, do not change anything."],
        )
        handle(
            self.envelope(
                "Stop",
                {"transcript_path": str(transcript)},
                session_id="175bf6a0-session",
                project=str(self.runtime / "plugins"),
            ),
            self.runtime,
        )
        self.assertFalse(inbox.exists())
        write_transcript(
            transcript,
            ["Build a session-memory distiller that appends one inbox line."],
        )
        handle(
            self.envelope(
                "Stop",
                {"transcript_path": str(transcript)},
                session_id="e73e60d3-session",
                project=str(self.runtime / "plugins"),
            ),
            self.runtime,
        )
        self.assertIn("goal", inbox.read_text(encoding="utf-8"))
        self.assertIn("session-memory distiller", inbox.read_text(encoding="utf-8"))
        self.assertEqual(stat.S_IMODE(inbox.stat().st_mode), 0o600)

    def test_stop_skips_secret_like_corrections(self):
        transcript = self.runtime / "secret.jsonl"
        write_transcript(
            transcript,
            [
                "Build a session-memory distiller that appends one inbox line.",
                "no, rotate token: ghp_abcdefghijklmnopqrstuvwxyz123456",
            ],
        )
        handle(
            self.envelope(
                "Stop",
                {"transcript_path": str(transcript)},
                session_id="secret01-session",
                project=str(self.runtime / "plugins"),
            ),
            self.runtime,
        )
        inbox = self.runtime / "memory-review.md"
        text = inbox.read_text(encoding="utf-8")
        self.assertIn("goal", text)
        self.assertIn("session-memory distiller", text)
        self.assertNotIn("ghp_", text)
        self.assertEqual(stat.S_IMODE(inbox.stat().st_mode), 0o600)

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
        self.assertIn("headroom archive ids", result["additionalContext"])
        self.assertEqual(
            stat.S_IMODE(
                (self.runtime / "logs/compaction-checkpoints/12345678.md").stat().st_mode
            ),
            0o600,
        )

    def test_pre_compact_drops_secret_prompts(self):
        transcript = self.runtime / "transcript.jsonl"
        write_transcript(
            transcript,
            [
                "finish the hook core",
                "token: ghp_abcdefghijklmnopqrstuvwxyz123456",
            ],
        )
        handle(
            self.envelope(
                "PreCompact",
                {"transcript_path": str(transcript)},
                session_id="87654321-session",
            ),
            self.runtime,
        )
        checkpoint = (
            self.runtime / "logs/compaction-checkpoints/87654321.md"
        ).read_text(encoding="utf-8")
        self.assertIn("finish the hook core", checkpoint)
        self.assertNotIn("ghp_", checkpoint)
        self.assertEqual(
            stat.S_IMODE(
                (self.runtime / "logs/compaction-checkpoints/87654321.md").stat().st_mode
            ),
            0o600,
        )

    def test_post_tool_use_warns_only_above_the_frozen_threshold(self):
        small = handle(
            self.envelope(
                "PostToolUse",
                {"tool_name": "Read", "tool_response": "x" * 29999},
            ),
            self.runtime,
        )
        store = self.runtime / "headroom-store"
        os.environ["KINGSTACK_HEADROOM_ROOT"] = str(store)
        self.addCleanup(os.environ.pop, "KINGSTACK_HEADROOM_ROOT", None)
        large = handle(
            self.envelope(
                "PostToolUse",
                {"tool_name": "Read", "tool_response": "x" * 30000},
            ),
            self.runtime,
        )
        self.assertEqual(small, {})
        self.assertIn("headroom archived Read", large["systemMessage"])
        self.assertIn("tokens ", large["systemMessage"])

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

    def test_cursor_normalizer_maps_native_events_and_outputs(self):
        event = cursor_normalize(
            "sessionStart",
            {"session_id": "conv-1", "cwd": "/work/plugins", "composer_mode": "agent"},
        )
        self.assertEqual(event["event"], "SessionStart")
        self.assertEqual(event["agent"], "cursor")
        self.assertEqual(event["session_id"], "conv-1")
        self.assertEqual(event["project"], "/work/plugins")
        result = handle(event, self.runtime)
        output = json.loads(cursor_format("sessionStart", result))
        self.assertIn("pstack (poteto-mode)", output["additional_context"])
        root = output.get("env", {}).get("KINGSTACK_ROOT")
        self.assertTrue(root)
        self.assertTrue((Path(root) / "lib" / "kingstack").is_dir())
        store = self.runtime / "headroom-store"
        os.environ["KINGSTACK_HEADROOM_ROOT"] = str(store)
        self.addCleanup(os.environ.pop, "KINGSTACK_HEADROOM_ROOT", None)
        post = cursor_normalize(
            "postToolUse",
            {"tool_name": "Read", "tool_output": "x" * 30000, "cwd": "/work/plugins"},
        )
        large = handle(post, self.runtime)
        post_out = json.loads(cursor_format("postToolUse", large))
        self.assertIn("headroom archived Read", post_out["additional_context"])
        code, stop_out = cursor_run_event("stop", "{", self.runtime)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stop_out), {})
        with self.assertRaises(HookError):
            cursor_normalize("SessionStartX", {})
