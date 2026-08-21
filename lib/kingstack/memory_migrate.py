"""Copy-only migration of curated Claude banks into the private store."""

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any, Mapping

from kingstack.memory_store import MemoryStore, _atomic_write
from kingstack.project_id import project_identity


class MemoryMigrateError(ValueError):
    """Raised when a copy-only migration cannot complete safely."""


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_banks(claude_home: Path) -> Mapping[str, Any]:
    projects = claude_home / "projects"
    banks = []
    if projects.is_dir():
        for project in sorted(projects.iterdir()):
            memory = project / "memory"
            if not memory.is_dir():
                continue
            files = []
            unindexed = []
            index = (memory / "MEMORY.md").read_text(encoding="utf-8") if (memory / "MEMORY.md").is_file() else ""
            for path in sorted(memory.rglob("*")):
                if not path.is_file() or path.is_symlink():
                    continue
                relative = str(path.relative_to(memory))
                record = {
                    "path": relative,
                    "sha256": _hash_file(path),
                    "mtime_ns": path.stat().st_mtime_ns,
                    "mode": path.stat().st_mode & 0o777,
                }
                files.append(record)
                if relative != "MEMORY.md" and relative not in index:
                    unindexed.append(relative)
            banks.append(
                {
                    "source": str(memory),
                    "project": project.name,
                    "files": files,
                    "unindexed_files": unindexed,
                }
            )
    return {"schema_version": 1, "banks": banks, "count": len(banks)}


def migrate_claude(claude_home: Path, store: MemoryStore, apply: bool = False) -> Mapping[str, Any]:
    report = inventory_banks(claude_home)
    if not apply:
        return report
    for bank in report["banks"]:
        identity = project_identity(Path(bank["source"]).parent)
        store.register_project(identity)
        destination = store.bank(identity.id)
        staging = destination.with_name(destination.name + ".staging")
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(bank["source"], staging, copy_function=shutil.copy2, symlinks=False)
        for path in staging.rglob("*"):
            os.chmod(path, 0o700 if path.is_dir() else 0o600)
        manifest = {
            "schema_version": 1,
            "project_id": identity.id,
            "source": bank["source"],
            "files": bank["files"],
        }
        _atomic_write(staging / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n")
        if destination.exists():
            shutil.rmtree(destination)
        os.rename(staging, destination)
    return report
