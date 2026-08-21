from unittest import TestCase

from kingstack.json_patch import inverse_json, merge_json


class JsonPatchTest(TestCase):
    def test_preserves_unowned_keys_and_inverts(self):
        original = '{\n  "keep": true,\n  "nested": {"x": 1}\n}\n'
        patched, snapshot = merge_json(original, {"owned": "kingstack"})
        self.assertIn('"keep": true', patched)
        self.assertIn('"owned": "kingstack"', patched)
        restored = inverse_json(patched, snapshot)
        self.assertNotIn("owned", restored)
        self.assertIn('"keep": true', restored)
        overwritten, old = merge_json('{"owned": "other", "keep": true}', {"owned": "kingstack"})
        self.assertIn('"owned": "kingstack"', overwritten)
        self.assertEqual(old["owned"], "other")
        self.assertIn('"owned": "other"', inverse_json(overwritten, old))
        plugins, _ = merge_json(
            '{"enabledPlugins": {"cloudflare@cloudflare": true, "superpowers@claude-plugins-official": true}}',
            {"enabledPlugins.superpowers@claude-plugins-official": False},
        )
        self.assertIn('"cloudflare@cloudflare": true', plugins)
        self.assertIn('"superpowers@claude-plugins-official": false', plugins)
