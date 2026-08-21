"""Per-human runtime profile. Identity and checkout live here, not in the repo."""

import json
import os
from pathlib import Path
from typing import Mapping, Optional

from kingstack.memory_store import _atomic_write


IDENTITIES = ("personal", "hassan")


class ProfileError(ValueError):
    """Raised when the runtime profile is invalid."""


def profile_path(runtime: Path) -> Path:
    return Path(runtime) / "profile.json"


def load_profile(runtime: Path) -> Optional[Mapping[str, object]]:
    path = profile_path(runtime)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    identity = payload.get("identity")
    if identity not in IDENTITIES:
        raise ProfileError("profile identity must be personal or hassan")
    return payload


def save_profile(runtime: Path, identity: str, checkout: Path) -> Mapping[str, object]:
    if identity not in IDENTITIES:
        raise ProfileError("profile identity must be personal or hassan")
    payload = {
        "schema": 1,
        "identity": identity,
        "checkout": str(Path(checkout).resolve()),
    }
    runtime = Path(runtime)
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    _atomic_write(profile_path(runtime), json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n")
    return payload


def hook_environment(home: Optional[Path] = None) -> Mapping[str, str]:
    root = Path(home or Path.home()) / ".kingstack"
    try:
        profile = load_profile(root)
    except ProfileError:
        return {}
    if profile is None:
        return {}
    extra = {
        "KINGSTACK_IDENTITY": str(profile["identity"]),
        "KINGSTACK_MEMORY_ROOT": str(root / "memory"),
        "KINGSTACK_HEADROOM_ROOT": str(root / "headroom"),
        "KINGSTACK_SESSIONS_ROOT": str(root / "sessions"),
    }
    checkout = profile.get("checkout")
    if checkout:
        extra["KINGSTACK_ROOT"] = str(checkout)
    return extra


def apply_hook_env(home: Optional[Path] = None) -> Mapping[str, str]:
    extra = hook_environment(home)
    for key, value in extra.items():
        os.environ.setdefault(key, value)
    return extra
