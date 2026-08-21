from pathlib import Path
from unittest import TestCase

from kingstack.cli import main
from kingstack.effort import failed, scan_file, scan_spawns
from kingstack.hooks.dispatch import handle


class EffortScanTest(TestCase):
    def test_named_spawn_passes_and_inherit_fails(self):
        text = (
            "noise\n"
            "↳ spawn [builder] render the adapter · model=sonnet effort=medium\n"
            "↳ spawn [default] quick look · model=inherit effort=inherit ⚠ no model set\n"
        )
        rows = scan_spawns(text)
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["ok"])
        self.assertFalse(rows[1]["ok"])
        self.assertEqual(len(failed(rows)), 1)

    def test_hook_line_is_what_the_scanner_reads(self):
        runtime = Path("/tmp")
        named = handle(
            {
                "event": "SubagentStart",
                "agent": "claude",
                "session_id": "s1",
                "project": "/work",
                "payload": {
                    "role": "builder",
                    "model": "sonnet",
                    "effort": "medium",
                    "task": "render the adapter",
                },
            },
            runtime,
        )
        inherited = handle(
            {
                "event": "SubagentStart",
                "agent": "claude",
                "session_id": "s2",
                "project": "/work",
                "payload": {"task": "quick look"},
            },
            runtime,
        )
        rows = scan_spawns(named["systemMessage"] + "\n" + inherited["systemMessage"])
        self.assertTrue(rows[0]["ok"])
        self.assertFalse(rows[1]["ok"])

    def test_cli_exits_one_on_inherit(self):
        import tempfile

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "spawns.txt"
        path.write_text(
            "↳ spawn [builder] ok · model=haiku effort=low\n"
            "↳ spawn [default] bad · model=inherit effort=medium\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["effort", "--file", str(path)]), 1)
        good = Path(temporary.name) / "good.txt"
        good.write_text(
            "↳ spawn [builder] ok · model=haiku effort=low\n",
            encoding="utf-8",
        )
        self.assertEqual(main(["effort", "--file", str(good)]), 0)
        self.assertEqual(scan_file(good)[0]["model"], "haiku")
        empty = scan_spawns("no spawns here")
        self.assertEqual(empty, [])
        self.assertEqual(failed(empty), [])
