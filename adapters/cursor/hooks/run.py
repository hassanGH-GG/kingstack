#!/usr/bin/env python3
"""Read one Cursor hook payload and dispatch the portable handler."""

import os
import sys
from pathlib import Path


def _lib_path() -> Path:
    root = os.environ.get("KINGSTACK_ROOT")
    if root:
        return Path(root) / "lib"
    here = Path(__file__).resolve().parent
    for candidate in (here.parents[2] / "lib", here.parents[3] / "lib"):
        if (candidate / "kingstack").is_dir():
            return candidate
    default = Path.home() / "Desktop/Work/kingstack/lib"
    if (default / "kingstack").is_dir():
        return default
    raise SystemExit("kingstack hook runner cannot locate lib/")


sys.path.insert(0, str(_lib_path()))

from kingstack.hooks.cursor import run_event  # noqa: E402
from kingstack.profile import apply_hook_env  # noqa: E402

apply_hook_env()


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: run.py EVENT", file=sys.stderr)
        return 2
    runtime = Path(os.environ.get("KINGSTACK_RUNTIME", Path.home() / ".cursor"))
    code, output = run_event(argv[0], sys.stdin.read(), runtime)
    sys.stdout.write(output)
    if not output.endswith("\n"):
        sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
