#!/usr/bin/env python3
"""Dispatch a Codex lifecycle event through the portable handlers."""

import json
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

from kingstack.hooks.codex import format_output  # noqa: E402
from kingstack.hooks.dispatch import handle  # noqa: E402
from kingstack.profile import apply_hook_env  # noqa: E402

apply_hook_env()


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: run.py EVENT", file=sys.stderr)
        return 2
    runtime = Path(os.environ.get("KINGSTACK_RUNTIME", Path.home() / ".codex"))
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    event = {
        "event": argv[0],
        "agent": "codex",
        "session_id": payload.get("session_id") or "unknown",
        "project": payload.get("cwd") or str(Path.cwd()),
        "payload": payload,
    }
    if argv[0] == "Stop":
        try:
            handle(event, runtime)
        except Exception:
            pass
        sys.stdout.write("{}\n")
        return 0
    try:
        result = handle(event, runtime)
    except Exception:
        raise
    sys.stdout.write(format_output(argv[0], result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
