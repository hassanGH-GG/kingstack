"""Codex-native hook output shaping.

Portable handlers return Claude-shaped keys (`additionalContext`, `blocked`).
Codex 0.149 rejects those at the top level. SessionStart must wrap context in
`hookSpecificOutput`. Stop must be an empty object.
"""

import json


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
