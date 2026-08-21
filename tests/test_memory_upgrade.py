import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.handoff import packet, write_packet
from kingstack.hooks.inbox import Candidate, Inbox, inbox_path
from kingstack.memory_candidate import make_candidate
from kingstack.memory_consolidate import consolidate
from kingstack.memory_harvest import harvest
from kingstack.memory_review import promote
from kingstack.memory_store import MemoryStore
from kingstack.project_id import project_identity


class MemoryUpgradeTest(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = MemoryStore.open(self.root / "memory")
        self.cwd = self.root / "proj"
        self.cwd.mkdir()

    def test_consolidate_proposes_near_duplicates_and_does_not_promote(self):
        identity = project_identity(self.cwd)
        self.store.register_project(identity)
        first = make_candidate(
            "claude", identity.id, "s1", "keep paths owned", "owned paths",
            "Stage only task-owned paths.\n\nKeep the list exact.",
        )
        second = make_candidate(
            "claude", identity.id, "s2", "keep paths owned again", "owned paths",
            "Stage only task-owned paths.\n\nKeep the list exact!",
        )
        self.store.append_candidate(first)
        self.store.append_candidate(second)
        promote(
            self.store, first["id"], "owned-paths", "feedback",
            "Stage only task-owned paths",
            "Stage only task-owned paths.\n\nKeep the list exact.", "hassan",
        )
        promote(
            self.store, second["id"], "owned-paths-dup", "feedback",
            "Stage only task-owned paths",
            "Stage only task-owned paths.\n\nKeep the list exact!", "hassan",
        )
        created = consolidate(self.store)
        self.assertEqual(len(created), 1)
        self.assertIn("Near-duplicate", created[0]["body"])
        self.assertFalse((self.store.bank(identity.id) / "memories" / "project_merge.md").exists())

    def test_harvest_writes_correction_candidates_only(self):
        inbox = inbox_path(self.root)
        document = Inbox(
            header="# Memory review inbox\n\n",
            pending=[
                Candidate(
                    "2026-08-21 10:00", "proj", "correction",
                    "no, keep homes read-only", 2, "abcd1234", "/tmp/t.jsonl",
                ),
                Candidate(
                    "2026-08-21 10:01", "proj", "goal",
                    "build the adapter", 1, "eeeeeeee", "/tmp/t.jsonl",
                ),
            ],
            reviewed=[],
        )
        inbox.write_text(document.render(), encoding="utf-8")
        created = harvest(self.store, inbox, self.cwd)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["type"], "feedback")
        again = harvest(self.store, inbox, self.cwd)
        self.assertEqual(again, [])

    def test_harvest_keeps_the_inbox_project(self):
        other = self.root / "other"
        other.mkdir()
        inbox = inbox_path(self.root)
        document = Inbox(
            header="# Memory review inbox\n\n",
            pending=[
                Candidate(
                    "2026-08-21 10:00", "proj", "correction",
                    "no, bank under the inbox project", 1, "abcd1234", "/tmp/t.jsonl",
                ),
            ],
            reviewed=[],
        )
        inbox.write_text(document.render(), encoding="utf-8")
        created = harvest(self.store, inbox, other)
        self.assertEqual(created[0]["project_id"], project_identity(self.cwd).id)
        self.assertNotEqual(created[0]["project_id"], project_identity(other).id)

    def test_handoff_packet_names_finish_and_refuses_empty(self):
        path = write_packet(
            self.root / "HANDOFF.md",
            packet("ship setup without writing native homes", self.cwd, store=self.root / "missing"),
        )
        text = path.read_text(encoding="utf-8")
        self.assertIn("ship setup without writing native homes", text)
        self.assertIn("host spawn", text)
        from kingstack.handoff import HandoffError, packet as make
        with self.assertRaises(HandoffError):
            make("   ", self.cwd)
