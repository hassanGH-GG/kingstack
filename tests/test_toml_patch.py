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
        patched_list, _ = owned_spans("", {"tui.status_line": ["model", "tokens"]})
        self.assertIn("status_line = [\"model\", \"tokens\"]", patched_list)

    def test_missing_owned_keys_reuse_one_table_header(self):
        original = (
            "[features]\n"
            "js_repl = false\n"
            "\n"
            "[tui.model_availability_nux]\n"
            '"gpt-5.6-sol" = 3\n'
        )
        owned = {
            "agents.default_subagent_model": "gpt-5.6-terra",
            "agents.default_subagent_reasoning_effort": "medium",
            "features.memories": True,
            "memories.generate_memories": True,
            "memories.use_memories": True,
            "tui.status_line": ["model", "tokens"],
        }
        patched, snapshot = owned_spans(original, owned)
        headers = [line.strip() for line in patched.splitlines() if line.startswith("[")]
        self.assertEqual(headers.count("[agents]"), 1)
        self.assertEqual(headers.count("[features]"), 1)
        self.assertEqual(headers.count("[memories]"), 1)
        self.assertEqual(headers.count("[tui]"), 1)
        self.assertLess(patched.index("[tui]"), patched.index("[tui.model_availability_nux]"))
        self.assertIn("js_repl = false", patched)
        self.assertIn("memories = true", patched)
        self.assertEqual(snapshot["features.memories"], None)
        self.assertEqual(snapshot["agents.default_subagent_model"], None)
