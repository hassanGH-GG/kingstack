"""Independent staged health rows. Live mode passes when native homes are linked."""

import json
from pathlib import Path
from typing import List, Mapping

from kingstack.adapter_contract import load_adapter, load_capability_catalog, validate_adapter
from kingstack.docs_hygiene import hygiene_errors
from kingstack.ownership import discover_adapters, load_ownership, native_homes, ownership_matches_bundle
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
    try:
        catalog = load_catalog(root)
    except Exception:
        return []
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
    leftover_plans = [path for path in PLAN_FILES if (root / path).is_file()]
    rows.append(_row(
        "plan-files-removed",
        "core",
        not leftover_plans,
        "six plan files gone" if not leftover_plans else leftover_plans[0],
        "delete cutover plan files after live link",
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
        if adapter == "codex":
            try:
                allowed = set(json.loads((root / "adapters/codex/status-line-items.json").read_text(encoding="utf-8")))
                owned = json.loads((root / "adapters/codex/config-owned.json").read_text(encoding="utf-8"))
                unknown = [item for item in owned["tui.status_line"] if item not in allowed]
                rows.append(_row(
                    "codex-status-line",
                    "codex",
                    not unknown,
                    "valid" if not unknown else unknown[0],
                    "use a Codex StatusLineItem id",
                ))
            except Exception as error:
                rows.append(_row("codex-status-line", "codex", False, str(error), "fix config-owned.json"))
        undeclared = _undeclared_constructs(root, adapter)
        rows.append(_row(
            "unsupported-closed:" + adapter,
            adapter,
            not undeclared,
            "ok" if not undeclared else undeclared[0],
            "declare the construct or drop the target",
        ))
    try:
        from kingstack.headroom import check_pin
        pin = check_pin(root)
        rows.append(_row("headroom-pin", "core", True, pin["revision"], "sync-upstream headroom --check"))
    except Exception as error:
        rows.append(_row("headroom-pin", "core", False, str(error), "pin headroom checkout"))
    hygiene = hygiene_errors(root)
    rows.append(_row("docs-hygiene", "core", not hygiene, "ok" if not hygiene else "; ".join(hygiene[:3]), "classify markdown"))
    briefing = root / "docs/migration/pre-link-briefing.md"
    rows.append(_row("pre-link-briefing", "core", briefing.is_file(), str(briefing), "write briefing"))
    return rows


def _home_linked(name: str) -> bool:
    home = Path.home() / name
    return (home / ".kingstack-activation.json").is_file() and (home / ".kingstack-current").exists()


def live_checks(root: Path) -> List[Mapping[str, object]]:
    rows = list(staged_checks(root))
    homes = native_homes(root)
    missing = [name for name in homes if not _home_linked(name)]
    rows.append(_row(
        "live-activation",
        "core",
        not missing,
        "linked {}".format(",".join(homes)) if not missing else "unlinked {}".format(",".join(missing)),
        "ok" if not missing else "activate each adapter",
    ))
    shim = Path.home() / ".local" / "bin" / "kingstack"
    target = Path(root).resolve() / "scripts" / "kingstack"
    linked = (
        shim.is_file()
        and not shim.is_symlink()
        and str(target) in shim.read_text(encoding="utf-8")
    )
    rows.append(_row(
        "cli-shim",
        "core",
        linked,
        str(shim) if linked else "missing {}".format(shim),
        "run kingstack setup",
    ))
    return rows


def overall(rows: List[Mapping[str, object]]) -> str:
    if any(row["status"] != "pass" for row in rows):
        return "unhealthy"
    return "healthy"
