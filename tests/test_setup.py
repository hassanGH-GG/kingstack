import tempfile
from pathlib import Path
from unittest import TestCase

from kingstack.checkout import CheckoutError, discover_checkout, is_checkout
from kingstack.cli import main
from kingstack.profile import load_profile
from kingstack.setup import SetupError, setup
from kingstack.skills import default_upstream_root


ROOT = Path(__file__).parents[1]


class CheckoutTest(TestCase):
    def test_discovers_from_env_and_refuses_a_random_directory(self):
        self.assertTrue(is_checkout(ROOT))
        found = discover_checkout(env={"KINGSTACK_ROOT": str(ROOT)})
        self.assertEqual(found, ROOT.resolve())
        with self.assertRaises(CheckoutError):
            discover_checkout(cwd=Path("/tmp"), env={"KINGSTACK_ROOT": "/tmp"})


class SetupTest(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name) / "home"
        self.home.mkdir()
        self.runtime = self.home / ".kingstack"

    def test_setup_is_idempotent_and_refuses_native_homes(self):
        first = setup(
            checkout=ROOT,
            runtime=self.runtime,
            identity="personal",
            home=self.home,
        )
        second = setup(
            checkout=ROOT,
            runtime=self.runtime,
            identity="personal",
            home=self.home,
        )
        self.assertEqual(first["identity"], "personal")
        self.assertEqual(second["runtime"], str(self.runtime.resolve()))
        self.assertFalse(first["native_homes_written"])
        self.assertIn("king-mode overlay", first["not_got"])
        self.assertIn("live native-home link", first["not_got"])
        profile = load_profile(self.runtime)
        self.assertEqual(profile["identity"], "personal")
        self.assertTrue((self.runtime / "memory" / "inbox.jsonl").is_file())
        shim = self.home / ".local" / "bin" / "kingstack"
        target = (ROOT / "scripts" / "kingstack").resolve()
        self.assertTrue(shim.is_file())
        self.assertFalse(shim.is_symlink())
        self.assertIn(str(target), shim.read_text(encoding="utf-8"))
        self.assertFalse((self.home / ".claude").exists())
        with self.assertRaises(SetupError):
            setup(
                checkout=ROOT,
                runtime=self.home / ".claude",
                identity="personal",
                home=self.home,
            )

    def test_cli_setup_json_and_hassan_overlay(self):
        code = main(
            [
                "setup",
                "--root",
                str(ROOT),
                "--runtime",
                str(self.runtime),
                "--home",
                str(self.home),
                "--identity",
                "hassan",
                "--json",
            ]
        )
        self.assertIn(code, (0, 1))
        profile = load_profile(self.runtime)
        self.assertEqual(profile["identity"], "hassan")

    def test_upstream_defaults_to_the_checkout_sibling(self):
        self.assertEqual(default_upstream_root(ROOT, env={}), ROOT.parent / "plugins")
        self.assertEqual(
            default_upstream_root(ROOT, env={"KINGSTACK_UPSTREAM_ROOT": "/tmp/plugins"}),
            Path("/tmp/plugins"),
        )
