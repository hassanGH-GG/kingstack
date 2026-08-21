from pathlib import Path
from unittest import TestCase

from kingstack.checks import live_checks, overall, staged_checks


ROOT = Path(__file__).parents[1]


class ChecksTest(TestCase):
    def test_staged_is_healthy_and_live_stays_unhealthy(self):
        staged = staged_checks(ROOT)
        self.assertEqual(overall(staged), "healthy")
        self.assertTrue(all(row["status"] in ("pass", "fail") for row in staged))
        live = live_checks(ROOT)
        self.assertEqual(overall(live), "unhealthy")
        self.assertTrue(any(row["id"] == "live-activation" and row["status"] == "fail" for row in live))
        injected = list(staged)
        injected[0] = dict(injected[0], status="fail")
        self.assertTrue(any(row["status"] == "pass" for row in injected[1:]))
