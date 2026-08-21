"""Independent staged health rows. Live mode stays unhealthy on real homes."""

from pathlib import Path
from typing import List, Mapping

from kingstack.adapter_contract import load_adapter, load_capability_catalog, validate_adapter
from kingstack.docs_hygiene import hygiene_errors
from kingstack.ownership import discover_adapters, load_ownership, ownership_matches_bundle
from kingstack.render import render_bundle
from kingstack.schedules import load_schedules
from kingstack.skills import _UNSUPPORTED_CONSTRUCT_TOKENS, load_catalog


PLAN_FILES = (
    "docs/superpowers/plans/2026-08-20-agent-neutral-kingstack-migration.md",
    "docs/superpowers/plans/2026-08-20-kingstack-foundation-plan.md",
    "docs/superpowers/plans/2026-08-20-kingstack-core-claude-plan.md",
    "docs/superpowers/plans/2026-08-20-kingstack-shared-memory-plan.md",
    "docs/superpowers/plans/2026-08-20-kingstack-codex-adapter-plan.md",
    "docs/superpowers/plans/2026-08-20-kingstack-cutover-plan.md",
)


def _row(identity: str, adapter: str, ok: bool, evidence: str, fix: str) -> Mapping[str, object]:
    return {
        "id": identity,
        "adapter": adapter,
        "status": "pass" if ok else "fail",
        "evidence": evidence,
        "fix": fix,
    }


def _undeclared_constructs(root: Path, adapter: str) -> List[str]:
    catalog = load_catalog(root)
    declared = catalog.unsupported.get(adapter) or {}
    if not declared:
        return []
    unsupported = set(declared)
    errors = []
    for entry in catalog.entries:
        if adapter not in entry.targets or entry.owner == "plugin-manager" or entry.name in unsupported:
            continue
        for resource, content in catalog.sources[entry.name].items():
            for construct, token in _UNSUPPORTED_CONSTRUCT_TOKENS.items():
                if token in content:
                    errors.append("{}:{}:{}".format(entry.name, resource, construct))
    return errors


def staged_checks(root: Path) -> List[Mapping[str, object]]:
    root = Path(root)
    rows = []
    rows.append(_row("version", "core", (root / "VERSION").is_file(), str(root / "VERSION"), "add VERSION"))
    try:
        document = load_schedules(root)
        mismatches = []
        for item in document["schedules"]:
            name = Path(item["command"]).name
            plist = root / "launchd" / "{}.plist".format(item["id"])
            if not plist.is_file() or name not in plist.read_text(encoding="utf-8"):
                mismatches.append(item["id"])
        rows.append(_row("schedules", "core", not mismatches, "portable templates" if not mismatches else mismatches[0], "align schedules.json with launchd"))
    except Exception as error:
        rows.append(_row("schedules", "core", False, str(error), "fix schedule schema"))
    missing_plans = [path for path in PLAN_FILES if not (root / path).is_file()]
    rows.append(_row(
        "plan-files-still-present",
        "core",
        not missing_plans,
        "six plan files remain" if not missing_plans else "missing {}".format(missing_plans),
        "do not delete plan files before cutover",
    ))
    for adapter in discover_adapters(root):
        try:
            declaration = load_adapter(root / "adapters" / adapter / "adapter.json")
            errors = validate_adapter(declaration, load_capability_catalog(root / "core/capabilities/catalog.json"))
            rows.append(_row("contract:" + adapter, adapter, not errors, "valid" if not errors else "; ".join(errors), "fix adapter.json"))
        except Exception as error:
            rows.append(_row("contract:" + adapter, adapter, False, str(error), "fix adapter contract"))
        try:
            bundle = render_bundle(adapter, root)
            owned = load_ownership(root, adapter)
            mismatches = ownership_matches_bundle(owned, list(bundle))
            rows.append(_row("ownership:" + adapter, adapter, not mismatches, "aligned" if not mismatches else mismatches[0], "fix owned-paths.json"))
            rows.append(_row("render:" + adapter, adapter, bool(bundle), "{} files".format(len(bundle)), "fix renderer"))
        except Exception as error:
            rows.append(_row("render:" + adapter, adapter, False, str(error), "fix renderer"))
        undeclared = _undeclared_constructs(root, adapter)
        rows.append(_row(
            "unsupported-closed:" + adapter,
            adapter,
            not undeclared,
            "ok" if not undeclared else undeclared[0],
            "declare the construct or drop the target",
        ))
    hygiene = hygiene_errors(root)
    rows.append(_row("docs-hygiene", "core", not hygiene, "ok" if not hygiene else "; ".join(hygiene[:3]), "classify markdown"))
    briefing = root / "docs/migration/pre-link-briefing.md"
    rows.append(_row("pre-link-briefing", "core", briefing.is_file(), str(briefing), "write briefing"))
    return rows


def live_checks(root: Path) -> List[Mapping[str, object]]:
    rows = list(staged_checks(root))
    rows.append(_row(
        "live-activation",
        "core",
        False,
        "no native home is linked",
        "wait for Hassan to approve live link",
    ))
    return rows


def overall(rows: List[Mapping[str, object]]) -> str:
    if any(row["status"] != "pass" for row in rows):
        return "unhealthy"
    return "healthy"
