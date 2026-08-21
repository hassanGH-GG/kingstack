"""PostToolUse: archive fat results into CCR so the thread can drop them."""

import json
from pathlib import Path

from kingstack.headroom import HeadroomError, crush, default_store


THRESHOLD = 30000
ROOT = Path(__file__).resolve().parents[3]


def handle(event, runtime) -> dict:
    payload = event["payload"]
    response = payload.get("tool_response", "")
    if isinstance(response, str):
        text = response
        size = len(text)
    else:
        text = json.dumps(response, default=str)
        size = len(text)
    if size < THRESHOLD:
        return {}
    tool = payload.get("tool_name") or "tool"
    try:
        record = crush(text, default_store(), ROOT, tool=tool)
        return {"systemMessage": record["notice"]}
    except HeadroomError:
        return {
            "systemMessage": (
                "⚠ {} result ~{}KB entered the main thread; it will be re-read "
                "every turn until compaction. Ruler: bulk over ~200 lines goes to "
                "a haiku subagent that returns a summary."
            ).format(tool, size // 1024)
        }
