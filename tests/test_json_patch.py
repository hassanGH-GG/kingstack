from unittest import TestCase

from kingstack.json_patch import JsonPatchError, inverse_json, merge_json


class JsonPatchTest(TestCase):
    def test_preserves_unowned_keys_and_inverts(self):
        original = '{\n  "keep": true,\n  "nested": {"x": 1}\n}\n'
        patched, snapshot = merge_json(original, {"owned": "kingstack"})
        self.assertIn('"keep": true', patched)
        self.assertIn('"owned": "kingstack"', patched)
        restored = inverse_json(patched, snapshot)
        self.assertNotIn("owned", restored)
        self.assertIn('"keep": true', restored)
        with self.assertRaises(JsonPatchError):
            merge_json('{"owned": "other"}', {"owned": "kingstack"})
