import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.memory_context import session_index
from kingstack.memory_store import MemoryStore
from kingstack.project_id import project_identity


class MemoryContextTest(TestCase):
    def test_index_is_project_scoped_and_bounded(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        cwd = Path(temporary.name) / "proj"
        cwd.mkdir()
        store = MemoryStore.open(Path(temporary.name) / "memory")
        identity = project_identity(cwd)
        store.register_project(identity)
        (store.bank(identity.id) / "MEMORY.md").write_text(
            "# Memory Index\n\n- keep this project fact\n",
            encoding="utf-8",
        )
        other = store.register_project(
            type(identity)("p_other", "other", str(cwd / "other"), None)
        )
        (store.bank("p_other") / "MEMORY.md").write_text(
            "# Memory Index\n\n- secret other project\n",
            encoding="utf-8",
        )
        text = session_index(store, cwd, max_bytes=400)
        self.assertIn(identity.id, text)
        self.assertIn("not native adapter memory", text)
        self.assertNotIn("secret other project", text)
        self.assertLessEqual(len(text.encode("utf-8")), 280)
