"""Owned-key JSON merge with inverse restore."""

import json
from typing import Any, Mapping, Tuple


class JsonPatchError(ValueError):
    """Raised when an owned JSON key conflicts."""


def _get(data: Any, dotted: str):
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set(data: dict, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    current = data
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def _delete(data: dict, dotted: str) -> None:
    parts = dotted.split(".")
    current = data
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def merge_json(original: str, owned: Mapping[str, Any]) -> Tuple[str, Mapping[str, Any]]:
    data = json.loads(original) if original.strip() else {}
    if not isinstance(data, dict):
        raise JsonPatchError("settings root must be an object")
    snapshot = {}
    for key, value in owned.items():
        current = _get(data, key)
        snapshot[key] = current
        if current is not None and current != value:
            raise JsonPatchError("conflicting owned key {}".format(key))
        _set(data, key, value)
    return json.dumps(data, indent=2, sort_keys=True) + "\n", snapshot


def inverse_json(current: str, snapshot: Mapping[str, Any]) -> str:
    data = json.loads(current) if current.strip() else {}
    if not isinstance(data, dict):
        raise JsonPatchError("settings root must be an object")
    for key, old in snapshot.items():
        if old is None:
            _delete(data, key)
        else:
            _set(data, key, old)
    return json.dumps(data, indent=2, sort_keys=True) + "\n"
