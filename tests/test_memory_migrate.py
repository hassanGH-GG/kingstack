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

    def test_dry_run_against_live_claude_applies_only_to_a_temp_store(self):
        live = Path.home() / ".claude"
        if not (live / "projects").is_dir():
            self.skipTest("no live Claude banks")
        before = inventory_banks(live)
        store = MemoryStore.open(Path(tempfile.mkdtemp()) / "memory")
        dry = migrate_claude(live, store, apply=False)
        self.assertEqual(dry["count"], before["count"])
        migrate_claude(live, store, apply=True)
        after = inventory_banks(live)
        self.assertEqual(after, before)
        self.assertNotEqual(store.root, Path.home() / ".kingstack" / "memory")

    def test_two_claude_slugs_do_not_share_a_parent_git_identity(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        first = root / "covers-engine"
        second = root / "plugins"
        first.mkdir()
        second.mkdir()
        claude = root / "claude" / "projects"
        for real in (first, second):
            slug = "-" + "-".join(real.parts[1:])
            memory = claude / slug / "memory"
            memory.mkdir(parents=True)
            (memory / "MEMORY.md").write_text("# {}\n".format(real.name), encoding="utf-8")
        # parent git repo that used to steal every identity
        subprocess = __import__("subprocess")
        subprocess.run(["git", "init"], cwd=claude, check=True, stdout=subprocess.DEVNULL)
        store = MemoryStore.open(root / "memory")
        migrate_claude(root / "claude", store, apply=True)
        self.assertEqual(len(list((store.root / "projects").iterdir())), 2)
