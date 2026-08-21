import io
import json
import os
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import TestCase

from kingstack.cli import main
from kingstack.handoff import attach_session, packet
from kingstack.hooks.dispatch import handle
from kingstack.project_id import project_id
from kingstack.session_context import project_index
from kingstack.session_store import (
    SessionStore,
    SessionStoreError,
    mark_handoff,
    record_from_hook,
    record_id,
)
from kingstack.setup import setup


ROOT = Path(__file__).parents[1]
CONTRACT = (ROOT / "adapters/claude/hooks/poteto-mode-context.md").read_text(
    encoding="utf-8"
)


def write_transcript(path, prompts):
    rows = [
        {"type": "user", "promptSource": "typed", "message": {"content": text}}
        for text in prompts
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class SessionStoreTest(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = SessionStore.open(self.root / "sessions")
        self.cwd = self.root / "proj"
        self.cwd.mkdir()
        self.project = project_id(self.cwd)

    def test_upsert_is_idempotent_and_windows_current(self):
        first = self.store.upsert(
            {
                "adapter": "claude",
                "session_id": "sess-1",
                "project_id": self.project,
                "last_prompts": ["build the store"],
            }
        )
        again = self.store.upsert(
            {
                "adapter": "claude",
                "session_id": "sess-1",
                "project_id": self.project,
                "last_prompts": ["keep the pointer, not the chat"],
            }
        )
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(first["started_at"], again["started_at"])
        self.assertEqual(again["last_prompts"], ["keep the pointer, not the chat"])
        current = self.store.current(self.project)
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["id"], first["id"])
        for index in range(21):
            self.store.upsert(
                {
                    "adapter": "cursor",
                    "session_id": "extra-{}".format(index),
                    "project_id": self.project,
                }
            )
        self.assertEqual(len(self.store.current(self.project)), 20)
        journal = (self.root / "sessions" / "sessions.jsonl").read_text(encoding="utf-8")
        self.assertGreaterEqual(len([line for line in journal.splitlines() if line.strip()]), 23)
        example = self.store.upsert(
            {
                "adapter": "example",
                "session_id": "future-1",
                "project_id": self.project,
                "status": "live",
            }
        )
        self.assertTrue(example["id"].startswith("s_"))
        self.assertEqual(example["adapter"], "example")
        shown = self.store.show(example["id"])
        self.assertNotIn("build the adapter transcript", json.dumps(shown))
        with self.assertRaises(SessionStoreError):
            SessionStore.open(ROOT / "sessions", repo_root=ROOT)
        with self.assertRaises(SessionStoreError):
            self.store.upsert({"adapter": "claude", "session_id": "x", "project_id": "p", "status": "nope"})

    def test_hook_and_cli_share_one_index(self):
        os.environ["KINGSTACK_SESSIONS_ROOT"] = str(self.root / "sessions")
        self.addCleanup(os.environ.pop, "KINGSTACK_SESSIONS_ROOT", None)
        runtime = self.root / "runtime"
        runtime.mkdir()
        (runtime / "hooks").mkdir()
        (runtime / "hooks" / "poteto-mode-context.md").write_text(CONTRACT, encoding="utf-8")
        (runtime / "logs" / "compaction-checkpoints").mkdir(parents=True)
        transcript = runtime / "transcript.jsonl"
        write_transcript(transcript, ["ship the session index"])
        envelope = {
            "event": "SessionStart",
            "agent": "claude",
            "session_id": "abc12345-session",
            "project": str(self.cwd),
            "payload": {},
        }
        start = handle(envelope, runtime)
        self.assertIn("<session_index>", start["additionalContext"])
        self.assertIn(record_id("claude", "abc12345-session"), start["additionalContext"])
        handle(
            {
                "event": "Stop",
                "agent": "claude",
                "session_id": "abc12345-session",
                "project": str(self.cwd),
                "payload": {"transcript_path": str(transcript)},
            },
            runtime,
        )
        handle(
            {
                "event": "PreCompact",
                "agent": "claude",
                "session_id": "abc12345-session",
                "project": str(self.cwd),
                "payload": {"transcript_path": str(transcript)},
            },
            runtime,
        )
        row = self.store.show("abc12345-session")
        self.assertEqual(row["status"], "compacted")
        self.assertEqual(row["last_prompts"], ["ship the session index"])
        self.assertTrue(row["checkpoint_path"].endswith("abc12345.md"))
        self.assertEqual(record_from_hook({"agent": "claude", "session_id": "x", "project": "/missing"}), None)
        document = packet("index is the working set", self.cwd)
        attach_session(
            document,
            self.cwd,
            packet_path=str(self.root / "HANDOFF.md"),
            session_key=row["id"],
            sessions_root=self.root / "sessions",
        )
        handed = self.store.show(row["id"])
        self.assertEqual(handed["status"], "handed-off")
        self.assertEqual(handed["finish_condition"], "index is the working set")
        injected = project_index(self.store, self.cwd, max_bytes=80)
        self.assertIn("truncated", injected)
        sink = io.StringIO()
        with redirect_stdout(sink):
            code = main(
                ["session", "list", "--cwd", str(self.cwd), "--root", str(self.root / "sessions")]
            )
        self.assertEqual(code, 0)
        with redirect_stdout(sink):
            show = main(
                ["session", "show", row["id"], "--root", str(self.root / "sessions")]
            )
        self.assertEqual(show, 0)
        with redirect_stdout(sink), redirect_stderr(sink):
            missing = main(
                ["session", "show", "no-such-session", "--root", str(self.root / "sessions")]
            )
        self.assertEqual(missing, 2)
        with redirect_stdout(sink):
            continue_code = main(
                [
                    "session",
                    "continue",
                    row["id"],
                    "--root",
                    str(self.root / "sessions"),
                    "--cwd",
                    str(self.cwd),
                    "--out",
                    str(self.root / "HANDOFF.md"),
                ]
            )
        self.assertEqual(continue_code, 0)
        self.assertIn("index is the working set", (self.root / "HANDOFF.md").read_text(encoding="utf-8"))

    def test_setup_creates_the_store_and_profile_names_it(self):
        home = self.root / "home"
        home.mkdir()
        runtime = home / ".kingstack"
        report = setup(checkout=ROOT, runtime=runtime, identity="personal", home=home)
        self.assertIn("empty session store", report["got"])
        self.assertTrue((runtime / "sessions" / "sessions.jsonl").is_file())
        from kingstack.profile import hook_environment
        env = hook_environment(home)
        self.assertEqual(env["KINGSTACK_SESSIONS_ROOT"], str(runtime / "sessions"))

    def test_secrets_and_empty_packet_do_not_corrupt_the_index(self):
        os.environ["KINGSTACK_SESSIONS_ROOT"] = str(self.root / "sessions")
        self.addCleanup(os.environ.pop, "KINGSTACK_SESSIONS_ROOT", None)
        transcript = self.root / "secret.jsonl"
        write_transcript(transcript, ["rotate sk-ant-api03-not-a-real-key-value"])
        record_from_hook(
            {
                "agent": "claude",
                "session_id": "secret-session",
                "project": str(self.cwd),
            },
            transcript=str(transcript),
        )
        row = self.store.show("secret-session")
        self.assertEqual(row["last_prompts"], [])
        packet = "/tmp/handoff-keep.md"
        self.store.upsert(
            {
                "adapter": "claude",
                "session_id": "secret-session",
                "project_id": self.project,
                "packet_path": packet,
            }
        )
        mark_handoff(
            self.cwd,
            "keep the packet pointer",
            packet_path="",
            session_key=row["id"],
            root=self.root / "sessions",
        )
        self.assertEqual(self.store.show(row["id"])["packet_path"], packet)
        leak = ROOT / "docs" / "session-leak-probe"
        sink = io.StringIO()
        with redirect_stdout(sink), redirect_stderr(sink):
            code = main(["session", "list", "--root", str(leak)])
        self.assertEqual(code, 2)
        self.assertFalse(leak.exists())

    def test_close_and_sweep_drop_empty_live_rows(self):
        smoke = self.store.upsert(
            {
                "adapter": "cursor",
                "session_id": "smoke-empty",
                "project_id": self.project,
                "status": "live",
            }
        )
        kept = self.store.upsert(
            {
                "adapter": "claude",
                "session_id": "real-work",
                "project_id": self.project,
                "status": "live",
                "transcript_path": "/tmp/real.jsonl",
                "last_prompts": ["ship the leftover"],
            }
        )
        swept = self.store.sweep_empty()
        self.assertEqual([row["id"] for row in swept], [smoke["id"]])
        self.assertEqual(self.store.show(smoke["id"])["status"], "done")
        self.assertEqual(self.store.show(kept["id"])["status"], "live")
        current = self.store.current(self.project)
        self.assertEqual([row["id"] for row in current], [kept["id"]])
        closed = self.store.close_record(kept["id"])
        self.assertEqual(closed["status"], "done")
        self.assertEqual(self.store.current(self.project), [])
        sink = io.StringIO()
        with redirect_stdout(sink):
            code = main(
                [
                    "session",
                    "close",
                    smoke["id"],
                    "--root",
                    str(self.root / "sessions"),
                ]
            )
        self.assertEqual(code, 0)
        with redirect_stdout(sink):
            sweep_code = main(
                ["session", "sweep", "--root", str(self.root / "sessions")]
            )
        self.assertEqual(sweep_code, 0)
