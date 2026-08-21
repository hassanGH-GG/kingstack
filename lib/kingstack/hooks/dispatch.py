"""Dispatch a validated envelope to the matching portable handler."""

from pathlib import Path

from kingstack.hooks.events import HookError, validate_event
from kingstack.hooks import (
    post_tool_use,
    pre_compact,
    session_start,
    stop_capture,
    subagent_start,
)


HANDLERS = {
    "SessionStart": session_start.handle,
    "Stop": stop_capture.handle,
    "PreCompact": pre_compact.handle,
    "PostToolUse": post_tool_use.handle,
    "SubagentStart": subagent_start.handle,
}


def handle(event, runtime) -> dict:
    validated = validate_event(event)
    return HANDLERS[validated["event"]](validated, Path(runtime))
