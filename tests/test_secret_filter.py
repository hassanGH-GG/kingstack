from unittest import TestCase

from pathlib import Path

from kingstack.secret_filter import SecretFilterError, inspect, keep_public, reject_if_secret


ROOT = Path(__file__).parents[1]


class SecretFilterTest(TestCase):
    def test_rejects_tokens_and_allows_posthog_name(self):
        reject_if_secret("Use POSTHOG_KEY from the environment name only.")
        self.assertEqual(inspect("Use POSTHOG_KEY from the environment name only."), [])
        with self.assertRaises(SecretFilterError):
            reject_if_secret("token: ghp_abcdefghijklmnopqrstuvwxyz123456")
        with self.assertRaises(SecretFilterError):
            reject_if_secret("-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----")
        with self.assertRaises(SecretFilterError):
            reject_if_secret("https://user:supersecret@example.com/repo")
        hits = inspect("token: ghp_abcdefghijklmnopqrstuvwxyz123456")
        self.assertTrue(hits)
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz123456", str(hits))
        self.assertEqual(
            keep_public(
                ["ship the leftover", "token: ghp_abcdefghijklmnopqrstuvwxyz123456"]
            ),
            ["ship the leftover"],
        )

    def test_human_prompts_filters_at_the_read_boundary(self):
        text = (ROOT / "lib" / "kingstack" / "hooks" / "inbox.py").read_text(
            encoding="utf-8"
        )
        self.assertTrue("keep_public(" in text or "inspect(" in text)
