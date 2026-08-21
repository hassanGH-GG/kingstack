"""Cursor-native payload normalization and hook output shaping."""

import json
from pathlib import Path

from kingstack.hooks.dispatch import handle
from kingstack.hooks.events import HookError


NATIVE_TO_PORTABLE = {
    "sessionStart": "SessionStart",
    "stop": "Stop",
    "preCompact": "PreCompact",
    "postToolUse": "PostToolUse",
    "subagentStart": "SubagentStart",
}
PORTABLE_TO_NATIVE = {value: key for key, value in NATIVE_TO_PORTABLE.items()}


def portable_event(event_name: str) -> str:
    if event_name in NATIVE_TO_PORTABLE:
        return NATIVE_TO_PORTABLE[event_name]
    if event_name in PORTABLE_TO_NATIVE:
        return event_name
    raise HookError("unknown Cursor lifecycle event '{}'".format(event_name))


def normalize(event_name: str, payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise HookError("Cursor payload must be an object")
    portable = portable_event(event_name)
    session_id = (
        payload.get("session_id") or payload.get("conversation_id") or "unknown"
    )
    project = payload.get("cwd")
    if not project:
        roots = payload.get("workspace_roots")
        if isinstance(roots, list) and roots:
            project = roots[0]
        else:
            project = str(Path.cwd())
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    effort = "inherit"
    params = payload.get("model_params")
    if isinstance(params, list):
        for item in params:
            if isinstance(item, dict) and item.get("id") == "effort" and item.get("value"):
                effort = str(item["value"])
                break
    mapped = {
        "SessionStart": {},
        "Stop": {"transcript_path": payload.get("transcript_path") or ""},
        "PreCompact": {"transcript_path": payload.get("transcript_path") or ""},
        "PostToolUse": {
            "tool_name": payload.get("tool_name") or "tool",
            "tool_response": payload.get("tool_output", payload.get("tool_response", "")),
        },
        "SubagentStart": {
            "role": payload.get("subagent_type") or tool_input.get("subagent_type") or "default",
            "model": payload.get("subagent_model") or tool_input.get("model") or "inherit",
            "effort": effort,
            "task": payload.get("task") or tool_input.get("description") or "agent",
        },
    }
    return {
        "event": portable,
        "agent": "cursor",
        "session_id": session_id,
        "project": project,
        "payload": mapped[portable],
    }


def format_output(event_name: str, result: dict) -> str:
    portable = portable_event(event_name)
    if portable == "SessionStart":
        document = {"additional_context": result.get("additionalContext", "")}
        from kingstack.checkout import try_discover_checkout
        from kingstack.profile import hook_environment
        env = dict(hook_environment())
        root = try_discover_checkout()
        if root is not None:
            env.setdefault("KINGSTACK_ROOT", str(root))
        if env:
            document["env"] = env
    elif portable == "PreCompact":
        document = {}
        if result.get("additionalContext"):
            document["user_message"] = result["additionalContext"]
    elif portable == "PostToolUse":
        context = result.get("additionalContext") or result.get("systemMessage")
        document = {"additional_context": context} if context else {}
    else:
        document = {}
    return json.dumps(document, separators=(",", ":"))


def run_event(event_name: str, raw: str, runtime) -> tuple:
    runtime = Path(runtime)
    if portable_event(event_name) == "Stop":
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
