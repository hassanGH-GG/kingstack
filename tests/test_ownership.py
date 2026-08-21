import json
import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.ownership import OwnershipError, discover_adapters, native_homes


class OwnershipTest(TestCase):
    def test_fourth_adapter_json_is_enough_to_appear(self):
        root = Path(__file__).parents[1]
        self.assertEqual(discover_adapters(root), ["claude", "codex", "cursor"])
        self.assertEqual(set(native_homes(root)), {".claude", ".codex", ".cursor"})
        scratch = Path(tempfile.mkdtemp())
        for name in ("claude", "codex", "cursor"):
            dest = scratch / "adapters" / name
            dest.mkdir(parents=True)
            (dest / "adapter.json").write_text(
                json.dumps({"id": name, "native_home": "." + name}),
                encoding="utf-8",
            )
        extra = scratch / "adapters" / "example"
        extra.mkdir(parents=True)
        (extra / "adapter.json").write_text(
            json.dumps({"id": "example", "native_home": ".example"}),
            encoding="utf-8",
        )
        self.assertIn("example", discover_adapters(scratch))
        self.assertIn(".example", native_homes(scratch))
        empty = Path(tempfile.mkdtemp())
        with self.assertRaises(OwnershipError):
            native_homes(empty)
