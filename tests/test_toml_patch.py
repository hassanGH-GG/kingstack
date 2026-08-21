from unittest import TestCase

from kingstack.toml_patch import TomlPatchError, owned_spans


class TomlPatchTest(TestCase):
    def test_preserves_unowned_lines_and_sets_owned_keys(self):
        original = (
            "model = \"gpt-5.6-sol\"\n"
            "# keep this comment\n"
            "[plugins]\n"
            "enabled = true\n"
        )
        patched, _ = owned_spans(
            original,
            {"agents.default_subagent_model": "gpt-5.6-terra", "features.memories": True},
        )
        self.assertIn('model = "gpt-5.6-sol"', patched)
        self.assertIn("# keep this comment", patched)
        self.assertIn("[agents]", patched)
        self.assertIn('default_subagent_model = "gpt-5.6-terra"', patched)
        self.assertIn("memories = true", patched)
        with self.assertRaises(TomlPatchError):
            owned_spans('model = "other"\n', {"model": "gpt-5.6-terra"})
