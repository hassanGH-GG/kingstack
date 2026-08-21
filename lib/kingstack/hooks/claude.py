"""Claude-native payload normalization and hook output shaping."""

import json
from pathlib import Path

from kingstack.hooks.dispatch import handle
from kingstack.hooks.events import HookError


def normalize(event_name: str, payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise HookError("Claude payload must be an object")
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    mapped = {
        "SessionStart": {},
        "Stop": {"transcript_path": payload.get("transcript_path") or ""},
        "PreCompact": {"transcript_path": payload.get("transcript_path") or ""},
        "PostToolUse": {
            "tool_name": payload.get("tool_name") or "tool",
            "tool_response": payload.get("tool_response", ""),
        },
        "SubagentStart": {
            "role": tool_input.get("subagent_type") or "default",
            "model": tool_input.get("model") or "inherit",
            "effort": tool_input.get("effort") or "inherit",
            "task": tool_input.get("description") or tool_input.get("prompt") or "agent",
        },
    }
    if event_name not in mapped:
        raise HookError("unknown Claude lifecycle event '{}'".format(event_name))
    return {
        "event": event_name,
        "agent": "claude",
        "session_id": payload.get("session_id") or "unknown",
        "project": payload.get("cwd") or str(Path.cwd()),
        "payload": mapped[event_name],
    }


def format_output(event_name: str, result: dict) -> str:
    if event_name in {"SessionStart", "PreCompact"}:
        document = {
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "additionalContext": result.get("additionalContext", ""),
            }
        }
    elif event_name in {"PostToolUse", "SubagentStart"}:
        document = {}
        if result.get("systemMessage"):
            document["systemMessage"] = result["systemMessage"]
    else:
        document = {}
    return json.dumps(document, separators=(",", ":"))


def run_event(event_name: str, raw: str, runtime) -> tuple:
    runtime = Path(runtime)
    if event_name == "Stop":
        try:
            payload = json.loads(raw) if raw.strip() else {}
            handle(normalize(event_name, payload), runtime)
        except Exception:
            pass
        return 0, "{}"
    try:
        payload = json.loads(raw) if raw.strip() else {}
        result = handle(normalize(event_name, payload), runtime)
        return 0, format_output(event_name, result)
    except Exception:
        return 2, "{}"
