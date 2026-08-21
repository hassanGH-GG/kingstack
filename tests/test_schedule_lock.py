import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.schedule_lock import ScheduleLockError, claim, complete


class ScheduleLockTest(TestCase):
    def test_second_claim_is_duplicate_prevented(self):
        root = Path(tempfile.mkdtemp())
        first = claim("com.hassan.kingstack-sweeps", "launchd", root=root)
        self.assertEqual(first["owner"], "launchd")
        with self.assertRaisesRegex(ScheduleLockError, "duplicate prevented"):
            claim("com.hassan.kingstack-sweeps", "codex", root=root)
        complete("com.hassan.kingstack-sweeps", 0, root=root)
