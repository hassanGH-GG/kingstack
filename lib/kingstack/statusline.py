"""Portable context status line. Same cost math for every adapter."""

import json
import os
import sys
from typing import Any, Mapping


USD_PER_M_CACHE_READ = 0.69
AMBER, RED = 60000, 150000
G, A, R, D, X = "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m"


def context_tokens(transcript_path: str) -> int:
    if not transcript_path or not os.path.exists(transcript_path):
        return 0
    try:
        with open(transcript_path, "rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - 400000))
            lines = handle.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return 0
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            usage = json.loads(line).get("message", {}).get("usage") or {}
        except json.JSONDecodeError:
            continue
        total = (
            usage.get("input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
        )
        if total:
            return int(total)
    return 0


def load_payload(raw: str) -> Mapping[str, Any]:
    if raw.strip():
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {
        "transcript_path": os.environ.get("KINGSTACK_TRANSCRIPT", ""),
        "workspace": {"current_dir": os.getcwd()},
        "model": {"display_name": os.environ.get("KINGSTACK_MODEL", "")},
        "cost": {},
    }


def render_status(payload: Mapping[str, Any]) -> str:
    ctx = context_tokens(str(payload.get("transcript_path") or ""))
    colour = R if ctx >= RED else A if ctx >= AMBER else G
    per_req = ctx / 1000000 * USD_PER_M_CACHE_READ
    workspace = payload.get("workspace") or {}
    cwd = workspace.get("current_dir") or os.getcwd()
    model = (payload.get("model") or {}).get("display_name", "")
    parts = [
        "{}{}{}".format(D, os.path.basename(cwd), X),
        "{}{}{}".format(D, model, X),
    ]
    if ctx:
        parts.append("{}ctx {}k{} {}$${:.2f}/req{}".format(colour, ctx // 1000, X, D, per_req, X))
    session_cost = (payload.get("cost") or {}).get("total_cost_usd")
    if session_cost:
        parts.append("{}session ${:.2f}{}".format(D, float(session_cost), X))
    if ctx >= RED:
        parts.append("{}/clear{}".format(R, X))
    return "  ".join(part for part in parts if part.strip(D + X))


def main(argv=None) -> int:
    del argv
    print(render_status(load_payload(sys.stdin.read())))
    return 0
