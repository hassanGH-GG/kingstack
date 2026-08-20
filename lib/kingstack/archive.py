"""Immutable, private archives of the selected agent configuration files."""

import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from kingstack.inventory import CLAUDE_INCLUDE, CODEX_INCLUDE
from kingstack.paths import Paths


ARCHIVE_VERSION = 1
_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}$")
_DENYLISTED_NAMES = {
    "auth.json", ".claude.json",
}
_DENYLISTED_STEMS = {"auth", "session", "sessions", "transcript", "transcripts"}
_DENYLISTED_PREFIXES = ("credentials", "keychain")
_DENYLISTED_SUFFIXES = {".jsonl", ".transcript", ".transcript.json"}


class SourceChanged(ValueError):
    """The source did not remain identical for the full archive capture."""


def create_archive(paths: Paths, destination: Path, label: str,
                   after_copy: Optional[Callable[[], None]] = None) -> Path:
    """Capture selected configuration into a new, verified archive directory.

    The temporary directory is a private sibling of the eventual archive.  It
    is removed on every failure and renamed only after the source inventory is
    unchanged and the copied payload verifies against its manifest.
    """
    if not isinstance(label, str) or not _LABEL.fullmatch(label):
        raise ValueError("archive label must be 1-80 safe characters")

    pre_inventory = _source_inventory(paths)
    archive_name = "archive-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    destination = Path(destination).expanduser().resolve()
    final = destination / archive_name
    if final.exists() or final.is_symlink():
        raise ValueError("archive directory already exists")

    _private_directory(destination)
    # Recheck after making the parent.  This avoids replacing an existing ID;
    # the temporary directory is never the public archive identifier.
    if final.exists() or final.is_symlink():
        raise ValueError("archive directory already exists")
    temporary = destination / ("." + archive_name + "." + uuid.uuid4().hex + ".tmp")
    temporary.mkdir(mode=0o700)
    temporary.chmod(0o700)
    try:
        files_root = temporary / "files"
        _private_directory(files_root)
        records = []  # type: List[Dict[str, object]]
        for entry in pre_inventory:
            source = _source_path(paths, str(entry["path"]))
            record = _copy_entry(source, files_root, entry)
            records.append(record)

        if after_copy is not None:
            after_copy()
        post_inventory = _source_inventory(paths)
        if pre_inventory != post_inventory:
            raise SourceChanged("source changed while creating archive")

        manifest = {
            "version": ARCHIVE_VERSION,
            "label": label,
            "source_inventories": {"pre": pre_inventory, "post": post_inventory},
            "files": records,
        }
        manifest_path = temporary / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        manifest_path.chmod(0o600)
        problems = verify_archive(temporary, check_permissions=True)
        if problems:
            raise ValueError("created archive failed verification: " + "; ".join(problems))

        # The final operation is a no-replace rename.  A competing capture
        # therefore cannot turn this archive into an overwrite.
        if final.exists() or final.is_symlink():
            raise ValueError("archive directory already exists")
        _publish_exclusively(temporary, final)
        return final
    except Exception:
        if temporary.exists() and not temporary.is_symlink():
            shutil.rmtree(temporary)
        raise


def verify_archive(archive_dir: Path, check_permissions: bool = False) -> List[str]:
    """Return archive integrity problems, or an empty list when it verifies."""
    archive_dir = Path(archive_dir)
    problems = []  # type: List[str]
    try:
        archive_stat = archive_dir.lstat()
    except OSError as error:
        return ["archive is unavailable: " + str(error)]
    if stat.S_ISLNK(archive_stat.st_mode) or not stat.S_ISDIR(archive_stat.st_mode):
        return ["archive is not a directory"]
    if check_permissions and stat.S_IMODE(archive_stat.st_mode) != 0o700:
        problems.append("archive permission mismatch")

    manifest_path = archive_dir / "manifest.json"
    try:
        manifest_stat = manifest_path.lstat()
        if not stat.S_ISREG(manifest_stat.st_mode):
            return problems + ["manifest is not a regular file"]
        with manifest_path.open("r", encoding="utf-8") as source:
            manifest = json.load(source)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return problems + ["invalid manifest: " + str(error)]
    if check_permissions and stat.S_IMODE(manifest_stat.st_mode) != 0o600:
        problems.append("manifest permission mismatch")

    if not isinstance(manifest, dict):
        return problems + ["invalid archive manifest"]
    records = manifest.get("files")
    inventories = manifest.get("source_inventories")
    if manifest.get("version") != ARCHIVE_VERSION or not isinstance(records, list):
        return problems + ["invalid archive manifest"]
    if not isinstance(inventories, dict) or inventories.get("pre") != inventories.get("post"):
        problems.append("source inventory mismatch")

    expected = set()
    for record in records:
        error = _validate_manifest_record(record)
        if error:
            problems.append(error)
            continue
        path_text = str(record["path"])
        if path_text in expected:
            problems.append("duplicate archive entry: " + path_text)
            continue
        expected.add(path_text)
        stored = archive_dir / "files" / path_text
        try:
            details = stored.lstat()
        except OSError:
            problems.append("missing archive entry: " + path_text)
            continue
        if record["kind"] == "file":
            if not stat.S_ISREG(details.st_mode):
                problems.append("kind mismatch: " + path_text)
                continue
            if _hash_file(stored) != record["sha256"]:
                problems.append("hash mismatch: " + path_text)
            if check_permissions and stat.S_IMODE(details.st_mode) != int(str(record["mode"]), 8):
                problems.append("permission mismatch: " + path_text)
        elif not stat.S_ISLNK(details.st_mode):
            problems.append("kind mismatch: " + path_text)
        elif os.readlink(stored) != record["target"]:
            problems.append("symlink target mismatch: " + path_text)

    files_root = archive_dir / "files"
    if not files_root.is_dir() or files_root.is_symlink():
        problems.append("archive files directory is invalid")
    else:
        actual = _stored_paths(files_root, check_permissions, problems)
        for path_text in sorted(actual - expected):
            problems.append("unexpected archive entry: " + path_text)
    return problems


def _source_inventory(paths: Paths) -> List[Dict[str, object]]:
    selected = []  # type: List[Dict[str, object]]
    for namespace, root, include in (
        ("claude", paths.claude_home, CLAUDE_INCLUDE),
        ("codex", paths.codex_home, CODEX_INCLUDE),
    ):
        root = Path(root)
        if root.is_symlink():
            raise ValueError("refusing symlinked source root: " + str(root))
        if not root.is_dir():
            continue
        for path in _allowlisted_entries(root, include):
            relative = path.relative_to(root).as_posix()
            _reject_denylisted(relative)
            details = path.lstat()
            kind = "symlink" if stat.S_ISLNK(details.st_mode) else "file"
            if kind == "file" and not stat.S_ISREG(details.st_mode):
                raise ValueError("refusing non-regular source path: " + relative)
            selected.append({
                "path": namespace + "/" + relative,
                "kind": kind,
                "sha256": None if kind == "symlink" else _hash_file(path),
                "mode": format(stat.S_IMODE(details.st_mode), "04o"),
                "target": os.readlink(path) if kind == "symlink" else None,
                "identity": [details.st_dev, details.st_ino],
            })
    return sorted(selected, key=lambda item: str(item["path"]))


def _allowlisted_entries(root: Path, include: Iterable[str]) -> List[Path]:
    found = set()  # type: set
    for pattern in include:
        for match in root.glob(pattern):
            _collect_allowlisted(match, root, found)
    return sorted(found, key=lambda path: path.as_posix())


def _collect_allowlisted(path: Path, root: Path, found: set) -> None:
    relative = path.relative_to(root).as_posix()
    _reject_denylisted(relative)
    details = path.lstat()
    if stat.S_ISLNK(details.st_mode) or stat.S_ISREG(details.st_mode):
        found.add(path)
        return
    if not stat.S_ISDIR(details.st_mode):
        raise ValueError("refusing non-regular source path: " + relative)
    for directory, directories, filenames in os.walk(path, topdown=True, followlinks=False):
        current = Path(directory)
        for name in list(directories):
            child = current / name
            _reject_denylisted(child.relative_to(root).as_posix())
            if child.is_symlink():
                found.add(child)
                directories.remove(name)
        for name in filenames:
            child = current / name
            _reject_denylisted(child.relative_to(root).as_posix())
            details = child.lstat()
            if stat.S_ISLNK(details.st_mode) or stat.S_ISREG(details.st_mode):
                found.add(child)
            else:
                raise ValueError("refusing non-regular source path: " + str(child))


def _copy_entry(source: Path, files_root: Path,
                source_record: Dict[str, object]) -> Dict[str, object]:
    _assert_source_matches(source, source_record)
    path_text = str(source_record["path"])
    relative = PurePosixPath(path_text)
    destination = files_root.joinpath(*relative.parts)
    _private_directory_chain(files_root, destination.parent)
    if source_record["kind"] == "symlink":
        os.symlink(str(source_record["target"]), destination)
        mode = None
        sha256 = None
        target = str(source_record["target"])
    else:
        mode_value, sha256 = _copy_regular_file(source, destination, source_record)
        mode = format(mode_value, "04o")
        target = None
        if sha256 != source_record["sha256"]:
            raise SourceChanged("source changed while copying " + path_text)
    return {"path": path_text, "kind": source_record["kind"], "sha256": sha256,
            "mode": mode, "target": target}


def _assert_source_matches(source: Path, record: Dict[str, object]) -> None:
    try:
        details = source.lstat()
    except OSError as error:
        raise SourceChanged("source disappeared while copying " + str(source)) from error
    if [details.st_dev, details.st_ino] != record["identity"]:
        raise SourceChanged("source identity changed while copying " + str(source))
    if (stat.S_ISLNK(details.st_mode) and record["kind"] != "symlink") or (
            stat.S_ISREG(details.st_mode) and record["kind"] != "file"):
        raise SourceChanged("source kind changed while copying " + str(source))


def _copy_regular_file(source: Path, destination: Path,
                       record: Dict[str, object]) -> Tuple[int, str]:
    """Copy a verified regular source via no-follow, descriptor-relative I/O."""
    source_fd = None
    destination_parent_fd = None
    destination_fd = None
    try:
        source_parent_fd = _open_directory_no_follow(source.parent)
        try:
            source_fd = os.open(
                source.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=source_parent_fd
            )
        finally:
            os.close(source_parent_fd)
        details = os.fstat(source_fd)
        if (not stat.S_ISREG(details.st_mode)
                or [details.st_dev, details.st_ino] != record["identity"]):
            raise SourceChanged("source changed while copying " + str(source))
        mode_value = int(str(record["mode"]), 8) & 0o700
        destination_parent_fd = _open_directory_no_follow(destination.parent)
        destination_fd = os.open(
            destination.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            mode_value,
            dir_fd=destination_parent_fd,
        )
        digest = hashlib.sha256()
        while True:
            chunk = os.read(source_fd, 65536)
            if not chunk:
                break
            digest.update(chunk)
            _write_all(destination_fd, chunk)
        os.fchmod(destination_fd, mode_value)
        return mode_value, digest.hexdigest()
    except SourceChanged:
        raise
    except OSError as error:
        raise SourceChanged("source changed while copying " + str(source)) from error
    finally:
        for descriptor in (destination_fd, destination_parent_fd, source_fd):
            if descriptor is not None:
                os.close(descriptor)


def _write_all(descriptor: int, content: bytes) -> None:
    offset = 0
    while offset < len(content):
        written = os.write(descriptor, content[offset:])
        if written <= 0:
            raise OSError("could not write archive payload")
        offset += written


def _source_path(paths: Paths, path_text: str) -> Path:
    namespace, relative = path_text.split("/", 1)
    root = paths.claude_home if namespace == "claude" else paths.codex_home
    return Path(root).joinpath(*PurePosixPath(relative).parts)


def _validate_manifest_record(record: object) -> Optional[str]:
    if not isinstance(record, dict):
        return "invalid archive manifest record"
    path_text = record.get("path")
    if not isinstance(path_text, str) or not _safe_archive_path(path_text):
        return "invalid archive path"
    try:
        _reject_denylisted(path_text.split("/", 1)[1])
    except ValueError:
        return "denylisted archive path: " + path_text
    kind = record.get("kind")
    if kind == "file":
        if (not isinstance(record.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
                or not isinstance(record.get("mode"), str)
                or not re.fullmatch(r"0[0-7]{3}", record["mode"])):
            return "invalid archive manifest record"
    elif kind == "symlink":
        if not isinstance(record.get("target"), str) or record.get("mode") is not None:
            return "invalid archive manifest record"
    else:
        return "invalid archive manifest record"
    return None


def _stored_paths(files_root: Path, check_permissions: bool,
                  problems: List[str]) -> set:
    actual = set()  # type: set
    for directory, directories, filenames in os.walk(files_root, topdown=True, followlinks=False):
        current = Path(directory)
        if check_permissions and stat.S_IMODE(current.lstat().st_mode) != 0o700:
            problems.append("directory permission mismatch: " + current.relative_to(files_root).as_posix())
        for name in list(directories):
            child = current / name
            if child.is_symlink():
                actual.add(child.relative_to(files_root).as_posix())
                directories.remove(name)
        for name in filenames:
            child = current / name
            actual.add(child.relative_to(files_root).as_posix())
    return actual


def _reject_denylisted(relative: str) -> None:
    for part in PurePosixPath(relative).parts:
        lower = part.lower()
        stem = Path(lower).stem
        if (lower in _DENYLISTED_NAMES or stem in _DENYLISTED_STEMS
                or stem.startswith(_DENYLISTED_PREFIXES)
                or any(lower.endswith(suffix) for suffix in _DENYLISTED_SUFFIXES)):
            raise ValueError("denylisted source path: " + relative)


def _safe_archive_path(path_text: str) -> bool:
    parts = PurePosixPath(path_text).parts
    return bool(parts and parts[0] in {"claude", "codex"} and all(
        part not in {"", ".", ".."} for part in parts
    ) and \
        "/".join(parts) == path_text and "\\" not in path_text)


def _private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("refusing non-directory archive path: " + str(path))
    path.chmod(0o700)


def _private_directory_chain(root: Path, leaf: Path) -> None:
    """Create and chmod every archive-relative ancestor, not just the leaf."""
    current = root
    for part in leaf.relative_to(root).parts:
        current = current / part
        _private_directory(current)


def _open_directory_no_follow(path: Path) -> int:
    """Open each absolute directory component without retaining an FD chain."""
    path = Path(path)
    if not path.is_absolute():
        raise OSError("archive path must be absolute")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _publish_exclusively(temporary: Path, final: Path) -> None:
    """Publish a directory with the platform no-replace rename primitive."""
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        operation = library.renamex_np
        operation.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        result = operation(os.fsencode(temporary), os.fsencode(final), 0x00000004)
    elif sys.platform.startswith("linux") and hasattr(library, "renameat2"):
        operation = library.renameat2
        operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                              ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        result = operation(-100, os.fsencode(temporary), -100, os.fsencode(final), 1)
    else:
        raise OSError("platform lacks an exclusive directory rename")
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise ValueError("archive directory already exists")
    raise OSError(error_number, os.strerror(error_number), str(final))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
