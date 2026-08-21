"""One-command colleague setup. Idempotent. Never writes a native home."""

import os
from pathlib import Path
from typing import Mapping, Optional

from kingstack.checkout import CheckoutError, discover_checkout, is_checkout
from kingstack.headroom import HeadroomError, check_pin, pin_revision
from kingstack.memory_store import MemoryStore
from kingstack.session_store import SessionStore
from kingstack.ownership import native_homes
from kingstack.profile import IDENTITIES, save_profile
from kingstack.skills import load_catalog


class SetupError(ValueError):
    """Raised when setup would write a native home or the checkout is missing."""


def ensure_cli_shim(checkout: Path, home: Path) -> Path:
    target = Path(checkout).resolve() / "scripts" / "kingstack"
    if not target.is_file():
        raise SetupError("missing {}".format(target))
    bindir = Path(home).expanduser() / ".local" / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    shim = bindir / "kingstack"
    body = "#!/bin/sh\nset -eu\nexec '{}' \"$@\"\n".format(target)
    if shim.is_file() and not shim.is_symlink() and shim.read_text(encoding="utf-8") == body:
        return shim
    if shim.exists() or shim.is_symlink():
        shim.unlink()
    shim.write_text(body, encoding="utf-8")
    os.chmod(shim, 0o755)
    return shim


def _refuse_native_runtime(runtime: Path, checkout: Path, home: Path) -> Path:
    resolved = Path(runtime).expanduser().resolve()
    home = Path(home).expanduser().resolve()
    for name in native_homes(checkout):
        native = (home / name).resolve()
        if resolved == native or str(resolved).startswith(str(native) + os.sep):
            raise SetupError("refusing native home {}".format(native))
    return resolved


def setup(
    checkout: Optional[Path] = None,
    runtime: Optional[Path] = None,
    identity: str = "personal",
    home: Optional[Path] = None,
    headroom_checkout: Optional[Path] = None,
    cwd: Optional[Path] = None,
) -> Mapping[str, object]:
    if identity not in IDENTITIES:
        raise SetupError("identity must be personal or hassan")
    home = Path(home or Path.home()).expanduser()
    try:
        root = Path(checkout).resolve() if checkout is not None else discover_checkout(cwd=cwd)
    except CheckoutError as error:
        raise SetupError(str(error)) from error
    if not is_checkout(root):
        raise SetupError("not a kingstack checkout")
    runtime = _refuse_native_runtime(
        Path(runtime) if runtime is not None else home / ".kingstack",
        root,
        home,
    )
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(runtime, 0o700)
    save_profile(runtime, identity, root)
    ensure_cli_shim(root, home)
    MemoryStore.open(runtime / "memory", repo_root=root)
    SessionStore.open(runtime / "sessions", repo_root=root)
    (runtime / "headroom").mkdir(mode=0o700, exist_ok=True)
    try:
        catalog = load_catalog(root)
        pstack = {
            "status": "clean",
            "revision": catalog.upstream_revision("pstack"),
            "clone": None,
        }
    except Exception as error:
        pin = (root / "pstack-upstream.txt").read_text(encoding="utf-8").splitlines()[0]
        pstack = {
            "status": "missing",
            "revision": str(error),
            "clone": "git clone https://github.com/cursor/plugins.git {0} && git -C {0} checkout {1}".format(
                root.parent / "plugins", pin
            ),
        }
    sibling = Path(headroom_checkout) if headroom_checkout is not None else root.parent / "headroom"
    clone = (
        "git clone https://github.com/headroomlabs-ai/headroom.git {0} "
        "&& git -C {0} checkout {1}"
    ).format(sibling, pin_revision(root))
    try:
        pin = check_pin(root, sibling)
        headroom = {"status": "clean", "revision": pin["revision"], "clone": None}
    except HeadroomError as error:
        headroom = {"status": "missing", "revision": str(error), "clone": clone}
    from kingstack.checks import overall, staged_checks
    rows = staged_checks(root)
    failing = [row["id"] for row in rows if row["status"] != "pass"]
    health = overall(rows)
    got = [
        "poteto-mode",
        "adapters",
        "routing",
        "headroom CCR",
        "empty memory store",
        "empty session store",
    ]
    not_got = ["Hassan's memory", "live native-home link"]
    if identity == "personal":
        not_got.insert(1, "king-mode overlay")
    else:
        got.append("king-mode overlay")
    return {
        "schema_version": 1,
        "checkout": str(root),
        "runtime": str(runtime),
        "identity": identity,
        "pstack": pstack,
        "headroom": headroom,
        "staged": health,
        "failing": failing,
        "got": got,
        "not_got": not_got,
        "native_homes_written": False,
    }
