"""Rendered Claude capability-ID parity against the frozen baseline."""

import json
from pathlib import Path
from types import MappingProxyType

from kingstack.render import render_bundle
from kingstack.skills import load_catalog


def _row(state, where):
    return {"state": state, "where": where}


def _live_home() -> Path:
    return Path.home() / ".claude"


def _heading(root: Path, name: str) -> str:
    for line in (root / "core/instructions" / name).read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            return line
    return name


def rendered_parity(adapter: str, root: Path) -> MappingProxyType:
    root = Path(root)
    baseline = json.loads((root / "core/parity/claude-baseline.json").read_text(encoding="utf-8"))
    bundle = render_bundle(adapter, root)
    catalog = load_catalog(root)
    guidance = bundle.get("CLAUDE.md", b"").decode("utf-8")
    live = _live_home()
    ids = {}

    for name in catalog.available_names(adapter):
        path = "skills/{}/SKILL.md".format(name)
        live_skill = live / "skills" / name / "SKILL.md"
        if path in bundle:
            ids["skill:{}".format(name)] = _row("in_bundle", path)
        elif catalog.owner(name) == "plugin-manager" and live_skill.is_file():
            ids["skill:{}".format(name)] = _row("live_preserved", str(live_skill))
        else:
            ids["skill:{}".format(name)] = _row("missing", path)

    for capability, path in baseline["hooks"].items():
        ids["hook:{}".format(capability)] = (
            _row("in_bundle", path) if path in bundle else _row("missing", path)
        )

    for name in baseline["commands"]:
        path = root / "scripts" / name
        ids["command:{}".format(name)] = (
            _row("in_bundle", str(path)) if path.is_file() else _row("missing", str(path))
        )
    for name in baseline["schedules"]:
        path = root / "launchd" / name
        ids["schedule:{}".format(name)] = (
            _row("in_bundle", str(path)) if path.is_file() else _row("missing", str(path))
        )
    for name in baseline["sweeps"]:
        path = root / "sweeps" / name
        ids["sweep:{}".format(name)] = (
            _row("in_bundle", str(path)) if path.is_file() else _row("missing", str(path))
        )
    for name in baseline["agents"]:
        path = live / "agents" / name
        ids["agent:{}".format(name[:-3] if name.endswith(".md") else name)] = (
            _row("live_preserved", str(path)) if path.is_file() else _row("missing", str(path))
        )
    for name in baseline["instructions"]:
        heading = _heading(root, name)
        ids["instruction:{}".format(name)] = (
            _row("in_bundle", "CLAUDE.md") if heading in guidance else _row("missing", name)
        )

    settings = live / "settings.json"
    settings_text = settings.read_text(encoding="utf-8") if settings.is_file() else ""
    ids["policy:compaction-200k"] = (
        _row("live_preserved", str(settings))
        if '"autoCompactWindow": 200000' in settings_text
        else _row("missing", str(settings))
    )
    ids["policy:effort-medium"] = (
        _row("live_preserved", str(settings))
        if '"effortLevel": "medium"' in settings_text
        else _row("missing", str(settings))
    )
    ids["policy:pstack-63d938c"] = (
        _row("in_bundle", "core/skills/catalog.json")
        if catalog.upstream_revision("pstack") == "63d938c"
        else _row("missing", "pstack revision")
    )

    mismatches = [
        name for name, row in ids.items() if row["state"] not in {"in_bundle", "live_preserved"}
    ]
    return MappingProxyType(
        {
            "ok": not mismatches,
            "adapter": adapter,
            "ids": MappingProxyType(ids),
            "mismatches": tuple(sorted(mismatches)),
            "commands": tuple(baseline["commands"]),
            "schedules": tuple(baseline["schedules"]),
            "sweeps": tuple(baseline["sweeps"]),
            "instructions": tuple(baseline["instructions"]),
        }
    )
