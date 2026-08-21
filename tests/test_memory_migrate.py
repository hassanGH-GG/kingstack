import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.memory_migrate import inventory_banks, migrate_claude
from kingstack.memory_store import MemoryStore


class MemoryMigrateTest(TestCase):
    def test_copy_only_preserves_source_and_hashes(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home = Path(temporary.name) / "claude"
        memory = home / "projects" / "demo" / "memory"
        memory.mkdir(parents=True)
        body = "---\nname: fact\ndescription: keep\n---\n\nkeep this\n"
        target = memory / "user_fact.md"
        target.write_text(body, encoding="utf-8")
        (memory / "MEMORY.md").write_text("# Memory Index\n\n- fact\n", encoding="utf-8")
        (memory / "orphan.md").write_text("orphan\n", encoding="utf-8")
        source_hash = target.read_bytes()
        source_mtime = target.stat().st_mtime_ns
        dry = inventory_banks(home)
        self.assertEqual(dry["count"], 1)
        self.assertIn("orphan.md", dry["banks"][0]["unindexed_files"])
        store = MemoryStore.open(Path(temporary.name) / "memory")
        migrate_claude(home, store, apply=True)
        self.assertEqual(target.read_bytes(), source_hash)
        self.assertEqual(target.stat().st_mtime_ns, source_mtime)
        self.assertTrue(target.exists())
