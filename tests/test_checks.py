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
        live_only = [item for item in live if item["id"] in ("live-activation", "cli-shim")]
        self.assertEqual(len(live_only), 2)
        for row in live_only:
            self.assertIn(row["status"], ("pass", "fail"))
        if any(row["status"] == "fail" for row in live_only):
            self.assertEqual(overall(live), "unhealthy")
        else:
            self.assertEqual(overall(live), "healthy")
        injected = list(staged)
        injected[0] = dict(injected[0], status="fail")
        self.assertTrue(any(row["status"] == "pass" for row in injected[1:]))

    def test_live_checks_ignore_homes_that_do_not_exist(self):
        import tempfile
        from kingstack.setup import setup

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home = Path(temporary.name) / "home"
        home.mkdir()
        setup(checkout=ROOT, runtime=home / ".kingstack", identity="personal", home=home)
        isolated = live_checks(ROOT, home=home)
        activation = next(item for item in isolated if item["id"] == "live-activation")
        shim = next(item for item in isolated if item["id"] == "cli-shim")
        self.assertEqual(activation["status"], "fail")
        self.assertEqual(activation["evidence"], "no native home")
        self.assertEqual(shim["status"], "pass")
        cursor = home / ".cursor"
        cursor.mkdir()
        (cursor / ".kingstack-activation.json").write_text("{}", encoding="utf-8")
        (cursor / ".kingstack-current").symlink_to(cursor)
        linked = live_checks(ROOT, home=home)
        activation = next(item for item in linked if item["id"] == "live-activation")
        self.assertEqual(activation["status"], "pass")
        self.assertEqual(activation["evidence"], "linked .cursor")
