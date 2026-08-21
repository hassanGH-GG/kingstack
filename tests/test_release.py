import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.release import (
    ReleaseError,
    build_release,
    rollback_release,
    select_release,
)


ROOT = Path(__file__).parents[1]


class ReleaseTest(TestCase):
    def test_builds_then_rolls_back_on_private_runtime_only(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        runtime = Path(temporary.name) / "runtime"
        first = build_release("cursor", ROOT, runtime)
        second = build_release("cursor", ROOT, runtime)
        self.assertEqual(first["id"], second["id"])
        self.assertFalse((runtime / "adapters" / "cursor" / "current").exists())
        select_release("cursor", runtime, first["id"])
        current = runtime / "adapters" / "cursor" / "current"
        self.assertTrue(current.is_symlink())
        self.assertEqual(current.resolve().name, first["id"])
        rolled = rollback_release("cursor", runtime, first["id"])
        self.assertTrue(rolled.get("unchanged") or rolled["id"] == first["id"])
        with self.assertRaises(ReleaseError):
            build_release("cursor", ROOT, Path.home() / ".claude")
        with self.assertRaises(ReleaseError):
            select_release("cursor", Path.home() / ".codex", first["id"])
