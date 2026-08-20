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
        root = Path(temporary.name)
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
        return root

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
        unknown_target["entries"][0]["targets"] = ["claude", "cursor"]
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
                memory["dependencies"] = ["king-mode"]
            with self.subTest(message=message):
                with self.assertRaisesRegex(SkillCatalogError, message):
                    load_catalog(self.temporary_catalog(payload), upstream_root=PLUGINS)

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
        with self.assertRaises(TypeError):
            files["new/SKILL.md"] = b"bad"

    def test_transforms_remove_foreign_hosts_and_preserve_semantics(self):
        """A host token leak or workflow-meaning change in any portable skill must fail."""
        for adapter, forbidden in (
            ("claude", (b".cursor", b"generalPurpose")),
            ("codex", (b".cursor", b".claude", b"Claude Code", b"CLAUDE.md")),
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
        files = render_skill_files("claude", ROOT, upstream_root=PLUGINS)
        path = "architect/SKILL.md"
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        installed = Path(temporary.name)
        (installed / "architect").mkdir()
        (installed / path).write_bytes(files[path])
        manifest = "{}  {}\n".format(hashlib.sha256(files[path]).hexdigest(), path).encode()

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
            self.assertIn("skills/king-mode/SKILL.md", bundle)
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
