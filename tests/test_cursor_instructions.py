import json
from pathlib import Path
from unittest import TestCase

from kingstack.ownership import load_ownership
from kingstack.render import render_bundle
from kingstack.skills import render_skill_files


ROOT = Path(__file__).parents[1]


class CursorInstructionsTest(TestCase):
    def test_cursor_uses_rules_not_home_agents_md(self):
        bundle = render_bundle("cursor", ROOT)
        self.assertNotIn("AGENTS.md", bundle)
        self.assertTrue(any(path.startswith("rules/kingstack/") for path in bundle))
        self.assertIn("rules/kingstack/10-correction-rule.mdc", bundle)
        self.assertIn("rules/kingstack/35-constraints.mdc", bundle)
        self.assertIn("rules/kingstack/adapter.mdc", bundle)
        identity = bundle["rules/kingstack/00-identity.mdc"].decode("utf-8")
        self.assertIn("alwaysApply: false", identity)
        self.assertIn("Hassan Ghandour", identity)
        correction = bundle["rules/kingstack/10-correction-rule.mdc"].decode("utf-8")
        self.assertIn("alwaysApply: true", correction)
        constraints = bundle["rules/kingstack/35-constraints.mdc"].decode("utf-8")
        self.assertIn("alwaysApply: true", constraints)
        routing = bundle["rules/kingstack/40-model-and-context.mdc"].decode("utf-8")
        self.assertIn("alwaysApply: true", routing)
        adapter = bundle["rules/kingstack/adapter.mdc"].decode("utf-8")
        self.assertIn("alwaysApply: true", adapter)
        self.assertIn("rules/kingstack", adapter)
        self.assertNotIn("Cursor Agent uses AGENTS.md", adapter)

        order = json.loads((ROOT / "core/instructions/order.json").read_text(encoding="utf-8"))
        for name in order:
            source = (ROOT / "core/instructions" / name).read_text(encoding="utf-8").lstrip("\n")
            if not source.endswith("\n"):
                source += "\n"
            text = bundle["rules/kingstack/{}.mdc".format(name[:-3])].decode("utf-8")
            _, marker, body = text.partition("\n---\n\n")
            self.assertTrue(marker, name)
            self.assertEqual(body, source)

        hooks = json.loads(bundle["hooks.json"].decode("utf-8"))
        self.assertEqual(hooks["version"], 1)
        self.assertIn("sessionStart", hooks["hooks"])
        self.assertNotIn("SessionStart", hooks["hooks"])
        self.assertEqual(
            hooks["hooks"]["sessionStart"][0]["command"],
            "python3 \"$HOME/.cursor/hooks/run.py\" sessionStart",
        )
        self.assertIn("hooks/run.py", bundle)
        self.assertIn("hooks/poteto-mode-context.md", bundle)
        self.assertIn(
            "Do not wait for Hassan to name a skill",
            bundle["hooks/poteto-mode-context.md"].decode("utf-8"),
        )
        skills = {path.split("/", 1)[0] for path in render_skill_files("cursor", ROOT)}
        self.assertEqual(len(skills), 54)
        self.assertIn("poteto-mode", skills)
        self.assertIn("king-mode", skills)
        poteto = bundle["skills/poteto-mode/SKILL.md"].decode("utf-8")
        king = bundle["skills/king-mode/SKILL.md"].decode("utf-8")
        tdd = bundle["skills/tdd/SKILL.md"].decode("utf-8")
        self.assertNotIn("disable-model-invocation", poteto)
        self.assertNotIn("disable-model-invocation", king)
        self.assertIn("disable-model-invocation: true", tdd)
        self.assertIn("Do not wait to be named", king)

    def test_cursor_ownership_forbids_cursor_private_paths(self):
        owned = load_ownership(ROOT, "cursor")
        self.assertIn("rules/kingstack", owned["fully_owned"])
        self.assertNotIn("AGENTS.md", owned["fully_owned"])
        for name in ("skills-cursor", "chats", "cli-config.json"):
            self.assertIn(name, owned["forbidden"])
