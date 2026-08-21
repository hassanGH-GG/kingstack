"""Private working-set index. Pointers, not transcripts."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, List, Mapping, Optional

from kingstack.project_id import ProjectIdError, project_id


SCHEMA = 1
WINDOW = 20
PROMPT_CAP = 6
STATUSES = ("live", "compacted", "handed-off", "done")


class SessionStoreError(ValueError):
    """Raised when the session index cannot be used safely."""


def record_id(adapter: str, session_id: str) -> str:
    material = "{}:{}".format(adapter.strip(), session_id.strip())
    return "s_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def default_root() -> Path:
    override = os.environ.get("KINGSTACK_SESSIONS_ROOT")
    if override:
        return Path(override)
    return Path.home() / ".kingstack" / "sessions"


def parse_patch(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise SessionStoreError("session patch must be an object")
    adapter = str(raw.get("adapter") or "").strip()
    session = str(raw.get("session_id") or "").strip()
    project = str(raw.get("project_id") or "").strip()
    if not adapter or not session or not project:
        raise SessionStoreError("adapter, session_id, and project_id are required")
    patch = {
        "schema": SCHEMA,
        "id": record_id(adapter, session),
        "adapter": adapter,
        "session_id": session,
        "project_id": project,
    }
    if "status" in raw:
        status = raw["status"]
        if status not in STATUSES:
            raise SessionStoreError(
                "status must be live, compacted, handed-off, or done"
            )
        patch["status"] = status
    if "transcript_path" in raw:
        patch["transcript_path"] = str(raw.get("transcript_path") or "")
    if "last_prompts" in raw:
        prompts = raw["last_prompts"]
        if not isinstance(prompts, list):
            raise SessionStoreError("last_prompts must be a list")
        patch["last_prompts"] = [str(item)[:200] for item in prompts][-PROMPT_CAP:]
    if "finish_condition" in raw:
        patch["finish_condition"] = str(raw.get("finish_condition") or "")
    if "headroom_ids" in raw:
        ids = raw["headroom_ids"]
        if not isinstance(ids, list):
            raise SessionStoreError("headroom_ids must be a list")
        patch["headroom_ids"] = [str(item) for item in ids]
    if "memory_names" in raw:
        names = raw["memory_names"]
        if not isinstance(names, list):
            raise SessionStoreError("memory_names must be a list")
        patch["memory_names"] = [str(item) for item in names]
    if "packet_path" in raw:
        patch["packet_path"] = str(raw.get("packet_path") or "")
    if "checkpoint_path" in raw:
        patch["checkpoint_path"] = str(raw.get("checkpoint_path") or "")
    return patch


def _blank() -> Mapping[str, Any]:
    return {
        "schema": SCHEMA,
        "id": "",
        "adapter": "",
        "session_id": "",
        "project_id": "",
        "status": "live",
        "transcript_path": "",
        "last_prompts": [],
        "finish_condition": "",
        "headroom_ids": [],
        "memory_names": [],
        "packet_path": "",
        "checkpoint_path": "",
        "started_at": "",
        "updated_at": "",
    }


def assemble(previous: Mapping[str, Any], patch: Mapping[str, Any]) -> Mapping[str, Any]:
    record = dict(_blank())
    record.update(previous)
    record.update(patch)
    record["schema"] = SCHEMA
    record["id"] = patch["id"]
    if record["status"] not in STATUSES:
        record["status"] = "live"
    return record


def merge_record(previous: Mapping[str, Any], patch: Mapping[str, Any]) -> Mapping[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = assemble(previous, patch)
    record["started_at"] = previous.get("started_at") or now
    record["updated_at"] = now
    return record


@dataclass
class SessionStore:
    root: Path

    @classmethod
    def open(cls, root: Path, repo_root: Optional[Path] = None) -> "SessionStore":
        root = Path(root).expanduser()
        if repo_root is not None:
            repo = Path(os.path.realpath(str(repo_root)))
            resolved = Path(os.path.realpath(str(root)))
            if resolved == repo or str(resolved).startswith(str(repo) + os.sep):
                raise SessionStoreError(
                    "session root may not live inside the public repository"
                )
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        (root / "projects").mkdir(mode=0o700, exist_ok=True)
        meta = root / "store.json"
        if meta.exists():
            payload = json.loads(meta.read_text(encoding="utf-8") or "{}")
            if payload.get("schema_version") not in (None, SCHEMA):
                raise SessionStoreError("unsupported session schema")
        else:
            _atomic_write(
                meta,
                json.dumps({"schema_version": SCHEMA}, indent=2, sort_keys=True).encode()
                + b"\n",
            )
        journal = root / "sessions.jsonl"
        if not journal.exists():
            _atomic_write(journal, b"")
        os.chmod(journal, 0o600)
        return cls(root)

    def upsert(self, patch: Mapping[str, Any]) -> Mapping[str, Any]:
        parsed = parse_patch(patch)
        with _lock(self.root):
            folded = self._fold()
            previous = folded.get(parsed["id"], {})
            record = merge_record(previous, parsed)
            _atomic_append(
                self.root / "sessions.jsonl",
                json.dumps(record, sort_keys=True) + "\n",
            )
            folded[record["id"]] = record
            self._write_current(record["project_id"], folded)
        return record

    def current(self, project: str) -> List[Mapping[str, Any]]:
        path = self.root / "projects" / project / "current.json"
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return []
        if payload.get("schema") not in (None, SCHEMA):
            return []
        rows = payload.get("records") or []
        return [row for row in rows if isinstance(row, Mapping)]

    def list_records(self, project: Optional[str] = None) -> List[Mapping[str, Any]]:
        with _lock(self.root):
            rows = list(self._fold().values())
        rows.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        if project:
            rows = [row for row in rows if row.get("project_id") == project]
        return rows

    def show(self, key: str) -> Mapping[str, Any]:
        rows = self.list_records()
        for row in rows:
            if row.get("id") == key or row.get("session_id") == key:
                return row
        raise SessionStoreError("unknown session '{}'".format(key))

    def close_record(self, key: str) -> Mapping[str, Any]:
        previous = self.show(key)
        return self.upsert(
            {
                "adapter": previous["adapter"],
                "session_id": previous["session_id"],
                "project_id": previous["project_id"],
                "status": "done",
            }
        )

    def sweep_empty(self) -> List[Mapping[str, Any]]:
        closed = []
        for row in self.list_records():
            if row.get("status") != "live":
                continue
            if row.get("transcript_path"):
                continue
            if row.get("last_prompts"):
                continue
            if row.get("finish_condition"):
                continue
            closed.append(self.close_record(row["id"]))
        return closed

    def _fold(self) -> Mapping[str, Mapping[str, Any]]:
        folded = {}
        text = (self.root / "sessions.jsonl").read_text(encoding="utf-8")
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except ValueError:
                continue
            if raw.get("schema") != SCHEMA:
                continue
            try:
                parsed = parse_patch(raw)
            except SessionStoreError:
                continue
            record = assemble(raw, parsed)
            record["started_at"] = raw.get("started_at") or record.get("started_at")
            record["updated_at"] = raw.get("updated_at") or record.get("updated_at")
            folded[parsed["id"]] = record
        return folded

    def _write_current(self, project: str, folded: Mapping[str, Mapping[str, Any]]) -> None:
        rows = [
            row
            for row in folded.values()
            if row.get("project_id") == project
            and row.get("status") in ("live", "compacted", "handed-off")
        ]
        rows.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        payload = {
            "schema": SCHEMA,
            "project_id": project,
            "records": rows[:WINDOW],
        }
        path = self.root / "projects" / project / "current.json"
        _atomic_write(
            path,
            json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n",
        )


def record_from_hook(
    event: Mapping[str, Any],
    status: Optional[str] = None,
    transcript: str = "",
    checkpoint: str = "",
    finish: str = "",
    packet: str = "",
) -> Optional[Mapping[str, Any]]:
    root = os.environ.get("KINGSTACK_SESSIONS_ROOT")
    if not root:
        return None
    project = event.get("project") or ""
    try:
        identity = project_id(Path(project))
    except (OSError, ProjectIdError):
        return None
    adapter = str(event.get("agent") or "").strip()
    session = str(event.get("session_id") or "").strip()
    if not adapter or not session:
        return None
    patch = {
        "adapter": adapter,
        "session_id": session,
        "project_id": identity,
    }
    try:
        store = SessionStore.open(Path(root))
    except (SessionStoreError, OSError):
        return None
    try:
        previous = store.show(record_id(adapter, session))
    except SessionStoreError:
        previous = None
    if (
        previous
        and previous.get("status") == "done"
        and status == "live"
        and not transcript
    ):
        return previous
    if status:
        patch["status"] = status
    if transcript:
        patch["transcript_path"] = transcript
        if os.path.exists(transcript):
            from kingstack.hooks.inbox import human_prompts, one_line
            from kingstack.secret_filter import inspect
            patch["last_prompts"] = [
                one_line(text)
                for text in human_prompts(transcript)[-PROMPT_CAP:]
                if not inspect(text)
            ]
    store_path = os.environ.get("KINGSTACK_HEADROOM_ROOT")
    if store_path:
        from kingstack.headroom import live_ids
        patch["headroom_ids"] = live_ids(Path(store_path))
    memory_root = os.environ.get("KINGSTACK_MEMORY_ROOT")
    if memory_root:
        patch["memory_names"] = _memory_names(Path(memory_root), Path(project))
    if checkpoint:
        patch["checkpoint_path"] = checkpoint
    if finish:
        patch["finish_condition"] = finish
    if packet:
        patch["packet_path"] = packet
    try:
        opened = store if store is not None else SessionStore.open(Path(root))
        return opened.upsert(patch)
    except Exception:
        return None


def mark_handoff(
    cwd: Path,
    finish: str,
    packet_path: str = "",
    session_key: Optional[str] = None,
    root: Optional[Path] = None,
) -> Optional[Mapping[str, Any]]:
    explicit = root is not None
    store_root = Path(root) if explicit else default_root()
    if (
        not explicit
        and not store_root.exists()
        and not os.environ.get("KINGSTACK_SESSIONS_ROOT")
    ):
        return None
    from kingstack.project_id import project_identity
    store = SessionStore.open(store_root)
    identity = project_identity(Path(cwd))
    if session_key:
        previous = store.show(session_key)
    else:
        live = [
            row
            for row in store.current(identity.id)
            if row.get("status") in ("live", "compacted")
        ]
        if not live:
            return None
        previous = live[0]
    patch = {
        "adapter": previous["adapter"],
        "session_id": previous["session_id"],
        "project_id": identity.id,
        "status": "handed-off",
        "finish_condition": finish,
    }
    if packet_path:
        patch["packet_path"] = packet_path
    return store.upsert(patch)


def _memory_names(memory_root: Path, cwd: Path) -> List[str]:
    try:
        from kingstack.memory_store import MemoryStore
        from kingstack.project_id import project_identity
        bank = MemoryStore.open(memory_root).bank(project_identity(cwd).id)
        index = (bank / "MEMORY.md").read_text(encoding="utf-8")
        return [
            line.split("]")[0][2:]
            for line in index.splitlines()
            if line.startswith("- [")
        ]
    except Exception:
        return []


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _atomic_append(path: Path, line: str) -> None:
    current = path.read_bytes() if path.exists() else b""
    _atomic_write(path, current + line.encode("utf-8"))


def _lock(root: Path):
    return _MkdirLock(root / ".lock")


class _MkdirLock:
    def __init__(self, path: Path):
        self.path = path

    def __enter__(self):
        deadline = time.time() + 5
        while True:
            try:
                os.mkdir(self.path)
                (self.path / "owner").write_text(
                    json.dumps({"pid": os.getpid(), "ts": time.time()}),
                    encoding="utf-8",
                )
                return self
            except FileExistsError:
                if time.time() > deadline:
                    raise SessionStoreError("session store lock is busy")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb):
        try:
            for child in self.path.iterdir():
                child.unlink()
            self.path.rmdir()
        except OSError:
            pass
