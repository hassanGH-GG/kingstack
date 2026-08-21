import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.memory_candidate import make_candidate
from kingstack.memory_review import list_pending, promote, reject
from kingstack.memory_store import MemoryStore
from kingstack.project_id import ProjectIdentity


class MemoryReviewTest(TestCase):
    def test_promote_and_reject_are_human_gated(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        store = MemoryStore.open(Path(temporary.name) / "memory")
        identity = ProjectIdentity("p_demo", "demo", str(Path(temporary.name)), None)
        store.register_project(identity)
        candidate = make_candidate(
            "claude", "p_demo", "s1", "explicit staging", "stage owned paths",
            "Stage only task-owned paths.",
        )
        store.append_candidate(candidate)
        path = promote(
            store, candidate["id"], "explicit-staging", "feedback",
            "Stage only task-owned paths", "Stage only task-owned paths.", "hassan",
        )
        self.assertTrue(path.is_file())
        self.assertEqual(list_pending(store), [])
        other = make_candidate(
            "codex", "p_demo", "s2", "stale", "old", "old status",
        )
        store.append_candidate(other)
        reject(store, other["id"], "stale project status", "hassan")
        store.append_candidate(make_candidate("codex", "p_demo", "s9", "stale", "old", "old status"))
        self.assertEqual(list_pending(store), [])
