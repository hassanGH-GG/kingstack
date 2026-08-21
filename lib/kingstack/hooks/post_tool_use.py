"""PostToolUse: flag tool results that will be re-read every later turn."""

import json


THRESHOLD = 30000


def handle(event, runtime) -> dict:
    payload = event["payload"]
    response = payload.get("tool_response", "")
    if isinstance(response, str):
        size = len(response)
    else:
        size = len(json.dumps(response, default=str))
    if size < THRESHOLD:
        return {}
    tool = payload.get("tool_name") or "tool"
    return {
        "systemMessage": (
            "⚠ {} result ~{}KB entered the main thread; it will be re-read "
            "every turn until compaction. Ruler: bulk over ~200 lines goes to "
            "a haiku subagent that returns a summary."
        ).format(tool, size // 1024)
    }
