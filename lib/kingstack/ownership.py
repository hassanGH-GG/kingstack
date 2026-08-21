"""Single ownership document for render, release, and activation."""

import json
from pathlib import Path
from typing import Any, List, Mapping, Tuple


class OwnershipError(ValueError):
    """Raised when an ownership document is invalid or disagrees with a bundle."""


def load_ownership(root: Path, adapter: str) -> Mapping[str, Any]:
    path = Path(root) / "adapters" / adapter / "owned-paths.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("adapter") != adapter:
        raise OwnershipError("owned-paths adapter mismatch")
    fully = list(payload.get("fully_owned") or [])
    mixed = list(payload.get("mixed") or [])
    payloads = list(payload.get("mixed_payloads") or [])
    forbidden = list(payload.get("forbidden") or [])
    for item in fully + mixed + payloads + forbidden:
        if item in ("", ".", "/"):
            raise OwnershipError("whole-home ownership is forbidden")
    return {
        "adapter": adapter,
        "fully_owned": fully,
        "mixed": mixed,
        "mixed_payloads": payloads,
        "forbidden": forbidden,
    }


def render_paths(ownership: Mapping[str, Any]) -> Tuple[str, ...]:
    return tuple(ownership["fully_owned"] + ownership["mixed_payloads"])


def discover_adapters(root: Path) -> List[str]:
    adapters = []
    base = Path(root) / "adapters"
    if not base.is_dir():
        return []
    for path in sorted(base.iterdir()):
        if path.name == "contract":
            continue
        if (path / "adapter.json").is_file():
            adapters.append(path.name)
    return adapters


def native_homes(root: Path) -> Tuple[str, ...]:
    homes = []
    for adapter in discover_adapters(root):
        raw = json.loads((Path(root) / "adapters" / adapter / "adapter.json").read_text())
        home = raw.get("native_home")
        if isinstance(home, str) and home:
            homes.append(home)
    return tuple(homes)


def ownership_matches_bundle(ownership: Mapping[str, Any], bundle_paths: List[str]) -> List[str]:
    allowed = render_paths(ownership)
    errors = []
    for path in bundle_paths:
        if not any(path == owned or path.startswith(owned + "/") for owned in allowed):
            errors.append("rendered '{}' is not owned".format(path))
    return errors
