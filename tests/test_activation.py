from pathlib import Path
from unittest import TestCase

from kingstack.activation import ActivationError, apply_activation, plan_activation


ROOT = Path(__file__).parents[1]


class ActivationTest(TestCase):
    def test_plan_does_not_write_and_apply_is_forbidden(self):
        home = Path("/tmp/fake-claude-home")
        plan = plan_activation("claude", ROOT, home, "deadbeef")
        self.assertFalse(plan["writes"])
        self.assertTrue(any(item["release"] == "CLAUDE.md" for item in plan["owned"]))
        self.assertTrue(any(item["mode"] == "merge" for item in plan["mixed"]))
        self.assertFalse(home.exists())
        with self.assertRaises(ActivationError):
            apply_activation(plan)
