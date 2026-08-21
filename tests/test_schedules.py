from unittest import TestCase

from kingstack.schedules import ScheduleError, load_schedules, validate_schedules


class ScheduleTest(TestCase):
    def test_checked_in_schedules_are_single_owned_local_jobs(self):
        from pathlib import Path
        payload = load_schedules(Path(__file__).parents[1])
        ids = [item["id"] for item in payload["schedules"]]
        self.assertEqual(
            ids,
            [
                "com.hassan.claude-usage-snapshot",
                "com.hassan.king-mode-refresh",
                "com.hassan.kingstack-sweeps",
            ],
        )
        for item in payload["schedules"]:
            self.assertEqual(item["surface"], "local")
            self.assertEqual(item["owner"], "launchd")
            self.assertIsNone(item["model_tier"])

    def test_duplicate_enabled_and_surface_rules_fail(self):
        base = {
            "id": "job",
            "surface": "local",
            "owner": "launchd",
            "cadence": {"hour": 1},
            "command": "/bin/true",
            "timeout": None,
            "model_tier": None,
            "output": "/tmp/out",
            "idempotency_key": "job",
            "enabled": True,
        }
        with self.assertRaises(ScheduleError):
            validate_schedules({"schema_version": 1, "schedules": [base, dict(base, owner="codex")]})
        with self.assertRaises(ScheduleError):
            validate_schedules({"schema_version": 1, "schedules": [dict(base, model_tier="balanced")]})
        with self.assertRaises(ScheduleError):
            validate_schedules({"schema_version": 1, "schedules": [dict(base, surface="adapter")]})
