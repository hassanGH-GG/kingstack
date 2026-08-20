"""Deterministic, secret-safe inventories of agent configuration files."""

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from kingstack.paths import Paths


CLAUDE_INCLUDE = [
    "settings.json", "hooks/", "scripts/", "agents/", "skills/", "launchd/",
    "sweeps/", "projects/*/memory/",
]
IGNORED_PARTS = {
    "auth", "session", "sessions", "cache", "caches", "history", "histories",
    "log", "logs", "download", "downloads", "browser", "browsers", "credential",
    "credentials", "transcript", "transcripts", "database", "databases", "backup",
    "backups",
}
CODEX_INCLUDE = [
    "config.toml", "AGENTS.md", "AGENTS.override.md", "hooks.json", "hooks/",
    "skills/", "plugins/*/plugin.json", "plugins/*/.codex-plugin/plugin.json",
]


@dataclass(frozen=True)
class FileRecord:
    path: str
    kind: str
    sha256: Optional[str]
    mode: str
    target: Optional[str]


def hash_file(path: Path) -> str:
    """Return the SHA-256 digest of a regular file without reading it as text."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(root: Path, path: Path) -> FileRecord:
    if _is_excluded_path(root, path):
        raise ValueError("refusing to inventory excluded path")
    details = path.lstat()
    relative = path.relative_to(root).as_posix()
    mode = format(stat.S_IMODE(details.st_mode), "04o")
    if path.is_symlink():
        return FileRecord(relative, "symlink", None, mode, _safe_link_target(str(path.readlink())))
    return FileRecord(relative, "file", hash_file(path), mode, None)


def walk_records(root: Path, include: List[str]) -> List[FileRecord]:
    """List included regular files and symlinks under *root* in path order."""
    if not root.is_dir():
        return []
    found = set()
    for pattern in include:
        for match in root.glob(pattern):
            if _is_excluded_path(root, match):
                continue
            if match.is_symlink() or match.is_file():
                found.add(match)
            elif match.is_dir():
                for directory, directories, filenames in os.walk(match, topdown=True, followlinks=False):
                    current = Path(directory)
                    for name in list(directories):
                        child = current / name
                        if _is_excluded_path(root, child):
                            directories.remove(name)
                        elif child.is_symlink():
                            found.add(child)
                            directories.remove(name)
                    for name in filenames:
                        child = current / name
                        if not _is_excluded_path(root, child):
                            found.add(child)
    return [_record(root, path) for path in sorted(found, key=lambda item: item.as_posix())]


def _is_excluded_path(root: Path, path: Path) -> bool:
    """Match sensitive names from a relative path without inspecting its content."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    for part in parts:
        name = part.lower()
        stem = Path(name).stem
        if name in IGNORED_PARTS or stem in IGNORED_PARTS:
            return True
        if Path(name).suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            return True
    return False


def _tracked_include(root: Path) -> List[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files"], check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [
        line for line in result.stdout.splitlines()
        if line and not _is_excluded_path(root, root / line)
    ]


def _json_key_paths(path: Path) -> List[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    paths = []

    def visit(value: object, prefix: str) -> None:
        if isinstance(value, dict):
            for key in sorted(value):
                child_key = _safe_key_part(str(key))
                child = child_key if not prefix else prefix + "." + child_key
                visit(value[key], child)
        elif prefix:
            paths.append(prefix)

    visit(data, "")
    return paths


def _toml_key_paths(path: Path) -> List[str]:
    """Extract TOML keys without parsing or retaining their scalar values."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    table: Tuple[str, ...] = ()
    keys = []
    table_pattern = re.compile(r"^\s*\[\[?([^\]]+)\]?\]\s*(?:#.*)?$")
    key_pattern = re.compile(r"^\s*([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)\s*=")
    for line in lines:
        table_match = table_pattern.match(line)
        if table_match:
            table = tuple(_safe_key_part(part.strip()) for part in table_match.group(1).split("."))
            continue
        key_match = key_pattern.match(line)
        if key_match:
            keys.append(".".join(table + tuple(_safe_key_part(part) for part in key_match.group(1).split("."))))
    return sorted(keys)


def _safe_key_part(part: str) -> str:
    """Keep configuration structure while removing path-shaped key segments."""
    return "<redacted>" if "/" in part or "\\" in part else part


def _safe_link_target(target: str) -> str:
    """Redact absolute link targets while retaining safe relative link structure."""
    if target.startswith(("/", "\\", "~")) or re.match(r"^[A-Za-z]:[\\/]", target):
        return "<redacted>"
    return target


def _records_dict(records: List[FileRecord]) -> List[dict]:
    return [asdict(record) for record in records]


def capture_baseline(paths: Paths) -> dict:
    """Capture a relative, redacted baseline for the two supported agent homes."""
    claude_records = walk_records(
        paths.claude_home, sorted(set(CLAUDE_INCLUDE + _tracked_include(paths.claude_home)))
    )
    codex_records = walk_records(paths.codex_home, CODEX_INCLUDE)
    memory_banks = list(paths.claude_home.glob("projects/*/memory"))
    return {
        "claude": {
            "config_keys": _json_key_paths(paths.claude_home / "settings.json"),
            "records": _records_dict(claude_records),
        },
        "codex": {
            "config_keys": _toml_key_paths(paths.codex_home / "config.toml"),
            "records": _records_dict(codex_records),
        },
        "counts": {
            "claude_records": len(claude_records),
            "codex_records": len(codex_records),
            "memory_banks": len(memory_banks),
        },
        "version": 1,
    }


def _is_private_destination(destination: Path) -> bool:
    resolved = destination.expanduser().resolve()
    return any(part in {".claude", ".codex", "memory"} for part in resolved.parts)


def write_public_report(baseline: dict, destination: Path) -> None:
    """Write canonical JSON, refusing agent homes and memory-bank destinations."""
    destination = Path(destination).expanduser()
    if _is_private_destination(destination):
        raise ValueError("refusing to write a public report inside agent-private storage")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
