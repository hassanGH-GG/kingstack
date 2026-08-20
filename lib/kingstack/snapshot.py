"""Private, lossless snapshots of the safe Claude and Codex configuration subset."""

import hashlib
import json
import os
import re
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from kingstack.inventory import CLAUDE_INCLUDE, CODEX_INCLUDE
from kingstack.paths import Paths


SNAPSHOT_VERSION = 1
_DENYLISTED_NAMES = {
    ".claude.json", "auth.json", "credentials", "credential", "keychain",
    "keychains", "session", "sessions", "cache", "caches", "browser",
    "browsers", "transcript", "transcripts",
}
_DENYLISTED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".jsonl"}
_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}$")


def create_snapshot(paths: Paths, destination: Path, label: str) -> Path:
    """Copy the approved configuration subset to a new private snapshot directory."""
    if not _LABEL_PATTERN.fullmatch(label):
        raise ValueError("snapshot label must be 1-80 safe characters")
    selected = _selected_sources(paths)
    destination = Path(destination).expanduser()
    _mkdir_private(destination)
    snapshot_dir = _new_snapshot_directory(destination)
    _mkdir_private(snapshot_dir)
    files_dir = snapshot_dir / "files"
    _mkdir_private(files_dir)

    manifest_files = []
    for namespace, root, source in selected:
        relative = source.relative_to(root)
        snapshot_relative = Path(namespace) / relative
        stored = files_dir / snapshot_relative
        _mkdir_private(stored.parent)
        details = source.lstat()
        path_text = snapshot_relative.as_posix()
        if stat.S_ISLNK(details.st_mode):
            target = os.readlink(source)
            os.symlink(target, stored)
            manifest_files.append({
                "path": path_text,
                "kind": "symlink",
                "sha256": None,
                "mode": format(stat.S_IMODE(details.st_mode), "04o"),
                "target": target,
            })
            continue
        if not stat.S_ISREG(details.st_mode):
            raise ValueError("refusing non-regular snapshot source: " + str(source))
        shutil.copy2(source, stored, follow_symlinks=False)
        mode = 0o700 if details.st_mode & stat.S_IXUSR else 0o600
        stored.chmod(mode)
        manifest_files.append({
            "path": path_text,
            "kind": "file",
            "sha256": _hash_file(stored),
            "mode": format(mode, "04o"),
            "target": None,
        })

    manifest = {
        "version": SNAPSHOT_VERSION,
        "label": label,
        "files": manifest_files,
    }
    manifest_path = snapshot_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_path.chmod(0o600)
    return snapshot_dir


def verify_snapshot(snapshot_dir: Path, check_permissions: bool = False) -> List[str]:
    """Return integrity and, optionally, private-permission failures for a snapshot."""
    snapshot_dir = Path(snapshot_dir)
    problems = []
    try:
        manifest = _load_manifest(snapshot_dir)
    except ValueError as error:
        return [str(error)]
    if check_permissions:
        problems.extend(_permission_problems(snapshot_dir))
    for record in manifest["files"]:
        try:
            stored = _stored_path(snapshot_dir, record["path"])
        except ValueError as error:
            problems.append(str(error))
            continue
        if not os.path.lexists(stored):
            problems.append("missing snapshot entry: " + record["path"])
            continue
        details = stored.lstat()
        if record["kind"] == "file":
            if not stat.S_ISREG(details.st_mode):
                problems.append("wrong kind for snapshot entry: " + record["path"])
                continue
            if _hash_file(stored) != record["sha256"]:
                problems.append("hash mismatch: " + record["path"])
            if check_permissions and stat.S_IMODE(details.st_mode) != int(record["mode"], 8):
                problems.append("permission mismatch: " + record["path"])
        elif record["kind"] == "symlink":
            if not stat.S_ISLNK(details.st_mode):
                problems.append("wrong kind for snapshot entry: " + record["path"])
            elif os.readlink(stored) != record["target"]:
                problems.append("symlink target mismatch: " + record["path"])
    return problems


def restore_snapshot(
    snapshot_dir: Path,
    destination_home: Path,
    dry_run: bool = True,
    expected_current_hash: Optional[str] = None,
) -> List[Path]:
    """Plan or apply a snapshot restore, guarding every existing destination entry."""
    snapshot_dir = Path(snapshot_dir)
    destination_home = Path(destination_home).expanduser()
    problems = verify_snapshot(snapshot_dir, check_permissions=True)
    if problems:
        raise ValueError("refusing invalid snapshot: " + "; ".join(problems))
    manifest = _load_manifest(snapshot_dir)
    planned = [destination_home / _destination_relative(record["path"]) for record in manifest["files"]]
    existing = [path for path in planned if os.path.lexists(path)]
    if dry_run:
        return planned
    if existing:
        if not expected_current_hash:
            raise ValueError("refusing live overwrite without expected current hash")
        actual = current_destination_hash(snapshot_dir, destination_home)
        if actual != expected_current_hash:
            raise ValueError("refusing live overwrite: expected current hash does not match")
    for record, target in zip(manifest["files"], planned):
        _mkdir_restore_parent(destination_home, target)
        if os.path.lexists(target):
            if target.is_dir() and not target.is_symlink():
                raise ValueError("refusing to replace destination directory: " + str(target))
            target.unlink()
        source = _stored_path(snapshot_dir, record["path"])
        if record["kind"] == "symlink":
            os.symlink(record["target"], target)
        else:
            shutil.copy2(source, target, follow_symlinks=False)
            target.chmod(int(record["mode"], 8))
    return planned


def current_destination_hash(snapshot_dir: Path, destination_home: Path) -> str:
    """Hash the live state that a restore would replace, for an explicit precondition."""
    manifest = _load_manifest(Path(snapshot_dir))
    destination_home = Path(destination_home).expanduser()
    state = []
    for record in manifest["files"]:
        target = destination_home / _destination_relative(record["path"])
        if not os.path.lexists(target):
            state.append({"path": record["path"], "kind": "missing"})
        elif target.is_symlink():
            state.append({"path": record["path"], "kind": "symlink", "target": os.readlink(target)})
        elif target.is_file():
            state.append({"path": record["path"], "kind": "file", "sha256": _hash_file(target)})
        else:
            state.append({"path": record["path"], "kind": "other"})
    encoded = json.dumps(state, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _selected_sources(paths: Paths) -> List[Tuple[str, Path, Path]]:
    selected = []
    for namespace, root, include in (
        ("claude", paths.claude_home, CLAUDE_INCLUDE),
        ("codex", paths.codex_home, CODEX_INCLUDE),
    ):
        selected.extend((namespace, root, source) for source in _walk_selected(root, include))
    return sorted(selected, key=lambda item: (item[0], item[2].as_posix()))


def _walk_selected(root: Path, include: Iterable[str]) -> List[Path]:
    if not root.is_dir():
        return []
    found = set()
    for pattern in include:
        for match in root.glob(pattern):
            _assert_safe_source(root, match)
            details = match.lstat()
            if stat.S_ISLNK(details.st_mode) or stat.S_ISREG(details.st_mode):
                found.add(match)
            elif stat.S_ISDIR(details.st_mode):
                for directory, directories, filenames in os.walk(match, topdown=True, followlinks=False):
                    current = Path(directory)
                    for name in list(directories):
                        child = current / name
                        _assert_safe_source(root, child)
                        child_details = child.lstat()
                        if stat.S_ISLNK(child_details.st_mode):
                            found.add(child)
                            directories.remove(name)
                    for name in filenames:
                        child = current / name
                        _assert_safe_source(root, child)
                        found.add(child)
    return sorted(found, key=lambda path: path.as_posix())


def _assert_safe_source(root: Path, path: Path) -> None:
    try:
        parts = path.relative_to(root).parts
    except ValueError as error:
        raise ValueError("refusing source outside agent home") from error
    for part in parts:
        lowered = part.lower()
        if lowered in _DENYLISTED_NAMES or Path(lowered).stem in _DENYLISTED_NAMES:
            raise ValueError("refusing denylisted snapshot source: " + path.as_posix())
        if Path(lowered).suffix in _DENYLISTED_SUFFIXES:
            raise ValueError("refusing denylisted snapshot source: " + path.as_posix())


def _new_snapshot_directory(destination: Path) -> Path:
    prefix = "snapshot-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    candidate = destination / prefix
    number = 1
    while os.path.lexists(candidate):
        candidate = destination / (prefix + "-" + str(number))
        number += 1
    return candidate


def _load_manifest(snapshot_dir: Path) -> Dict[str, object]:
    manifest_path = snapshot_dir / "manifest.json"
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid snapshot manifest") from error
    if not isinstance(value, dict) or value.get("version") != SNAPSHOT_VERSION:
        raise ValueError("unsupported snapshot manifest")
    records = value.get("files")
    if not isinstance(records, list):
        raise ValueError("invalid snapshot manifest files")
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid snapshot manifest record")
        path = record.get("path")
        if not isinstance(path, str):
            raise ValueError("invalid snapshot manifest path")
        _destination_relative(path)
        if record.get("kind") not in {"file", "symlink"}:
            raise ValueError("invalid snapshot manifest kind")
        if record["kind"] == "file":
            if not isinstance(record.get("sha256"), str) or not isinstance(record.get("mode"), str):
                raise ValueError("invalid snapshot manifest file")
        elif not isinstance(record.get("target"), str):
            raise ValueError("invalid snapshot manifest symlink")
    return value


def _destination_relative(path_text: str) -> Path:
    relative = Path(path_text)
    if relative.is_absolute() or len(relative.parts) < 2 or relative.parts[0] not in {"claude", "codex"}:
        raise ValueError("invalid snapshot manifest path")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("invalid snapshot manifest path")
    return Path("." + relative.parts[0]) / Path(*relative.parts[1:])


def _stored_path(snapshot_dir: Path, path_text: str) -> Path:
    return snapshot_dir / "files" / Path(path_text)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mkdir_private(path: Path) -> None:
    missing = []
    current = path
    while not os.path.lexists(current):
        missing.append(current)
        current = current.parent
    path.mkdir(parents=True, exist_ok=True)
    for directory in reversed(missing):
        directory.chmod(0o700)
    path.chmod(0o700)


def _mkdir_restore_parent(destination_home: Path, target: Path) -> None:
    if os.path.lexists(destination_home):
        if destination_home.is_symlink() or not destination_home.is_dir():
            raise ValueError("refusing symlinked destination directory: " + str(destination_home))
    else:
        destination_home.mkdir(parents=True, exist_ok=True)
    relative = target.relative_to(destination_home)
    current = destination_home
    for part in relative.parts[:-1]:
        current = current / part
        if os.path.lexists(current):
            if current.is_symlink() or not current.is_dir():
                raise ValueError("refusing symlinked destination directory: " + str(current))
        else:
            current.mkdir()
        current.chmod(0o700)


def _permission_problems(snapshot_dir: Path) -> List[str]:
    problems = []
    for directory, directories, filenames in os.walk(snapshot_dir, topdown=True, followlinks=False):
        current = Path(directory)
        if stat.S_IMODE(current.lstat().st_mode) != 0o700:
            problems.append("private directory permission mismatch: " + str(current))
        for name in list(directories):
            child = current / name
            if child.is_symlink():
                directories.remove(name)
        for name in filenames:
            path = current / name
            if path.is_symlink():
                continue
            if stat.S_IMODE(path.lstat().st_mode) & 0o077:
                problems.append("private file permission mismatch: " + str(path))
    return problems
