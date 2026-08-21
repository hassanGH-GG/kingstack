"""Dry-run activation plans. Live apply stays forbidden."""

import json
from pathlib import Path
from typing import Any, Mapping


class ActivationError(ValueError):
    """Raised when an activation plan is invalid or live apply is requested."""


def load_owned_paths(root: Path, adapter: str) -> Mapping[str, Any]:
    path = Path(root) / "adapters" / adapter / "owned-paths.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("adapter") != adapter:
        raise ActivationError("owned-paths adapter mismatch")
    if "" in payload.get("fully_owned", []) or "." in payload.get("fully_owned", []):
        raise ActivationError("whole-home ownership is forbidden")
    return payload


def plan_activation(adapter: str, root: Path, native_home: Path, release_id: str) -> Mapping[str, Any]:
    owned = load_owned_paths(root, adapter)
    home = Path(native_home)
    return {
        "schema_version": 1,
        "adapter": adapter,
        "release": release_id,
        "native_home": str(home),
        "writes": False,
        "owned": [
            {"live": str(home / relative), "release": relative}
            for relative in owned["fully_owned"]
        ],
        "mixed": [
            {"live": str(home / relative), "mode": "merge"}
            for relative in owned["mixed"]
        ],
        "forbidden_untouched": [str(home / relative) for relative in owned["forbidden"]],
    }


def apply_activation(plan: Mapping[str, Any], fail_after=None) -> Mapping[str, Any]:
    raise ActivationError("live apply is forbidden until Hassan approves the pre-link briefing")
