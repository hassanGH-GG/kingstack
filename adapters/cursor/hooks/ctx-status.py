#!/usr/bin/env python3
"""Adapter-facing wrapper around the portable context status line."""

import os
import sys
from pathlib import Path


def _lib() -> Path:
    root = os.environ.get("KINGSTACK_ROOT")
    if root:
        return Path(root) / "lib"
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "lib"
        if (candidate / "kingstack" / "statusline.py").is_file():
            return candidate
    raise SystemExit("ctx-status cannot locate kingstack lib/")


sys.path.insert(0, str(_lib()))
from kingstack.statusline import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
