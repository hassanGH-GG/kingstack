"""Normalized lifecycle envelope validation."""

from types import MappingProxyType
from typing import Mapping


class HookError(ValueError):
    """Raised when a lifecycle envelope or native payload is invalid."""


EVENTS = ("SessionStart", "Stop", "PreCompact", "PostToolUse", "SubagentStart")
REQUIRED = ("event", "agent", "session_id", "project", "payload")


def validate_event(event: object) -> Mapping[str, object]:
    if not isinstance(event, dict):
        raise HookError("lifecycle event must be an object")
    missing = [key for key in REQUIRED if key not in event]
    if missing:
        raise HookError("lifecycle event missing {}".format(", ".join(missing)))
    if event["event"] not in EVENTS:
        raise HookError("unknown lifecycle event '{}'".format(event["event"]))
    if not isinstance(event["agent"], str) or not event["agent"]:
        raise HookError("lifecycle event agent must be a non-empty string")
    if not isinstance(event["session_id"], str) or not event["session_id"]:
        raise HookError("lifecycle event session_id must be a non-empty string")
    if not isinstance(event["project"], str) or not event["project"]:
        raise HookError("lifecycle event project must be a non-empty string")
    if not isinstance(event["payload"], dict):
        raise HookError("lifecycle event payload must be an object")
    return MappingProxyType(
        {
            "event": event["event"],
            "agent": event["agent"],
            "session_id": event["session_id"],
            "project": event["project"],
            "payload": MappingProxyType(dict(event["payload"])),
        }
    )
