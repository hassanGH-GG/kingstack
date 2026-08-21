import json
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
        self.assertTrue((home / "rules/kingstack/00-identity.mdc").is_file())
        self.assertTrue((home / "hooks/ctx-status.py").is_file())
        self.assertTrue((home / "bin/kingstack-path").is_file())
        rollback_activation(applied)
        self.assertFalse((home / ".kingstack-current").exists())
        home.mkdir(parents=True, exist_ok=True)
        (home / "rules/kingstack").mkdir(parents=True, exist_ok=True)
        (home / "rules/kingstack/keep.mdc").write_text("keep-me\n", encoding="utf-8")
        plan = plan_activation("cursor", ROOT, home, release["id"], runtime=runtime)
        with self.assertRaises(ActivationError):
            apply_activation(plan, ROOT, fail_after="owned-rename")
        self.assertEqual((home / "rules/kingstack/keep.mdc").read_text(encoding="utf-8"), "keep-me\n")
        first = apply_activation(plan, ROOT)
        second = apply_activation(plan, ROOT)
        self.assertEqual(first["release"], second["release"])
        claude = build_release("claude", ROOT, runtime)
        native_plan = plan_activation(
            "claude", ROOT, Path.home() / ".claude", claude["id"], runtime=runtime
        )
        with self.assertRaises(ActivationError):
            apply_activation(native_plan, ROOT)

    def test_settings_unowned_keys_survive_inverse_rollback(self):
        runtime = Path(tempfile.mkdtemp())
        release = build_release("claude", ROOT, runtime)
        home = Path(tempfile.mkdtemp()) / "claude-home"
        home.mkdir()
        (home / "settings.json").write_text(
            json.dumps({"autoCompactWindow": 200000, "theme": "dark"}, indent=2) + "\n",
            encoding="utf-8",
        )
        plan = plan_activation("claude", ROOT, home, release["id"], runtime=runtime)
        with self.assertRaises(ActivationError):
            apply_activation(plan, ROOT, fail_after="mixed-publish")
        self.assertEqual(json.loads((home / "settings.json").read_text())["theme"], "dark")
        applied = apply_activation(plan, ROOT)
        live = json.loads((home / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("statusLine", live)
        live["keepAfter"] = True
        (home / "settings.json").write_text(json.dumps(live, indent=2) + "\n", encoding="utf-8")
        rollback_activation(applied)
        restored = json.loads((home / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(restored["theme"], "dark")
        self.assertTrue(restored["keepAfter"])
        self.assertNotIn("statusLine", restored)

    def test_occupied_sibling_and_current_failure_restore(self):
        runtime = Path(tempfile.mkdtemp())
        release = build_release("cursor", ROOT, runtime)
        home = Path(tempfile.mkdtemp()) / "cursor-home"
        home.mkdir()
        (home / "rules/kingstack").mkdir(parents=True)
        (home / "rules/kingstack/old.mdc").write_text("original\n", encoding="utf-8")
        plan = plan_activation("cursor", ROOT, home, release["id"], runtime=runtime)
        with self.assertRaises(ActivationError):
            apply_activation(plan, ROOT, fail_after="current")
        self.assertEqual((home / "rules/kingstack/old.mdc").read_text(encoding="utf-8"), "original\n")
        (home / "rules/kingstack.kingstack-occupied").write_text("nope\n", encoding="utf-8")
        # occupied check uses the live timestamped sibling name, not this file
        apply_activation(plan, ROOT)
        self.assertTrue((home / ".kingstack-current").is_symlink())
