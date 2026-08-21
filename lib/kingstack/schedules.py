"""Single-owner schedule declarations. No live install."""

import json
from pathlib import Path
from typing import Any, Mapping


class ScheduleError(ValueError):
    """Raised when schedule ownership or schema is invalid."""


REQUIRED = (
    "id", "surface", "owner", "cadence", "command", "output", "idempotency_key", "enabled",
)


def load_schedules(root: Path) -> Mapping[str, Any]:
    payload = json.loads((Path(root) / "core/schedules/schedules.json").read_text(encoding="utf-8"))
    validate_schedules(payload)
    return payload


def validate_schedules(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ScheduleError("schedule schema must be 1")
    seen = {}
    for item in payload.get("schedules", []):
        missing = [key for key in REQUIRED if key not in item]
        if missing:
            raise ScheduleError("schedule missing {}".format(",".join(missing)))
        if item["surface"] not in ("local", "adapter", "cloud"):
            raise ScheduleError("unknown surface")
        if item["surface"] == "local" and item.get("model_tier"):
            raise ScheduleError("local work cannot declare a model")
        if item["surface"] == "adapter" and not item.get("adapter_id"):
            raise ScheduleError("adapter surface requires adapter_id")
        key = item["id"]
        if item.get("enabled") and key in seen:
            raise ScheduleError("duplicate enabled executor for {}".format(key))
        if item.get("enabled"):
            seen[key] = item["owner"]
