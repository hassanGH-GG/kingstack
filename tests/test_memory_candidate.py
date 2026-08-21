import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.memory_candidate import make_candidate
from kingstack.memory_store import MemoryStore


class MemoryCandidateTest(TestCase):
    def test_same_fact_different_provenance_and_idempotent_append(self):
        shared = dict(
            project_id="p_demo",
            title="Use explicit staged paths",
            description="Never sweep unrelated work into a shared checkout commit.",
            body="Stage only paths owned by the current task.",
        )
        claude = make_candidate(source_adapter="claude", session_id="claude-1", **shared)
        codex = make_candidate(source_adapter="codex", session_id="codex-1", **shared)
        example = make_candidate(source_adapter="example", session_id="ex-1", **shared)
        self.assertEqual(claude["content_hash"], codex["content_hash"])
        self.assertNotEqual(claude["id"], codex["id"])
        self.assertNotEqual(claude["id"], example["id"])
        again = make_candidate(source_adapter="claude", session_id="claude-1", **shared)
        self.assertEqual(claude["id"], again["id"])
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        store = MemoryStore.open(Path(temporary.name) / "memory")
        store.append_candidate(claude)
        store.append_candidate(again)
        rows = [line for line in (store.root / "inbox.jsonl").read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
