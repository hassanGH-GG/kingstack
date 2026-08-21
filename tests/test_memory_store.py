import os
import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.memory_store import MemoryStore, MemoryStoreError
from kingstack.project_id import ProjectIdentity


class MemoryStoreTest(TestCase):
    def test_store_layout_modes_and_repo_refusal(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "memory"
        store = MemoryStore.open(root, repo_root=Path(temporary.name) / "repo")
        self.assertEqual(oct(root.stat().st_mode & 0o777), "0o700")
        identity = ProjectIdentity("p_abc", "plugins", "/tmp/plugins", None)
        store.register_project(identity)
        bank = store.bank("p_abc")
        self.assertTrue((bank / "MEMORY.md").is_file())
        self.assertEqual(oct((root / "inbox.jsonl").stat().st_mode & 0o777), "0o600")
        inside = Path(temporary.name) / "repo" / "memory"
        inside.mkdir(parents=True)
        with self.assertRaises(MemoryStoreError):
            MemoryStore.open(inside, repo_root=Path(temporary.name) / "repo")
