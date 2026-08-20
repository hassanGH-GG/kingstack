"""Private, verified snapshots of the safe Claude and Codex configuration subset."""

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from kingstack.inventory import CLAUDE_INCLUDE, CODEX_INCLUDE
from kingstack.paths import Paths


SNAPSHOT_VERSION = 2
_ID_PATTERN = re.compile(r"^snapshot-[0-9]{8}-[0-9]{6}$")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}$")
_DENYLISTED_NAMES = {".claude.json", "auth.json", "credentials", "credential", "keychain", "keychains", "session", "sessions", "cache", "caches", "browser", "browsers", "transcript", "transcripts"}
_DENYLISTED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".jsonl"}
_JOURNAL_NAME = ".kingstack-restore-journal.json"


def create_snapshot(paths: Paths, destination: Path, label: str) -> Path:
    """Create a new private snapshot without reusing an existing filesystem entry."""
    if not _LABEL_PATTERN.fullmatch(label):
        raise ValueError("snapshot label must be 1-80 safe characters")
    selected = _selected_sources(paths)
    destination = Path(destination).expanduser()
    _mkdir_private(destination)
    snapshot_dir = destination / ("snapshot-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S"))
    _assert_no_symlink_ancestors(snapshot_dir)
    try:
        os.mkdir(snapshot_dir, 0o700)
    except FileExistsError as error:
        raise ValueError("snapshot directory already exists") from error
    files_dir = snapshot_dir / "files"
    _mkdir_private(files_dir)
    records = []
    for namespace, root, source in selected:
        path_text = (Path(namespace) / source.relative_to(root)).as_posix()
        _assert_safe_manifest_path(path_text)
        stored = files_dir / path_text
        _mkdir_private(stored.parent)
        details = source.lstat()
        if stat.S_ISLNK(details.st_mode):
            target = os.readlink(source)
            os.symlink(target, stored)
            records.append({"path": path_text, "kind": "symlink", "sha256": None, "mode": None, "target": target})
            continue
        if not stat.S_ISREG(details.st_mode):
            raise ValueError("refusing non-regular snapshot source: " + str(source))
        before = (details.st_dev, details.st_ino, details.st_mtime_ns, details.st_size)
        shutil.copy2(source, stored, follow_symlinks=False)
        after = source.lstat()
        if (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size) != before:
            raise ValueError("source changed while creating snapshot: " + str(source))
        if not stat.S_ISREG(stored.lstat().st_mode):
            raise ValueError("refusing raced snapshot source: " + str(source))
        mode = 0o700 if details.st_mode & stat.S_IXUSR else 0o600
        stored.chmod(mode)
        records.append({"path": path_text, "kind": "file", "sha256": _hash_file(stored), "mode": format(mode, "04o"), "target": None})
    manifest_path = snapshot_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"version": SNAPSHOT_VERSION, "label": label, "files": records}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.chmod(0o600)
    return snapshot_dir


def snapshot_path(storage: Path, identifier: str) -> Path:
    """Resolve a validated direct-child snapshot identifier inside its storage root."""
    if not _ID_PATTERN.fullmatch(identifier):
        raise ValueError("invalid snapshot identifier")
    storage = Path(storage).expanduser()
    _assert_no_symlink_ancestors(storage)
    if not storage.is_dir():
        raise ValueError("snapshot storage is not a directory")
    candidate = storage / identifier
    _assert_no_symlink_ancestors(candidate)
    if candidate.parent.resolve() != storage.resolve():
        raise ValueError("snapshot identifier escapes storage")
    return candidate


def verify_snapshot(snapshot_dir: Path, check_permissions: bool = False) -> List[str]:
    """Return every manifest, tree, integrity, and requested permission failure."""
    snapshot_dir = Path(snapshot_dir)
    try:
        manifest = _read_manifest(snapshot_dir)
    except ValueError as error:
        return [str(error)]
    problems = _manifest_problems(manifest)
    records = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    expected = _expected_tree(records)
    actual, tree_problems = _actual_tree(snapshot_dir)
    problems.extend(tree_problems)
    for relative, kind in actual.items():
        if expected.get(relative) != kind:
            problems.append("unexpected snapshot entry: " + relative)
    for relative, kind in expected.items():
        if actual.get(relative) != kind:
            problems.append("missing or wrong snapshot entry: " + relative)
    if check_permissions:
        problems.extend(_permission_problems(snapshot_dir, actual, expected, records))
    for record in records:
        if not _record_is_usable(record):
            continue
        stored = snapshot_dir / "files" / record["path"]
        if actual.get((Path("files") / record["path"]).as_posix()) != record["kind"]:
            continue
        if record["kind"] == "file" and _hash_file(stored) != record["sha256"]:
            problems.append("hash mismatch: " + record["path"])
        if record["kind"] == "symlink" and os.readlink(stored) != record["target"]:
            problems.append("symlink target mismatch: " + record["path"])
    return sorted(set(problems))


def restore_snapshot(snapshot_dir: Path, destination_home: Path, dry_run: bool = True, expected_current_hash: Optional[str] = None) -> List[Path]:
    """Plan or transactionally restore a verified snapshot into a separate home."""
    snapshot_dir = Path(snapshot_dir)
    destination_home = Path(destination_home).expanduser()
    _recover_transaction(destination_home)
    problems = verify_snapshot(snapshot_dir, check_permissions=True)
    if problems:
        raise ValueError("refusing invalid snapshot: " + "; ".join(problems))
    manifest = _read_manifest(snapshot_dir)
    records = manifest["files"]
    planned = [destination_home / _destination_relative(record["path"]) for record in records]
    if dry_run:
        return planned
    if not expected_current_hash:
        raise ValueError("refusing apply without expected current hash")
    if not _HASH_PATTERN.fullmatch(expected_current_hash):
        raise ValueError("invalid expected current hash")
    _preflight_destination(destination_home, planned)
    if current_destination_hash(snapshot_dir, destination_home) != expected_current_hash:
        raise ValueError("refusing live apply: expected current hash does not match")
    return _apply_transaction(snapshot_dir, destination_home, records, planned, expected_current_hash)


def current_destination_hash(snapshot_dir: Path, destination_home: Path) -> str:
    """Hash target and relevant parent state, including kinds, bytes, and modes."""
    manifest = _read_manifest(Path(snapshot_dir))
    destination_home = Path(destination_home).expanduser()
    paths, parents = [], set()
    for record in manifest["files"]:
        target = destination_home / _destination_relative(record["path"])
        paths.append((record["path"], target))
        current = target.parent
        while current != destination_home:
            parents.add(current)
            current = current.parent
    state = [{"role": "target", "path": name, "state": _describe(path)} for name, path in paths]
    state.extend({"role": "parent", "path": parent.relative_to(destination_home).as_posix(), "state": _describe(parent)} for parent in sorted(parents, key=lambda item: item.as_posix()))
    return hashlib.sha256(json.dumps(state, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()


def _apply_transaction(snapshot_dir: Path, destination: Path, records: List[dict], targets: List[Path], expected_hash: str) -> List[Path]:
    _ensure_destination_root(destination)
    token = uuid.uuid4().hex
    stage, backup = destination / (".kingstack-restore-stage-" + token), destination / (".kingstack-restore-backup-" + token)
    journal = destination / _JOURNAL_NAME
    _mkdir_private(stage)
    _mkdir_private(backup)
    parents, entries = _parent_paths(destination, targets), []
    try:
        for index, record in enumerate(records):
            staged, source = stage / str(index), snapshot_dir / "files" / record["path"]
            if record["kind"] == "symlink":
                os.symlink(record["target"], staged)
            else:
                shutil.copy2(source, staged, follow_symlinks=False)
                staged.chmod(int(record["mode"], 8))
            entries.append({"target": targets[index].relative_to(destination).as_posix(), "backup": str(index), "before": _describe(targets[index])})
        transaction = {"version": 1, "status": "prepared", "expected": expected_hash, "stage": stage.name, "backup": backup.name, "entries": entries, "parents": [{"path": path.relative_to(destination).as_posix(), "before": _describe(path)} for path in parents]}
        _write_journal(journal, transaction)
        _preflight_destination(destination, targets)
        if current_destination_hash(snapshot_dir, destination) != expected_hash:
            raise ValueError("destination changed before atomic rename")
        for parent in parents:
            _make_restore_parent(parent)
        for index, entry in enumerate(entries):
            target = destination / entry["target"]
            if _describe(target) != entry["before"]:
                raise ValueError("destination target changed before atomic rename")
            if entry["before"]["kind"] != "missing":
                os.replace(target, backup / entry["backup"])
            os.replace(stage / str(index), target)
        transaction["status"] = "committed"
        _write_journal(journal, transaction)
    except Exception:
        if journal.exists():
            _rollback_transaction(destination, _read_journal(journal))
        _cleanup_transaction(destination, stage, backup, journal)
        raise
    _cleanup_transaction(destination, stage, backup, journal)
    return targets


def _recover_transaction(destination: Path) -> None:
    journal = destination / _JOURNAL_NAME
    if not os.path.lexists(journal):
        return
    _assert_no_symlink_ancestors(journal)
    transaction = _read_journal(journal)
    if transaction.get("status") != "committed":
        _rollback_transaction(destination, transaction)
    _cleanup_transaction(destination, destination / transaction["stage"], destination / transaction["backup"], journal)


def _rollback_transaction(destination: Path, transaction: dict) -> None:
    backup = destination / transaction["backup"]
    for entry in reversed(transaction["entries"]):
        target, saved = destination / entry["target"], backup / entry["backup"]
        if entry["before"]["kind"] == "missing":
            if os.path.lexists(target):
                target.unlink()
        elif os.path.lexists(saved):
            os.replace(saved, target)
    for parent in reversed(transaction["parents"]):
        path, before = destination / parent["path"], parent["before"]
        if before["kind"] == "dir" and path.is_dir() and not path.is_symlink():
            path.chmod(int(before["mode"], 8))
        elif before["kind"] == "missing" and path.is_dir() and not path.is_symlink():
            try:
                path.rmdir()
            except OSError:
                pass


def _cleanup_transaction(destination: Path, stage: Path, backup: Path, journal: Path) -> None:
    for path in (stage, backup):
        if path.parent == destination and path.name.startswith(".kingstack-restore-") and path.exists():
            shutil.rmtree(path)
    if journal.parent == destination and journal.name == _JOURNAL_NAME and os.path.lexists(journal):
        journal.unlink()


def _write_journal(path: Path, transaction: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(transaction, sort_keys=True), encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def _read_journal(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid restore transaction journal") from error
    required = {"version", "status", "stage", "backup", "entries", "parents", "expected"}
    if not isinstance(value, dict) or not required.issubset(value) or value["version"] != 1 or not isinstance(value["entries"], list) or not isinstance(value["parents"], list):
        raise ValueError("invalid restore transaction journal")
    for name in (value["stage"], value["backup"]):
        if not isinstance(name, str) or not name.startswith(".kingstack-restore-") or "/" in name:
            raise ValueError("invalid restore transaction journal")
    return value


def _preflight_destination(destination: Path, targets: List[Path]) -> None:
    if os.path.lexists(destination) and (destination.is_symlink() or not destination.is_dir()):
        raise ValueError("refusing symlinked destination directory: " + str(destination))
    for parent in _parent_paths(destination, targets):
        if os.path.lexists(parent) and (parent.is_symlink() or not parent.is_dir()):
            raise ValueError("refusing invalid destination directory: " + str(parent))
    for target in targets:
        if os.path.lexists(target) and target.is_dir() and not target.is_symlink():
            raise ValueError("refusing to replace destination directory: " + str(target))


def _parent_paths(destination: Path, targets: List[Path]) -> List[Path]:
    parents = set()
    for target in targets:
        current = target.parent
        while current != destination:
            parents.add(current)
            current = current.parent
    return sorted(parents, key=lambda item: (len(item.parts), item.as_posix()))


def _ensure_destination_root(destination: Path) -> None:
    if not os.path.lexists(destination):
        destination.mkdir(parents=True)
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("refusing symlinked destination directory: " + str(destination))


def _make_restore_parent(parent: Path) -> None:
    if not os.path.lexists(parent):
        parent.mkdir()
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("refusing invalid destination directory: " + str(parent))
    parent.chmod(0o700)


def _selected_sources(paths: Paths) -> List[Tuple[str, Path, Path]]:
    selected = []
    for namespace, root, include in (("claude", paths.claude_home, CLAUDE_INCLUDE), ("codex", paths.codex_home, CODEX_INCLUDE)):
        selected.extend((namespace, root, source) for source in _walk_selected(root, include))
    return sorted(selected, key=lambda item: (item[0], item[2].as_posix()))


def _walk_selected(root: Path, include: Iterable[str]) -> List[Path]:
    if os.path.lexists(root) and root.is_symlink():
        raise ValueError("refusing symlinked source root: " + str(root))
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
                        if child.is_symlink():
                            found.add(child)
                            directories.remove(name)
                    for name in filenames:
                        child = current / name
                        _assert_safe_source(root, child)
                        found.add(child)
    return sorted(found, key=lambda item: item.as_posix())


def _read_manifest(snapshot_dir: Path) -> dict:
    _assert_no_symlink_ancestors(snapshot_dir)
    if not snapshot_dir.is_dir():
        raise ValueError("snapshot is not a directory")
    manifest_path = snapshot_dir / "manifest.json"
    if not os.path.lexists(manifest_path) or manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("invalid snapshot manifest")
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid snapshot manifest") from error
    if not isinstance(value, dict) or value.get("version") != SNAPSHOT_VERSION:
        raise ValueError("unsupported snapshot manifest")
    return value


def _manifest_problems(manifest: dict) -> List[str]:
    problems = []
    if set(manifest) != {"version", "label", "files"} or not isinstance(manifest.get("label"), str):
        problems.append("invalid snapshot manifest")
    records = manifest.get("files")
    if not isinstance(records, list):
        return problems + ["invalid snapshot manifest files"]
    seen = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"path", "kind", "sha256", "mode", "target"}:
            problems.append("invalid snapshot manifest record")
            continue
        path = record.get("path")
        try:
            _assert_safe_manifest_path(path)
        except (TypeError, ValueError):
            problems.append("denylisted or invalid snapshot path")
            continue
        if path in seen:
            problems.append("duplicate snapshot manifest path: " + path)
        seen.add(path)
        if record["kind"] == "file":
            if not isinstance(record["sha256"], str) or not _HASH_PATTERN.fullmatch(record["sha256"]):
                problems.append("invalid snapshot manifest hash")
            if record["mode"] not in {"0600", "0700"} or record["target"] is not None:
                problems.append("invalid snapshot manifest file mode")
        elif record["kind"] == "symlink":
            if record["sha256"] is not None or record["mode"] is not None or not isinstance(record["target"], str):
                problems.append("invalid snapshot manifest symlink")
        else:
            problems.append("invalid snapshot manifest kind")
    return problems


def _expected_tree(records: object) -> Dict[str, str]:
    expected = {".": "dir", "manifest.json": "file", "files": "dir"}
    if not isinstance(records, list):
        return expected
    for record in records:
        if not _record_is_usable(record):
            continue
        relative = (Path("files") / record["path"]).as_posix()
        expected[relative] = record["kind"]
        parent = Path(relative).parent
        while parent != Path("."):
            expected[parent.as_posix()] = "dir"
            parent = parent.parent
    return expected


def _actual_tree(snapshot_dir: Path) -> Tuple[Dict[str, str], List[str]]:
    actual, problems = {}, []
    for directory, directories, filenames in os.walk(snapshot_dir, topdown=True, followlinks=False):
        current = Path(directory)
        relative = "." if current == snapshot_dir else current.relative_to(snapshot_dir).as_posix()
        if not stat.S_ISDIR(current.lstat().st_mode):
            problems.append("symlinked or invalid snapshot directory: " + relative)
            continue
        actual[relative] = "dir"
        for name in list(directories):
            child = current / name
            if child.is_symlink():
                directories.remove(name)
                actual[child.relative_to(snapshot_dir).as_posix()] = "symlink"
                problems.append("symlinked snapshot entry: " + child.relative_to(snapshot_dir).as_posix())
        for name in filenames:
            child, details = current / name, (current / name).lstat()
            actual[child.relative_to(snapshot_dir).as_posix()] = "symlink" if stat.S_ISLNK(details.st_mode) else "file" if stat.S_ISREG(details.st_mode) else "other"
    return actual, problems


def _permission_problems(snapshot_dir: Path, actual: Dict[str, str], expected: Dict[str, str], records: object) -> List[str]:
    problems = []
    for relative, kind in expected.items():
        if actual.get(relative) != kind:
            continue
        path, mode = (snapshot_dir if relative == "." else snapshot_dir / relative), None
        mode = stat.S_IMODE(path.lstat().st_mode)
        if kind == "dir" and mode != 0o700:
            problems.append("private directory permission mismatch: " + relative)
        elif relative == "manifest.json" and mode != 0o600:
            problems.append("permission mismatch: manifest.json")
    if isinstance(records, list):
        for record in records:
            if _record_is_usable(record) and record["kind"] == "file":
                stored = snapshot_dir / "files" / record["path"]
                if stored.is_file() and stat.S_IMODE(stored.lstat().st_mode) != int(record["mode"], 8):
                    problems.append("permission mismatch: " + record["path"])
    return problems


def _record_is_usable(record: object) -> bool:
    return isinstance(record, dict) and isinstance(record.get("path"), str) and record.get("kind") in {"file", "symlink"} and not _path_is_denylisted(record["path"])


def _assert_safe_manifest_path(path: object) -> None:
    if not isinstance(path, str):
        raise ValueError("invalid snapshot manifest path")
    relative = Path(path)
    if relative.is_absolute() or len(relative.parts) < 2 or relative.parts[0] not in {"claude", "codex"}:
        raise ValueError("invalid snapshot manifest path")
    if any(part in {"", ".", ".."} for part in relative.parts) or _path_is_denylisted(path):
        raise ValueError("denylisted snapshot manifest path")


def _path_is_denylisted(path: str) -> bool:
    for part in Path(path).parts:
        lowered = part.lower()
        if lowered in _DENYLISTED_NAMES or Path(lowered).stem in _DENYLISTED_NAMES or Path(lowered).suffix in _DENYLISTED_SUFFIXES:
            return True
    return False


def _assert_safe_source(root: Path, path: Path) -> None:
    try:
        _assert_safe_manifest_path((Path("claude") / path.relative_to(root)).as_posix())
    except ValueError as error:
        raise ValueError("refusing denylisted snapshot source: " + path.as_posix()) from error


def _destination_relative(path_text: str) -> Path:
    _assert_safe_manifest_path(path_text)
    relative = Path(path_text)
    return Path("." + relative.parts[0]) / Path(*relative.parts[1:])


def _describe(path: Path) -> dict:
    if not os.path.lexists(path):
        return {"kind": "missing"}
    details, mode = path.lstat(), None
    mode = format(stat.S_IMODE(details.st_mode), "04o")
    if stat.S_ISLNK(details.st_mode):
        return {"kind": "symlink", "target": os.readlink(path)}
    if stat.S_ISREG(details.st_mode):
        return {"kind": "file", "sha256": _hash_file(path), "mode": mode}
    if stat.S_ISDIR(details.st_mode):
        return {"kind": "dir", "mode": mode}
    return {"kind": "other", "mode": mode}


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mkdir_private(path: Path) -> None:
    _assert_no_symlink_ancestors(path)
    missing, current = [], path
    while not os.path.lexists(current):
        missing.append(current)
        current = current.parent
    path.mkdir(parents=True, exist_ok=True)
    _assert_no_symlink_ancestors(path)
    if not path.is_dir():
        raise ValueError("private path is not a directory")
    for directory in reversed(missing):
        directory.chmod(0o700)
    path.chmod(0o700)


def _assert_no_symlink_ancestors(path: Path) -> None:
    absolute = Path(os.path.abspath(str(path)))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if not os.path.lexists(current) or not stat.S_ISLNK(current.lstat().st_mode):
            continue
        # Darwin's /var is a system-owned compatibility symlink to /private/var;
        # it is outside the caller-controlled snapshot/storage boundary.
        if current == Path("/var"):
            continue
        raise ValueError("refusing symlinked snapshot/storage ancestor: " + str(current))
