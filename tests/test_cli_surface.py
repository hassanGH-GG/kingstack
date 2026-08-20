import io
import pkgutil
import re
from contextlib import redirect_stdout
from pathlib import Path
from unittest import TestCase

import kingstack
from kingstack.cli import main


ROOT = Path(__file__).parents[1]


def cli_command_names():
    """Return the commands advertised by the public CLI help text."""
    output = io.StringIO()
    with redirect_stdout(output):
        with TestCase().assertRaises(SystemExit) as exit_call:
            main(["--help"])
    if exit_call.exception.code != 0:
        raise AssertionError("CLI help did not exit successfully")
    match = re.search(r"\{([^}]+)\}", output.getvalue())
    if match is None:
        return set()
    return set(match.group(1).split(","))


def production_module_names():
    return {module.name for module in pkgutil.iter_modules(kingstack.__path__)}


class CliSurfaceTest(TestCase):
    def test_no_recursive_backup_or_restore_surface(self):
        self.assertFalse((ROOT / "lib/kingstack/snapshot.py").exists())
        self.assertFalse((ROOT / "lib/kingstack/archive.py").exists())
        self.assertNotIn("snapshot", production_module_names())
        self.assertNotIn("archive", production_module_names())
        self.assertNotIn("snapshot", cli_command_names())
        self.assertNotIn("archive", cli_command_names())
        self.assertEqual(
            cli_command_names(), {"bootstrap", "check", "inventory", "render"}
        )
