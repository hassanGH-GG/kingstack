import json
import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.cli import main
from kingstack.headroom import HeadroomError, check_pin, crush, live_ids, retrieve, stats


ROOT = Path(__file__).parents[1]


def fat_log():
    rows = []
    for index in range(400):
        rows.append(
            {
                "n": index,
                "level": "INFO",
                "msg": "ok " + ("payload " * 8),
            }
        )
    rows[67] = {"n": 67, "level": "FATAL", "msg": "disk full on /var/lib"}
    return json.dumps(rows, indent=2) + "\n"


class HeadroomTest(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Path(self.temporary.name) / "store"

    def test_pin_matches_sibling_checkout(self):
        report = check_pin(ROOT, ROOT.parent / "headroom")
        self.assertTrue(report["revision"].startswith("5e0ce24"))
        self.assertEqual(report["status"], "clean")

    def test_crush_keeps_fatal_and_retrieve_is_exact(self):
        text = fat_log()
        record = crush(text, self.store, ROOT, tool="logs")
        self.assertGreater(record["bytes"], 30000)
        self.assertGreater(record["saved"], 0)
        self.assertIn("FATAL", record["notice"])
        self.assertIn("disk full on /var/lib", record["notice"])
        self.assertEqual(retrieve(record["id"], self.store, ROOT), text)
        self.assertIn(record["id"], live_ids(self.store))
        summary = stats(self.store, ROOT)
        self.assertEqual(summary["archives"], 1)
        self.assertEqual(summary["saved"], record["saved"])
        blob = crush("x" * 30000, self.store, ROOT, tool="Read")
        self.assertGreater(blob["saved"], 5000)
        self.assertLess(blob["tokens_out"], 400)

    def test_store_refuses_native_home(self):
        with self.assertRaises(HeadroomError):
            crush("x" * 40000, Path.home() / ".cursor" / "headroom", ROOT)

    def test_cli_crush_and_retrieve(self):
        source = Path(self.temporary.name) / "log.json"
        source.write_text(fat_log(), encoding="utf-8")
        self.assertEqual(
            main(
                [
                    "headroom",
                    "crush",
                    "--file",
                    str(source),
                    "--store",
                    str(self.store),
                    "--tool",
                    "logs",
                ]
            ),
            0,
        )
        identity = next(self.store.glob("*.txt")).stem
        self.assertEqual(
            main(["headroom", "retrieve", identity, "--store", str(self.store)]),
            0,
        )
        self.assertEqual(main(["sync-upstream", "headroom", "--check"]), 0)
