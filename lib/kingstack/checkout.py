"""Find the kingstack checkout without assuming one laptop path."""

import os
from pathlib import Path
from typing import Mapping, Optional


MARKERS = ("VERSION", "core/instructions", "scripts/kingstack", "lib/kingstack")


class CheckoutError(ValueError):
    """Raised when the checkout cannot be found."""


def is_checkout(path: Path) -> bool:
    root = Path(path)
    return all((root / name).exists() for name in MARKERS)


def discover_checkout(
    cwd: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    profile_checkout: Optional[Path] = None,
) -> Path:
    environment = env if env is not None else os.environ
    override = environment.get("KINGSTACK_ROOT")
    if override:
        candidate = Path(override).expanduser()
        if is_checkout(candidate):
            return candidate.resolve()
        raise CheckoutError("KINGSTACK_ROOT is not a kingstack checkout")
    if profile_checkout is not None:
        candidate = Path(profile_checkout).expanduser()
        if is_checkout(candidate):
            return candidate.resolve()
    here = Path(cwd or Path.cwd()).resolve()
    for path in [here, *here.parents]:
        if is_checkout(path):
            return path
    default = Path.home() / "Desktop/Work/kingstack"
    if is_checkout(default):
        return default.resolve()
    raise CheckoutError(
        "cannot find kingstack checkout; set KINGSTACK_ROOT or run from the clone"
    )


def try_discover_checkout(
    cwd: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    profile_checkout: Optional[Path] = None,
) -> Optional[Path]:
    try:
        return discover_checkout(cwd=cwd, env=env, profile_checkout=profile_checkout)
    except CheckoutError:
        return None
