"""Single-run schedule locks. A second owner exits without work."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional


class ScheduleLockError(ValueError):
    """Raised when a schedule lock cannot be claimed."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lock_dir(root: Optional[Path] = None) -> Path:
    base = Path(root) if root is not None else Path.home() / ".kingstack"
    return base / "manifests" / "schedules"


def claim(schedule_id: str, owner: str, root: Optional[Path] = None) -> Mapping[str, object]:
    directory = lock_dir(root)
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    path = directory / "{}.lock".format(schedule_id)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        pid = existing.get("pid")
        if isinstance(pid, int):
            try:
                os.kill(pid, 0)
            except OSError:
                pass
            else:
                raise ScheduleLockError("duplicate prevented")
    record = {"id": schedule_id, "owner": owner, "pid": os.getpid(), "started": _now()}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return record


def complete(schedule_id: str, exit_code: int, root: Optional[Path] = None) -> Mapping[str, object]:
    path = lock_dir(root) / "{}.lock".format(schedule_id)
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"id": schedule_id}
    record["completed"] = _now()
    record["exit"] = exit_code
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record
