import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import MappingProxyType
from unittest import TestCase
from unittest.mock import patch

import kingstack.skills as skill_module

from kingstack.cli import main
from kingstack.render import render_bundle
from kingstack.skills import (
    SkillCatalogError,
    bundle_manifest,
    check_clobber_manifest,
    check_upstream,
    load_catalog,
    render_skill_files,
    semantic_parity_errors,
)


ROOT = Path(__file__).parents[1]
PLUGINS = ROOT.parent / "plugins"
BASELINE_65_NAMES = frozenset(
    {
        "agents-sdk",
        "architect",
        "arena",
        "automate-me",
        "blast-radius",
        "bro",
        "cli-for-agents",
        "cloudflare",
        "cloudflare-email-service",
        "cloudflare-one",
        "cloudflare-one-migrations",
        "control-cli",
        "control-ui",
        "create-verification-skill",
        "deslop",
        "durable-objects",
        "figure-it-out",
        "how",
        "interrogate",
        "king-mode",
        "maintain-verification-skill",
        "make-pr-easy-to-review",
        "memory-review",
        "no-comments",
        "poteto-mode",
        "principle-boundary-discipline",
        "principle-build-the-lever",
        "principle-encode-lessons-in-structure",
        "principle-exhaust-the-design-space",
        "principle-experience-first",
        "principle-fix-root-causes",
        "principle-foundational-thinking",
        "principle-guard-the-context-window",
        "principle-laziness-protocol",
        "principle-make-operations-idempotent",
        "principle-migrate-callers-then-delete-legacy-apis",
        "principle-minimize-reader-load",
        "principle-model-the-domain",
        "principle-never-block-on-the-human",
        "principle-outcome-oriented-execution",
        "principle-prove-it-works",
        "principle-redesign-from-first-principles",
        "principle-separate-before-serializing-shared-state",
        "principle-sequence-verifiable-units",
        "principle-subtract-before-you-add",
        "principle-type-system-discipline",
        "recall",
        "reflect",
        "sandbox-sdk",
        "service-migration-handover",
        "show-me-your-work",
        "swarm",
        "tdd",
        "teach",
        "technical-writing",
        "thermo-nuclear-code-quality-review",
        "thermo-nuclear-review",
        "turnstile-spin",
        "typescript-best-practices",
        "unslop",
        "verify-this",
        "web-perf",
        "why",
        "workers-best-practices",
        "wrangler",
    }
)


class SkillCatalogTest(TestCase):
    def payload(self):
        return json.loads(
            (ROOT / "core/skills/catalog.json").read_text(encoding="utf-8")
        )

    def temporary_catalog(self, payload=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(os.path.realpath(temporary.name))
        catalog_dir = root / "core/skills"
        catalog_dir.mkdir(parents=True)
        if (ROOT / "core/skills/authored").exists():
            shutil.copytree(
                ROOT / "core/skills/authored", catalog_dir / "authored"
            )
        (catalog_dir / "catalog.json").write_text(
            json.dumps(payload or self.payload()), encoding="utf-8"
        )
        shutil.copytree(ROOT / "core/skills/transforms", catalog_dir / "transforms")
        shutil.copytree(ROOT / "adapters", root / "adapters")
        shutil.copytree(ROOT / "core/capabilities", root / "core/capabilities")
        return root

    def full_generated_install(self, adapter="claude"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        installed = Path(os.path.realpath(temporary.name))
        files = render_skill_files(adapter, ROOT, upstream_root=PLUGINS)
        catalog = load_catalog(ROOT, upstream_root=PLUGINS)
        generated = {
            path: content
            for path, content in files.items()
            if catalog.owner(path.split("/", 1)[0]) in ("pstack", "adopted")
        }
        for path, content in generated.items():
            destination = installed / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        manifest = "".join(
            "{}  {}\n".format(hashlib.sha256(content).hexdigest(), path)
            for path, content in sorted(generated.items())
        ).encode()
        return installed, generated, manifest

    def test_claude_catalog_exactly_matches_frozen_65_name_baseline(self):
        """Dropping, adding, or renaming any baseline Claude skill must fail."""
        catalog = load_catalog(ROOT, upstream_root=PLUGINS)

        self.assertEqual(set(catalog.available_names("claude")), BASELINE_65_NAMES)
        self.assertEqual(len(catalog.available_names("claude")), 65)

    def test_catalog_preserves_frozen_pstack_revision_and_ownership(self):
        """Revision drift or ownership reassignment must fail visibly."""
        catalog = load_catalog(ROOT, upstream_root=PLUGINS)

        self.assertEqual(catalog.upstream_revision("pstack"), "63d938c")
        self.assertEqual(catalog.owner("king-mode"), "kingstack")
        self.assertEqual(catalog.owner("cloudflare"), "plugin-manager")

    def test_catalog_is_exact_validated_and_immutable(self):
        """A malformed entry or mutable loaded contract must never pass as valid."""
        catalog = load_catalog(ROOT, upstream_root=PLUGINS)

        self.assertEqual(
            {owner: sum(entry.owner == owner for entry in catalog.entries) for owner in (
                "kingstack", "pstack", "adopted", "plugin-manager"
            )},
            {"kingstack": 2, "pstack": 43, "adopted": 8, "plugin-manager": 12},
        )
        self.assertIsInstance(catalog.upstreams, MappingProxyType)
        self.assertEqual(catalog.owner("memory-review"), "kingstack")
        with self.assertRaises(TypeError):
            catalog.upstreams["pstack"] = {}

    def test_unknown_keys_owners_targets_and_owner_source_contradictions_fail(self):
        """Catalog schema drift or mixed ownership must fail before rendering."""
        cases = []
        unknown_top = self.payload()
        unknown_top["extra"] = True
        cases.append((unknown_top, "unknown catalog keys"))
        unknown_entry = self.payload()
        unknown_entry["entries"][0]["extra"] = True
        cases.append((unknown_entry, "unknown entry keys"))
        unknown_owner = self.payload()
        unknown_owner["entries"][0]["owner"] = "claude"
        cases.append((unknown_owner, "unknown owner"))
        unknown_target = self.payload()
        unknown_target["entries"][0]["targets"] = ["claude", "gemini"]
        cases.append((unknown_target, "unknown target"))
        contradiction = self.payload()
        next(entry for entry in contradiction["entries"] if entry["owner"] == "pstack")[
            "owner"
        ] = "kingstack"
        cases.append((contradiction, "owner/source contradiction"))

        for payload, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(SkillCatalogError, message):
                    load_catalog(self.temporary_catalog(payload), upstream_root=PLUGINS)

    def test_names_sources_and_targets_reject_portable_aliases(self):
        """Unicode/casefold aliases and unsafe or duplicate paths must not collide."""
        cases = []
        duplicate = self.payload()
        duplicate["entries"][1]["name"] = duplicate["entries"][0]["name"]
        cases.append((duplicate, "duplicate skill name"))
        casefold = self.payload()
        casefold["entries"][1]["name"] = casefold["entries"][0]["name"].upper()
        cases.append((casefold, "skill name"))
        unicode_name = self.payload()
        unicode_name["entries"][0]["name"] = "e\u0301"
        cases.append((unicode_name, "skill name"))
        source_alias = self.payload()
        source_alias["entries"][1]["source"] = source_alias["entries"][0]["source"].upper()
        cases.append((source_alias, "source path"))
        unsafe = self.payload()
        unsafe["entries"][0]["source"] = "../escape"
        cases.append((unsafe, "source path"))
        duplicate_target = self.payload()
        duplicate_target["entries"][0]["targets"] = ["claude", "CLAUDE"]
        cases.append((duplicate_target, "target"))

        for payload, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(SkillCatalogError, message):
                    load_catalog(self.temporary_catalog(payload), upstream_root=PLUGINS)

    def test_missing_sources_frontmatter_symlinks_and_dependency_graph_fail(self):
        """Missing/unsafe sources and an invalid dependency graph must fail closed."""
        missing = self.payload()
        next(entry for entry in missing["entries"] if entry["name"] == "king-mode")[
            "source"
        ] = "core/skills/authored/missing"
        with self.assertRaisesRegex(SkillCatalogError, "missing source"):
            load_catalog(self.temporary_catalog(missing), upstream_root=PLUGINS)

        invalid_root = self.temporary_catalog()
        (invalid_root / "core/skills/authored/king-mode/SKILL.md").write_text(
            "# no frontmatter\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(SkillCatalogError, "frontmatter"):
            load_catalog(invalid_root, upstream_root=PLUGINS)

        symlink_root = self.temporary_catalog()
        source = symlink_root / "core/skills/authored/king-mode/SKILL.md"
        source.unlink()
        source.symlink_to(ROOT / "skills/king-mode/SKILL.md")
        with self.assertRaisesRegex(SkillCatalogError, "symbolic link"):
            load_catalog(symlink_root, upstream_root=PLUGINS)

        for mutation, message in ((["missing"], "missing dependency"), (["memory-review"], "dependency cycle")):
            payload = self.payload()
            king = next(entry for entry in payload["entries"] if entry["name"] == "king-mode")
            memory = next(entry for entry in payload["entries"] if entry["name"] == "memory-review")
            if message == "missing dependency":
                king["dependencies"] = mutation
            else:
                king["dependencies"] = ["memory-review"]
                king["targets"] = list(dict.fromkeys(list(king["targets"]) + list(memory["targets"])))
                memory["dependencies"] = ["king-mode"]
            with self.subTest(message=message):
                with self.assertRaisesRegex(SkillCatalogError, message):
                    load_catalog(self.temporary_catalog(payload), upstream_root=PLUGINS)

    def test_catalog_rejects_symlinked_ancestors_and_source_identity_swaps(self):
        """Every source component must stay descriptor-confined for the whole read."""
        real_root = self.temporary_catalog()
        alias = real_root.parent / (real_root.name + "-alias")
        alias.symlink_to(real_root, target_is_directory=True)
        self.addCleanup(alias.unlink)
        with self.assertRaisesRegex(SkillCatalogError, "symbolic link|ancestor"):
            load_catalog(alias, upstream_root=PLUGINS)

        swap_root = self.temporary_catalog()
        source = swap_root / "core/skills/authored/king-mode"
        replacement = swap_root / "replacement"
        shutil.copytree(source, replacement)
        original_read_fd = skill_module._read_fd
        swapped = {"done": False}

        def swapping_read(descriptor, label):
            content = original_read_fd(descriptor, label)
            if b"name: king-mode" in content and not swapped["done"]:
                moved = source.with_name("king-mode-held")
                source.rename(moved)
                replacement.rename(source)
                swapped["done"] = True
            return content

        with patch("kingstack.skills._read_fd", side_effect=swapping_read):
            with self.assertRaisesRegex(SkillCatalogError, "changed|identity"):
                load_catalog(swap_root, upstream_root=PLUGINS)
        self.assertTrue(swapped["done"])

    def test_catalog_closes_every_acquired_root_descriptor_on_all_failures(self):
        """Each successful root acquisition is owned immediately, even on early exits."""
        original_open = skill_module._open_absolute_dir

        def exercise(root, upstream, fail_call=None):
            acquired = []
            calls = {"count": 0}

            def tracked_open(path, label):
                calls["count"] += 1
                if calls["count"] == fail_call:
                    raise SkillCatalogError("injected root-open failure")
                descriptor = original_open(path, label)
                acquired.append(descriptor)
                return descriptor

            with patch("kingstack.skills._open_absolute_dir", side_effect=tracked_open):
                with self.assertRaises(SkillCatalogError):
                    load_catalog(root, upstream_root=upstream)
            self.assertTrue(acquired)
            leaked = []
            for descriptor in acquired:
                try:
                    os.fstat(descriptor)
                except OSError:
                    continue
                leaked.append(descriptor)
                os.close(descriptor)
            self.assertEqual(leaked, [])

        exercise(ROOT, ROOT / "missing-upstream", fail_call=2)
        invalid = self.payload()
        invalid["extra"] = True
        exercise(self.temporary_catalog(invalid), PLUGINS)
        exercise(ROOT, PLUGINS, fail_call=4)

    def test_frontmatter_parser_accepts_baseline_and_rejects_malformed_subset(self):
        """The dependency-free parser accepts our subset and rejects ambiguous YAML."""
        load_catalog(ROOT, upstream_root=PLUGINS)
        mutations = {
            "flow value": "name: king-mode\ndescription: [\n",
            "duplicate key": "name: king-mode\nname: other\ndescription: valid\n",
            "control character": "name: king-mode\ndescription: bad\x01value\n",
            "ambiguous key": "name : king-mode\ndescription: valid\n",
            "unterminated quote": 'name: king-mode\ndescription: "broken\n',
        }
        for label, field in mutations.items():
            test_root = self.temporary_catalog()
            skill = test_root / "core/skills/authored/king-mode/SKILL.md"
            body = skill.read_text(encoding="utf-8")
            end = body.index("\n---\n", 4)
            skill.write_text("---\n" + field + body[end:], encoding="utf-8")
            with self.subTest(label=label):
                with self.assertRaisesRegex(SkillCatalogError, "frontmatter"):
                    load_catalog(test_root, upstream_root=PLUGINS)

    def test_frontmatter_names_and_descriptions_match_the_observed_baseline_subset(self):
        """Names are exact identities and descriptions are nonempty strings only."""
        invalid_descriptions = ("", "# comment", "null", "true", "false", "{}", "[]", "''")
        for value in invalid_descriptions:
            test_root = self.temporary_catalog()
            skill = test_root / "core/skills/authored/king-mode/SKILL.md"
            body = skill.read_text(encoding="utf-8")
            end = body.index("\n---\n", 4)
            skill.write_text(
                "---\nname: king-mode\ndescription: {}".format(value) + body[end:],
                encoding="utf-8",
            )
            with self.subTest(description=value):
                with self.assertRaisesRegex(SkillCatalogError, "frontmatter|description"):
                    load_catalog(test_root, upstream_root=PLUGINS)

        alias_root = self.temporary_catalog()
        skill = alias_root / "core/skills/authored/king-mode/SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8").replace("name: king-mode", "name: KING MODE", 1), encoding="utf-8")
        with self.assertRaisesRegex(SkillCatalogError, "frontmatter name"):
            load_catalog(alias_root, upstream_root=PLUGINS)

    def test_typed_transforms_reject_destructive_rules_and_parity_is_independent(self):
        """Kinds constrain edits and parity catches semantic edits independently."""
        test_root = self.temporary_catalog()
        transform_path = test_root / "core/skills/transforms/claude.json"
        document = json.loads(transform_path.read_text(encoding="utf-8"))
        document["transforms"]["cursor-host"]["replacements"].append(
            {"kind": "host", "pattern": ".*", "replacement": ""}
        )
        transform_path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(SkillCatalogError, "transform|destructive|exact|replacement"):
            load_catalog(test_root, upstream_root=PLUGINS)

        semantic_root = self.temporary_catalog()
        transform_path = semantic_root / "core/skills/transforms/claude.json"
        document = json.loads(transform_path.read_text(encoding="utf-8"))
        document["transforms"]["authored-host"]["replacements"].append(
            {"kind": "host", "source": "King Mode", "target": "Alien Mode"}
        )
        transform_path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(SkillCatalogError, "host transform"):
            load_catalog(semantic_root, upstream_root=PLUGINS)

        original_transform = skill_module._transform_content
        def corrupting_transform(content, path, rule, label):
            rendered = original_transform(content, path, rule, label)
            return rendered.replace(b"# King mode", b"# Alien mode")
        with patch("kingstack.skills._transform_content", side_effect=corrupting_transform):
            errors = semantic_parity_errors("claude", ROOT, upstream_root=PLUGINS)
        self.assertTrue(errors, "semantic parity accepted an out-of-engine heading edit")

    def test_transform_kinds_cannot_smuggle_arbitrary_instruction_rewrites(self):
        """Typed declarations accept tokens, not sentences or whole paragraphs."""
        bad_rules = (
            {"kind": "path", "source": "Runs inside poteto-mode, which supplies the playbooks and principles.", "target": "destroyed"},
            {"kind": "model", "source": "whole model paragraph", "target": "gpt-5.6-sol"},
            {"kind": "tool", "source": "Ask the user a destructive question", "target": "request_user_input"},
        )
        for rule in bad_rules:
            test_root = self.temporary_catalog()
            transform_path = test_root / "core/skills/transforms/claude.json"
            document = json.loads(transform_path.read_text(encoding="utf-8"))
            document["transforms"]["authored-host"]["replacements"].append(rule)
            transform_path.write_text(json.dumps(document), encoding="utf-8")
            with self.subTest(kind=rule["kind"]):
                with self.assertRaisesRegex(SkillCatalogError, "transform|token|path|model|tool"):
                    load_catalog(test_root, upstream_root=PLUGINS)

    def test_clobber_manifest_is_exact_and_descriptor_confined(self):
        """Only the exact generated set and exact installed tree may be adopted."""
        installed, generated, manifest = self.full_generated_install()
        check_clobber_manifest("claude", ROOT, installed, manifest, upstream_root=PLUGINS)
        cases = {
            "empty": b"",
            "missing": b"\n".join(manifest.splitlines()[1:]) + b"\n",
            "extra": manifest + (b"0" * 64) + b"  surprise/SKILL.md\n",
        }
        for label, value in cases.items():
            with self.subTest(label=label):
                with self.assertRaisesRegex(SkillCatalogError, "exact|missing|extra|generated"):
                    check_clobber_manifest("claude", ROOT, installed, value, upstream_root=PLUGINS)

        victim = sorted(generated)[0]
        (installed / victim).unlink()
        with self.assertRaisesRegex(SkillCatalogError, "missing"):
            check_clobber_manifest("claude", ROOT, installed, manifest, upstream_root=PLUGINS)
        (installed / victim).write_bytes(generated[victim])
        extra = installed / victim.split("/", 1)[0] / "unexpected.txt"
        extra.write_text("unexpected", encoding="utf-8")
        with self.assertRaisesRegex(SkillCatalogError, "extra|unexpected"):
            check_clobber_manifest("claude", ROOT, installed, manifest, upstream_root=PLUGINS)

    def test_codex_manifest_omits_and_explains_foreign_host_skills(self):
        """Codex must not claim skills whose workflows use unsupported host primitives."""
        direct = {
            "arena", "automate-me", "how", "interrogate", "no-comments",
            "poteto-mode", "recall", "reflect", "show-me-your-work", "swarm", "why",
        }
        unsupported = direct | {
            "architect", "blast-radius", "figure-it-out", "king-mode",
            "principle-prove-it-works", "service-migration-handover", "teach",
        }
        manifest = bundle_manifest("codex", ROOT, upstream_root=PLUGINS)
        records = {record["name"]: record for record in manifest["skills"]}
        self.assertEqual(
            {name for name, record in records.items() if record["status"] == "unsupported"},
            unsupported,
        )
        for name in direct:
            self.assertTrue(records[name].get("evidence"), name)
        files = render_skill_files("codex", ROOT, upstream_root=PLUGINS)
        self.assertFalse(any(path.split("/", 1)[0] in unsupported for path in files))
        joined = b"\n".join(files.values())
        for token in (b"subagent_type", b"run_in_background", b"AskQuestion", b"/loop", b"agent-transcripts"):
            self.assertNotIn(token, joined)

    def test_codex_unsupported_status_is_dependency_closed(self):
        """Every workflow that requires an unsupported skill is itself unsupported."""
        expected = {
            "arena", "architect", "automate-me", "blast-radius", "figure-it-out",
            "how", "interrogate", "king-mode", "no-comments", "poteto-mode",
            "principle-prove-it-works", "recall", "reflect", "service-migration-handover",
            "show-me-your-work", "swarm", "teach", "why",
        }
        manifest = bundle_manifest("codex", ROOT, upstream_root=PLUGINS)
        actual = {item["name"] for item in manifest["skills"] if item["status"] == "unsupported"}
        self.assertEqual(actual, expected)
        records = {item["name"]: item for item in manifest["skills"]}
        for name in expected - {"service-migration-handover"}:
            self.assertTrue(records[name].get("evidence"), name)

    def test_adapter_discovery_rejects_symlinked_and_swapped_declarations(self):
        """Adapter discovery remains confined to the held repository descriptor."""
        symlink_root = self.temporary_catalog()
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside)
        shutil.copytree(symlink_root / "adapters/codex", outside / "example")
        declaration_path = outside / "example/adapter.json"
        declaration = json.loads(declaration_path.read_text(encoding="utf-8"))
        declaration["id"] = "example"
        declaration["render_module"] = "example.external"
        declaration["capability_matrix"]["adapter_id"] = "example"
        declaration_path.write_text(json.dumps(declaration), encoding="utf-8")
        (symlink_root / "adapters/example").symlink_to(outside / "example", target_is_directory=True)
        shutil.copy(symlink_root / "core/skills/transforms/claude.json", symlink_root / "core/skills/transforms/example.json")
        transform_path = symlink_root / "core/skills/transforms/example.json"
        transform = json.loads(transform_path.read_text(encoding="utf-8"))
        transform["adapter"] = "example"
        transform_path.write_text(json.dumps(transform), encoding="utf-8")
        with self.assertRaisesRegex(SkillCatalogError, "adapter|symbolic link|unsafe"):
            load_catalog(symlink_root, upstream_root=PLUGINS)

        swap_root = self.temporary_catalog()
        source = swap_root / "adapters/codex"
        replacement = swap_root / "adapter-replacement"
        shutil.copytree(source, replacement)
        original_read = skill_module._read_fd
        swapped = {"done": False}

        def swapping_read(descriptor, label):
            content = original_read(descriptor, label)
            if label == "adapter 'codex'" and not swapped["done"]:
                source.rename(source.with_name("codex-held"))
                replacement.rename(source)
                swapped["done"] = True
            return content

        with patch("kingstack.skills._read_fd", side_effect=swapping_read):
            with self.assertRaisesRegex(SkillCatalogError, "adapter|changed|identity"):
                load_catalog(swap_root, upstream_root=PLUGINS)
        self.assertTrue(swapped["done"])

    def test_adapter_targets_are_declaration_driven_for_a_synthetic_third_adapter(self):
        """A valid declared adapter participates without first-party core imports."""
        test_root = self.temporary_catalog()
        adapter = json.loads((test_root / "adapters/codex/adapter.json").read_text())
        adapter.update({"id": "example", "render_module": "example.external"})
        adapter["capability_matrix"]["adapter_id"] = "example"
        example_dir = test_root / "adapters/example"
        example_dir.mkdir()
        (example_dir / "adapter.json").write_text(json.dumps(adapter), encoding="utf-8")
        shutil.copy(test_root / "adapters/codex/models.json", example_dir / "models.json")
        owned = json.loads((test_root / "adapters/codex/owned-paths.json").read_text())
        owned["adapter"] = "example"
        (example_dir / "owned-paths.json").write_text(json.dumps(owned), encoding="utf-8")
        shutil.copy(
            test_root / "core/skills/transforms/claude.json",
            test_root / "core/skills/transforms/example.json",
        )
        transform = json.loads((test_root / "core/skills/transforms/example.json").read_text())
        transform["adapter"] = "example"
        (test_root / "core/skills/transforms/example.json").write_text(json.dumps(transform), encoding="utf-8")
        payload = self.payload()
        entry = next(item for item in payload["entries"] if item["name"] == "memory-review")
        entry["targets"].append("example")
        (test_root / "core/skills/catalog.json").write_text(json.dumps(payload), encoding="utf-8")

        manifest = bundle_manifest("example", test_root, upstream_root=PLUGINS)
        self.assertEqual(manifest["adapter"], "example")
        self.assertIn("memory-review/SKILL.md", render_skill_files("example", test_root, upstream_root=PLUGINS))

    def test_adapter_ownership_never_claims_plugin_or_unsupported_skill_paths(self):
        """Adapter ownership enumerates generated paths instead of broad mixed trees."""
        for adapter in ("claude", "codex"):
            from kingstack.ownership import load_ownership, render_paths
            owned = set(render_paths(load_ownership(ROOT, adapter)))
            self.assertNotIn("skills", owned)
            manifest = bundle_manifest(adapter, ROOT, upstream_root=PLUGINS)
            records = {record["name"]: record for record in manifest["skills"]}
            for name, record in records.items():
                path = "skills/{}".format(name)
                if record["status"] == "bundled":
                    self.assertIn(path, owned)
                else:
                    self.assertNotIn(path, owned)

    def test_bundles_are_pure_immutable_and_account_for_plugins_explicitly(self):
        """Plugin-managed skills must be accounted for but never copied."""
        claude = bundle_manifest("claude", ROOT, upstream_root=PLUGINS)
        codex = bundle_manifest("codex", ROOT, upstream_root=PLUGINS)
        files = render_skill_files("claude", ROOT, upstream_root=PLUGINS)

        self.assertIsInstance(files, MappingProxyType)
        self.assertEqual(len({path.split("/", 1)[0] for path in files}), 53)
        self.assertFalse(any(path.startswith("cloudflare/") for path in files))
        self.assertEqual(len(claude["skills"]), 65)
        self.assertEqual(
            sum(record["status"] == "plugin-managed" for record in claude["skills"]),
            12,
        )
        service = next(record for record in codex["skills"] if record["name"] == "service-migration-handover")
        self.assertEqual(service["status"], "unsupported")
        cursor = bundle_manifest("cursor", ROOT, upstream_root=PLUGINS)
        self.assertEqual(sum(record["status"] == "bundled" for record in cursor["skills"]), 53)
        self.assertEqual(sum(record["status"] == "unsupported" for record in cursor["skills"]), 12)
        with self.assertRaises(TypeError):
            files["new/SKILL.md"] = b"bad"

    def test_transforms_remove_foreign_hosts_and_preserve_semantics(self):
        """A host token leak or workflow-meaning change in any portable skill must fail."""
        for adapter, forbidden in (
            ("claude", (b".cursor", b"generalPurpose")),
            ("codex", (b".cursor", b".claude", b"Claude Code", b"CLAUDE.md")),
            ("cursor", (b".claude", b"CLAUDE.md", b"Claude Code")),
        ):
            with self.subTest(adapter=adapter):
                files = render_skill_files(adapter, ROOT, upstream_root=PLUGINS)
                joined = b"\n".join(files.values())
                for token in forbidden:
                    self.assertNotIn(token, joined)
                self.assertEqual(
                    semantic_parity_errors(adapter, ROOT, upstream_root=PLUGINS),
                    (),
                )

    def test_clobber_manifest_rejects_hand_edits_and_non_generated_ownership(self):
        """A changed generated file or claimed authored/plugin path must be refused."""
        installed, files, manifest = self.full_generated_install()
        path = "architect/SKILL.md"

        check_clobber_manifest("claude", ROOT, installed, manifest, upstream_root=PLUGINS)
        (installed / path).write_bytes(b"hand edit\n")
        with self.assertRaisesRegex(SkillCatalogError, "hand-edited"):
            check_clobber_manifest("claude", ROOT, installed, manifest, upstream_root=PLUGINS)

        authored_manifest = "{}  king-mode/SKILL.md\n".format("0" * 64).encode()
        with self.assertRaisesRegex(SkillCatalogError, "not generated"):
            check_clobber_manifest("claude", ROOT, installed, authored_manifest, upstream_root=PLUGINS)

    def test_upstream_revision_cli_manifests_and_full_render_are_skill_aware(self):
        """Revision drift or a manifest omitting catalog accounting must fail."""
        self.assertEqual(check_upstream("pstack", ROOT, PLUGINS)["revision"], "63d938c")
        for adapter, guidance in (("claude", "CLAUDE.md"), ("codex", "AGENTS.md")):
            stdout = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
                self.assertEqual(
                    main(["sync-upstream", "pstack", "--adapter", adapter, "--bundle-manifest"]),
                    0,
                )
            document = json.loads(stdout.getvalue())
            self.assertEqual(len(document["skills"]), 65)
            bundle = render_bundle(adapter, ROOT)
            self.assertIn(guidance, bundle)
            if adapter == "claude":
                self.assertIn("skills/king-mode/SKILL.md", bundle)
            else:
                self.assertNotIn("skills/king-mode/SKILL.md", bundle)
            self.assertNotIn("skills/cloudflare/SKILL.md", bundle)

    def test_sync_pstack_wrapper_is_a_pure_adapter_aware_entry_point(self):
        """The compatibility command must return a manifest without native writes."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        environment = dict(os.environ)
        environment["HOME"] = temporary.name
        environment["PSTACK_REPO"] = str(Path(temporary.name) / "missing")

        result = subprocess.run(
            [str(ROOT / "scripts/sync-pstack.sh"), "--adapter", "claude", "--bundle-manifest"],
            cwd=str(ROOT),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["skills"]), 65)
        for native_name in (".claude", ".codex", ".kingstack"):
            self.assertFalse((Path(temporary.name) / native_name).exists())
