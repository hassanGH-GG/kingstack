from unittest import TestCase

from kingstack.secret_filter import SecretFilterError, inspect, reject_if_secret


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
