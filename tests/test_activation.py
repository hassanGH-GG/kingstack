import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.activation import ActivationError, apply_activation, plan_activation, rollback_activation
from kingstack.release import build_release


ROOT = Path(__file__).parents[1]


class ActivationTest(TestCase):
    def test_plan_requires_real_release_and_apply_refuses_native_home(self):
        runtime = Path(tempfile.mkdtemp())
        release = build_release("cursor", ROOT, runtime)
        home = Path(tempfile.mkdtemp()) / "cursor-home"
        with self.assertRaises(ActivationError):
            plan_activation("cursor", ROOT, home, "deadbeef", runtime=runtime)
        plan = plan_activation("cursor", ROOT, home, release["id"], runtime=runtime)
        self.assertFalse(plan["writes"])
        self.assertTrue(plan["owned"])
        applied = apply_activation(plan, ROOT)
        self.assertTrue((home / "AGENTS.md").is_file())
        self.assertTrue((home / ".kingstack-current").is_symlink())
        rollback_activation(applied)
        self.assertFalse((home / ".kingstack-current").exists())
        home.mkdir(parents=True, exist_ok=True)
        (home / "AGENTS.md").write_text("keep-me\n", encoding="utf-8")
        plan = plan_activation("cursor", ROOT, home, release["id"], runtime=runtime)
        with self.assertRaises(ActivationError):
            apply_activation(plan, ROOT, fail_after="owned-rename")
        self.assertEqual((home / "AGENTS.md").read_text(encoding="utf-8"), "keep-me\n")
        first = apply_activation(plan, ROOT)
        second = apply_activation(plan, ROOT)
        self.assertEqual(first["release"], second["release"])
        claude = build_release("claude", ROOT, runtime)
        native_plan = plan_activation(
            "claude", ROOT, Path.home() / ".claude", claude["id"], runtime=runtime
        )
        with self.assertRaises(ActivationError):
            apply_activation(native_plan, ROOT)
