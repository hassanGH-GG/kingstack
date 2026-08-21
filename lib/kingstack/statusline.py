"""One readable status line for Claude, Codex, and Cursor."""

import json
import os
import sys
from typing import Any, List, Mapping, Optional, Tuple


USD_PER_M_CACHE_READ = 0.69
AMBER_PCT, RED_PCT = 30, 75
AMBER_TOKENS, RED_TOKENS = 60000, 150000
G, A, R, D, X = "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m"
SHORT_MODELS = ("haiku", "sonnet", "opus", "fable", "terra", "sol")


def short_model(name: str) -> str:
    text = (name or "").lower()
    for token in SHORT_MODELS:
        if token in text:
            return token
    return text.split("/")[-1].split("-")[0][:16] if text else ""


def _tail_events(transcript_path: str) -> List[Mapping[str, Any]]:
    if not transcript_path or not os.path.exists(transcript_path):
        return []
    try:
        with open(transcript_path, "rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - 400000))
            lines = handle.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return []
    events = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _usage_tokens(usage: Mapping[str, Any]) -> int:
    return int(
        (usage.get("input_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
    )


def context_from_payload(payload: Mapping[str, Any]) -> Tuple[int, int, Optional[int]]:
    window = payload.get("context_window") or {}
    usage = window.get("current_usage") or {}
    used = _usage_tokens(usage) or int(window.get("total_input_tokens") or 0)
    size = int(window.get("context_window_size") or 0)
    pct = window.get("used_percentage")
    if used:
        return used, size, int(pct) if pct is not None else None
    events = _tail_events(str(payload.get("transcript_path") or ""))
    for event in reversed(events):
        if event.get("isSidechain"):
            continue
        used = _usage_tokens((event.get("message") or {}).get("usage") or {})
        if used:
            return used, 0, None
    return 0, 0, None


def context_tokens(transcript_path: str) -> int:
    used, _, _ = context_from_payload({"transcript_path": transcript_path})
    return used


def effort_level(payload: Mapping[str, Any]) -> str:
    effort = payload.get("effort")
    if isinstance(effort, dict) and effort.get("level"):
        return str(effort["level"])
    if isinstance(effort, str) and effort:
        return effort
    if payload.get("effortLevel"):
        return str(payload["effortLevel"])
    return os.environ.get("KINGSTACK_EFFORT", "")


def subagent_models(payload: Mapping[str, Any], main: str) -> List[str]:
    found = []
    seen = set()
    agent = payload.get("agent") or {}
    current = short_model(str(agent.get("model") or ""))
    if current and current != main:
        found.append(current)
        seen.add(current)
    for event in reversed(_tail_events(str(payload.get("transcript_path") or ""))):
        message = event.get("message") or {}
        candidates = []
        if event.get("isSidechain") and message.get("model"):
            candidates.append(message["model"])
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("name") not in ("Task", "Agent"):
                continue
            model = (block.get("input") or {}).get("model")
            if model:
                candidates.append(model)
        for name in candidates:
            short = short_model(str(name))
            if not short or short == main or short in seen:
                continue
            seen.add(short)
            found.append(short)
            if len(found) >= 3:
                return found
    return found


def _colour_for(used: int, size: int, pct: Optional[int]) -> str:
    if pct is None and size:
        pct = int(used * 100 / size)
    if pct is not None:
        if pct >= RED_PCT:
            return R
        if pct >= AMBER_PCT:
            return A
        return G
    if used >= RED_TOKENS:
        return R
    if used >= AMBER_TOKENS:
        return A
    return G


def render_status(payload: Mapping[str, Any]) -> str:
    workspace = payload.get("workspace") or {}
    cwd = os.path.basename(workspace.get("current_dir") or os.getcwd())
    model = short_model((payload.get("model") or {}).get("display_name") or (payload.get("model") or {}).get("id") or "")
    effort = effort_level(payload)
    used, size, pct = context_from_payload(payload)
    if pct is None and used and size:
        pct = int(used * 100 / size)
    colour = _colour_for(used, size, pct)
    session_cost = (payload.get("cost") or {}).get("total_cost_usd")
    subs = subagent_models(payload, model)

    parts = ["{}{}{}".format(D, cwd, X)]
    if model:
        parts.append("model {}".format(model))
    if effort:
        parts.append("effort {}".format(effort))
    if used:
        ctx = "ctx {}k".format(used // 1000)
        if pct is not None:
            ctx += " ({}%)".format(pct)
        elif size:
            ctx += " / {}k".format(size // 1000)
        parts.append("{}{}{}".format(colour, ctx, X))
        parts.append("{}${:.2f}/req{}".format(D, used / 1000000 * USD_PER_M_CACHE_READ, X))
    if session_cost:
        parts.append("session ${:.2f}".format(float(session_cost)))
    if subs:
        parts.append("subagents {}".format(",".join(subs)))
    if colour == R:
        parts.append("{}/clear{}".format(R, X))
    return "  ".join(part for part in parts if part.strip(D + X))


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
        "effort": {"level": os.environ.get("KINGSTACK_EFFORT", "")},
        "cost": {},
    }


def main(argv=None) -> int:
    del argv
    print(render_status(load_payload(sys.stdin.read())))
    return 0
