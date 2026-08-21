"""Private shared memory store with mkdir locks and atomic JSONL appends."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Mapping, Optional

from kingstack.project_id import ProjectIdentity


class MemoryStoreError(ValueError):
    """Raised when the shared memory store cannot be used safely."""


SCHEMA = 1


@dataclass
class MemoryStore:
    root: Path

    @classmethod
    def open(cls, root: Path, repo_root: Optional[Path] = None) -> "MemoryStore":
        root = Path(root).expanduser()
        if repo_root is not None:
            repo = Path(os.path.realpath(str(repo_root)))
            resolved = Path(os.path.realpath(str(root)))
            if resolved == repo or str(resolved).startswith(str(repo) + os.sep):
                raise MemoryStoreError("memory root may not live inside the public repository")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        (root / "projects").mkdir(mode=0o700, exist_ok=True)
        for name in ("projects.json", "inbox.jsonl", "reviews.jsonl"):
            path = root / name
            if not path.exists():
                _atomic_write(path, b"{}\n" if name.endswith(".json") else b"")
            os.chmod(path, 0o600)
        store = cls(root)
        store._require_schema()
        return store

    def _require_schema(self) -> None:
        registry = self._read_json("projects.json")
        if registry and registry.get("schema_version") not in (None, SCHEMA):
            raise MemoryStoreError("unsupported memory schema")

    def register_project(self, identity: ProjectIdentity) -> ProjectIdentity:
        with _lock(self.root):
            registry = self._read_json("projects.json") or {"schema_version": SCHEMA, "projects": {}}
            projects = registry.setdefault("projects", {})
            projects[identity.id] = {
                "id": identity.id,
                "label": identity.label,
                "root": identity.root,
                "remote_fingerprint": identity.remote_fingerprint,
            }
            registry["schema_version"] = SCHEMA
            _atomic_write(self.root / "projects.json", json.dumps(registry, indent=2, sort_keys=True).encode() + b"\n")
            bank = self.root / "projects" / identity.id
            (bank / "memories").mkdir(mode=0o700, parents=True, exist_ok=True)
            if not (bank / "MEMORY.md").exists():
                _atomic_write(bank / "MEMORY.md", b"# Memory Index\n\n")
            if not (bank / "manifest.json").exists():
                _atomic_write(
                    bank / "manifest.json",
                    json.dumps({"schema_version": SCHEMA, "project_id": identity.id, "files": []}, indent=2).encode() + b"\n",
                )
            for path in bank.rglob("*"):
                os.chmod(path, 0o700 if path.is_dir() else 0o600)
        return identity

    def bank(self, project: str) -> Path:
        path = self.root / "projects" / project
        if not path.is_dir():
            raise MemoryStoreError("unknown project bank '{}'".format(project))
        return path

    def append_candidate(self, candidate: Mapping[str, Any]) -> Mapping[str, Any]:
        if candidate.get("schema") != SCHEMA:
            raise MemoryStoreError("candidate schema must be 1")
        with _lock(self.root):
            existing = [
                json.loads(line)
                for line in (self.root / "inbox.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if any(item.get("id") == candidate["id"] for item in existing):
                return candidate
            _atomic_append(self.root / "inbox.jsonl", json.dumps(candidate, sort_keys=True) + "\n")
        return candidate

    def review(self, candidate_id: str, verdict: str, actor: str, memory: Optional[Mapping[str, Any]] = None) -> Mapping[str, Any]:
        event = {
            "schema": SCHEMA,
            "candidate_id": candidate_id,
            "verdict": verdict,
            "actor": actor,
            "memory": memory or {},
        }
        with _lock(self.root):
            _atomic_append(self.root / "reviews.jsonl", json.dumps(event, sort_keys=True) + "\n")
        return event

    def _read_json(self, name: str) -> Any:
        text = (self.root / name).read_text(encoding="utf-8").strip()
        if not text:
            return {}
        return json.loads(text)


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
                    raise MemoryStoreError("memory store lock is busy")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb):
        try:
            for child in self.path.iterdir():
                child.unlink()
            self.path.rmdir()
        except OSError:
            pass
