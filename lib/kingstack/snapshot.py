"""Private, verified snapshots of the safe Claude and Codex configuration subset.

Filesystem reads and mutations become descriptor-relative as soon as an absolute
root is opened. A successful pathname check is not authority that can safely be
reused after an attacker renames or symlinks one of its ancestors.
"""

import errno
import fnmatch
import hashlib
import json
import os
import re
import stat
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Set, Tuple

from kingstack.inventory import CLAUDE_INCLUDE, CODEX_INCLUDE
from kingstack.paths import Paths


SNAPSHOT_VERSION = 2
_ID_PATTERN = re.compile(r"^snapshot-[0-9]{8}-[0-9]{6}$")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}$")
_TRANSACTION_NAME_PATTERN = re.compile(
    r"^\.kingstack-restore-(?:stage|backup)-[A-Za-z0-9-]+$"
)
_MODE_PATTERN = re.compile(r"^0[0-7]{3}$")
_DENYLISTED_NAMES = {
    ".claude.json", "auth.json", "credentials", "credential", "keychain",
    "keychains", "session", "sessions", "cache", "caches", "browser",
    "browsers", "transcript", "transcripts",
}
_DENYLISTED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".jsonl"}
_JOURNAL_NAME = ".kingstack-restore-journal.json"
_JOURNAL_TEMP_NAME = _JOURNAL_NAME + ".tmp"


def _platform_supports_required_primitives() -> bool:
    required = (
        os.open, os.stat, os.mkdir, os.rename, os.unlink, os.rmdir,
        os.chmod, os.readlink, os.symlink,
    )
    return (
        hasattr(os, "O_DIRECTORY")
        and hasattr(os, "O_NOFOLLOW")
        and hasattr(os, "O_EXCL")
        and hasattr(os, "fchmod")
        and all(operation in os.supports_dir_fd for operation in required)
    )


_REQUIRED_PRIMITIVES_AVAILABLE = _platform_supports_required_primitives()


class _JournalPublicationUncertain(Exception):
    """The journal rename happened but its parent fsync did not complete."""


class _DirectoryCache:
    """Keep destination directory descriptors alive through each transaction."""

    def __init__(self, root_fd: int):
        self.fds = {"": os.dup(root_fd)}  # type: Dict[str, int]
        self.removed = set()  # type: Set[str]

    def close(self) -> None:
        for descriptor in list(self.fds.values()):
            _close_quietly(descriptor)
        self.fds.clear()

    def existing(self, relative: str) -> Optional[int]:
        if relative == "":
            return self.fds[""]
        current_key = ""
        current_fd = self.fds[""]
        for part in PurePosixPath(relative).parts:
            child_key = part if not current_key else current_key + "/" + part
            if child_key in self.removed:
                return None
            if child_key in self.fds:
                current_key = child_key
                current_fd = self.fds[child_key]
                continue
            details = _stat_optional(current_fd, part)
            if details is None:
                return None
            if not stat.S_ISDIR(details.st_mode):
                raise ValueError(
                    "refusing invalid destination directory: " + child_key
                )
            child_fd = _open_child_directory(current_fd, part)
            self.fds[child_key] = child_fd
            current_key = child_key
            current_fd = child_fd
        return current_fd

    def ensure(self, relative: str) -> int:
        current_key = ""
        current_fd = self.fds[""]
        for part in PurePosixPath(relative).parts:
            child_key = part if not current_key else current_key + "/" + part
            if child_key in self.fds and child_key not in self.removed:
                current_key = child_key
                current_fd = self.fds[child_key]
                continue
            details = _stat_optional(current_fd, part)
            if details is None:
                _mkdir_durable(current_fd, part, 0o700)
            elif not stat.S_ISDIR(details.st_mode):
                raise ValueError(
                    "refusing invalid destination directory: " + child_key
                )
            child_fd = _open_child_directory(current_fd, part)
            self.fds[child_key] = child_fd
            self.removed.discard(child_key)
            current_key = child_key
            current_fd = child_fd
        return current_fd

    def validate_links(self) -> None:
        ordered = sorted(
            self.fds, key=lambda item: (item.count("/"), item)
        )
        for relative in ordered:
            if not relative or relative in self.removed:
                continue
            parent, name = _split_relative(relative)
            parent_fd = self.fds.get(parent)
            if parent_fd is None or parent in self.removed:
                raise ValueError("destination directory changed during transaction")
            details = _stat_optional(parent_fd, name)
            if details is None or not stat.S_ISDIR(details.st_mode):
                raise ValueError("destination directory changed during transaction")
            if _identity(details) != _identity(os.fstat(self.fds[relative])):
                raise ValueError("destination directory changed during transaction")

    def remove_empty(self, relative: str) -> None:
        descriptor = self.fds.get(relative)
        if descriptor is None or relative in self.removed:
            return
        parent, name = _split_relative(relative)
        parent_fd = self.fds[parent]
        details = _stat_optional(parent_fd, name)
        if details is None:
            self.removed.add(relative)
            return
        if _identity(details) != _identity(os.fstat(descriptor)):
            raise ValueError("destination directory changed during rollback")
        try:
            os.rmdir(name, dir_fd=parent_fd)
        except OSError as error:
            raise ValueError(
                "restore rollback could not remove a newly created parent"
            ) from error
        _fsync_directory_fd(parent_fd)
        self.removed.add(relative)


def create_snapshot(paths: Paths, destination: Path, label: str) -> Path:
    """Create a new private snapshot without post-check pathname access."""
    _require_primitives()
    if not isinstance(label, str) or not _LABEL_PATTERN.fullmatch(label):
        raise ValueError("snapshot label must be 1-80 safe characters")
    destination = Path(destination).expanduser()
    source_roots = _open_selected_source_roots(paths)
    destination_fd = None  # type: Optional[int]
    snapshot_fd = None  # type: Optional[int]
    snapshot_directories = None  # type: Optional[_DirectoryCache]
    snapshot_name = "snapshot-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    snapshot_identity = None  # type: Optional[Tuple[int, int]]
    created = False
    try:
        destination_fd, _ = _open_absolute_directory(
            destination, create=True, private=True
        )
        try:
            os.mkdir(snapshot_name, 0o700, dir_fd=destination_fd)
        except FileExistsError as error:
            raise ValueError("snapshot directory already exists") from error
        except OSError as error:
            raise ValueError("could not create private snapshot directory") from error
        created = True
        snapshot_fd = _open_child_directory(destination_fd, snapshot_name)
        os.fchmod(snapshot_fd, 0o700)
        _fsync_directory_fd(snapshot_fd)
        _fsync_directory_fd(destination_fd)
        snapshot_identity = _identity(os.fstat(snapshot_fd))
        snapshot_directories = _DirectoryCache(snapshot_fd)
        snapshot_directories.ensure("files")

        records = []
        selected = [
            entry for root in source_roots for entry in root["entries"]
        ]
        for source in sorted(
            selected, key=lambda entry: (entry["namespace"], entry["parts"])
        ):
            path_text = source["namespace"] + "/" + "/".join(source["parts"])
            _assert_safe_manifest_path(path_text)
            stored_parent = (
                ("files", source["namespace"]) + source["parts"][:-1]
            )
            parent_fd = snapshot_directories.ensure("/".join(stored_parent))
            records.append(
                _copy_source_entry(
                    source, parent_fd, source["parts"][-1], path_text
                )
            )

        snapshot_directories.validate_links()
        for root in source_roots:
            _verify_open_path_identity(
                root["path"], root["fd"],
                "source root changed while creating snapshot",
            )
        _verify_open_path_identity(
            destination, destination_fd, "snapshot destination root changed"
        )
        manifest = {
            "version": SNAPSHOT_VERSION,
            "label": label,
            "files": records,
        }
        _write_new_regular_at(
            snapshot_fd,
            "manifest.json",
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            0o600,
        )
        snapshot_directories.validate_links()
        problems = _verify_snapshot_fd(snapshot_fd, True)
        if problems:
            raise ValueError(
                "created snapshot failed verification: " + "; ".join(problems)
            )
        snapshot_directories.validate_links()
        _verify_open_path_identity(
            destination, destination_fd, "snapshot destination root changed"
        )
        published = _stat_optional(destination_fd, snapshot_name)
        if (
            published is None
            or not stat.S_ISDIR(published.st_mode)
            or _identity(published) != snapshot_identity
        ):
            raise ValueError("snapshot directory changed before publication")
        return destination / snapshot_name
    except Exception:
        if created and destination_fd is not None and snapshot_identity is not None:
            if snapshot_directories is not None:
                snapshot_directories.close()
                snapshot_directories = None
            if snapshot_fd is not None:
                os.close(snapshot_fd)
                snapshot_fd = None
            _remove_tree_at(destination_fd, snapshot_name, snapshot_identity)
        raise
    finally:
        if snapshot_directories is not None:
            snapshot_directories.close()
        _close_quietly(snapshot_fd)
        _close_quietly(destination_fd)
        for root in source_roots:
            _close_quietly(root["fd"])


def snapshot_path(storage: Path, identifier: str) -> Path:
    """Resolve a validated direct-child snapshot identifier inside storage."""
    _require_primitives()
    if not isinstance(identifier, str) or not _ID_PATTERN.fullmatch(identifier):
        raise ValueError("invalid snapshot identifier")
    storage = Path(storage).expanduser()
    storage_fd, _ = _open_absolute_directory(
        storage, create=False, private=False
    )
    if storage_fd is None:
        raise ValueError("snapshot storage is not a directory")
    try:
        details = _stat_optional(storage_fd, identifier)
        if details is not None and not stat.S_ISDIR(details.st_mode):
            raise ValueError(
                "refusing symlinked snapshot/storage ancestor: "
                + str(storage / identifier)
            )
    finally:
        os.close(storage_fd)
    return storage / identifier


def verify_snapshot(snapshot_dir: Path, check_permissions: bool = False) -> List[str]:
    """Return manifest, tree, integrity, and requested permission failures."""
    try:
        _require_primitives()
        snapshot_fd, _ = _open_absolute_directory(
            Path(snapshot_dir), create=False, private=False
        )
        if snapshot_fd is None:
            return ["snapshot is not a directory"]
    except (OSError, TypeError, ValueError) as error:
        return [str(error)]
    try:
        return _verify_snapshot_fd(snapshot_fd, check_permissions)
    finally:
        os.close(snapshot_fd)


def restore_snapshot(
    snapshot_dir: Path,
    destination_home: Path,
    dry_run: bool = True,
    expected_current_hash: Optional[str] = None,
) -> List[Path]:
    """Plan or transactionally restore a verified snapshot."""
    _require_primitives()
    snapshot_dir = Path(snapshot_dir)
    destination_home = Path(destination_home).expanduser()
    snapshot_fd, _ = _open_absolute_directory(
        snapshot_dir, create=False, private=False
    )
    if snapshot_fd is None:
        raise ValueError("refusing invalid snapshot: snapshot is not a directory")
    try:
        problems = _verify_snapshot_fd(snapshot_fd, True)
        if problems:
            raise ValueError("refusing invalid snapshot: " + "; ".join(problems))
        manifest = _read_manifest_fd(snapshot_fd)
        records = manifest["files"]
        planned = [
            destination_home / _destination_relative(record["path"])
            for record in records
        ]
        if dry_run:
            return planned
        if not isinstance(expected_current_hash, str):
            if expected_current_hash is None:
                raise ValueError("refusing apply without expected current hash")
            raise ValueError("invalid expected current hash")
        if not _HASH_PATTERN.fullmatch(expected_current_hash):
            raise ValueError("invalid expected current hash")
        destination_fd, destination_text = _open_absolute_directory(
            destination_home, create=True, private=False
        )
        if destination_fd is None:
            raise ValueError("refusing invalid destination directory")
        try:
            _recover_transaction(destination_fd, destination_text)
            current = _current_destination_hash_fd(
                snapshot_fd, destination_fd, records
            )
            if current != expected_current_hash:
                raise ValueError(
                    "refusing live apply: expected current hash does not match"
                )
            return _apply_transaction(
                snapshot_fd,
                snapshot_dir.name,
                destination_fd,
                destination_text,
                destination_home,
                records,
                planned,
                expected_current_hash,
            )
        finally:
            os.close(destination_fd)
    finally:
        os.close(snapshot_fd)


def current_destination_hash(snapshot_dir: Path, destination_home: Path) -> str:
    """Hash target and parent state without following destination symlinks."""
    _require_primitives()
    snapshot_fd, _ = _open_absolute_directory(
        Path(snapshot_dir), create=False, private=False
    )
    if snapshot_fd is None:
        raise ValueError("snapshot is not a directory")
    try:
        manifest = _read_manifest_fd(snapshot_fd)
        if _manifest_problems(manifest):
            raise ValueError("invalid snapshot manifest")
        destination_fd, _ = _open_absolute_directory(
            Path(destination_home).expanduser(), create=False, private=False
        )
        try:
            return _current_destination_hash_fd(
                snapshot_fd, destination_fd, manifest["files"]
            )
        finally:
            _close_quietly(destination_fd)
    finally:
        os.close(snapshot_fd)


def _apply_transaction(
    snapshot_fd: int,
    snapshot_name: str,
    destination_fd: int,
    destination_text: str,
    destination_path: Path,
    records: List[dict],
    targets: List[Path],
    expected_hash: str,
) -> List[Path]:
    token = uuid.uuid4().hex
    stage_name = ".kingstack-restore-stage-" + token
    backup_name = ".kingstack-restore-backup-" + token
    stage_fd = _create_private_child_directory(destination_fd, stage_name)
    backup_fd = _create_private_child_directory(destination_fd, backup_name)
    stage_identity = _identity(os.fstat(stage_fd))
    backup_identity = _identity(os.fstat(backup_fd))
    cache = _DirectoryCache(destination_fd)
    journal_written = False
    committed = False
    transaction = None  # type: Optional[dict]
    try:
        target_names = [
            _destination_relative_text(record["path"]) for record in records
        ]
        parents = _parent_relative_paths(target_names)
        entries = []
        parent_records = [
            {"path": parent, "before": _describe_relative_cached(cache, parent)}
            for parent in parents
        ]
        for index, record in enumerate(records):
            target = target_names[index]
            before = _describe_relative_cached(cache, target)
            if before["kind"] in {"dir", "other", "blocked"}:
                raise ValueError(
                    "refusing to replace destination directory: " + target
                )
            if not _valid_state(before, target_state=True):
                raise ValueError("refusing invalid destination target state")
            after = _stage_snapshot_record(
                snapshot_fd, record, stage_fd, str(index)
            )
            entries.append({
                "target": target,
                "backup": str(index),
                "before": before,
                "after": after,
            })
        _fsync_directory_fd(stage_fd)
        _fsync_directory_fd(backup_fd)
        transaction = {
            "version": 2,
            "status": "prepared",
            "expected": expected_hash,
            "destination": destination_text,
            "snapshot": snapshot_name,
            "stage": stage_name,
            "backup": backup_name,
            "entries": entries,
            "parents": parent_records,
        }
        journal_identity = _write_journal(destination_fd, transaction)
        journal_written = True

        cache.validate_links()
        current = _current_destination_hash_fd(
            snapshot_fd, destination_fd, records, cache
        )
        if current != expected_hash:
            raise ValueError("destination changed before atomic rename")
        for parent in parents:
            parent_fd = cache.ensure(parent)
            os.fchmod(parent_fd, 0o700)
            _fsync_directory_fd(parent_fd)
        cache.validate_links()

        for entry in entries:
            target_parent, target_name = _split_relative(entry["target"])
            target_parent_fd = cache.existing(target_parent)
            if target_parent_fd is None:
                raise ValueError("destination target parent disappeared")
            if _describe_at(target_parent_fd, target_name) != entry["before"]:
                raise ValueError(
                    "destination target changed before atomic rename"
                )
            if entry["before"]["kind"] != "missing":
                _rename_durable(
                    target_parent_fd,
                    target_name,
                    backup_fd,
                    entry["backup"],
                )
            _rename_durable(
                stage_fd, entry["backup"], target_parent_fd, target_name
            )
            if _describe_at(target_parent_fd, target_name) != entry["after"]:
                raise ValueError("restored target does not match staged state")

        cache.validate_links()
        _verify_open_path_identity(
            destination_path,
            destination_fd,
            "destination root changed during transaction",
        )
        transaction["status"] = "committed"
        journal_identity = _write_journal(destination_fd, transaction)
        committed = True
    except _JournalPublicationUncertain:
        # The on-disk journal is prepared or committed, and owns the retained
        # transaction directories. Never roll back against an uncertain status.
        raise
    except Exception:
        if journal_written and not committed and transaction is not None:
            recovery = _validate_journal_physical(destination_fd, transaction)
            recovery["journal_identity"] = journal_identity
            try:
                _rollback_transaction(destination_fd, transaction, recovery)
            except Exception:
                _close_recovery_context(recovery)
                raise
            recovery["cache"].close()
            _cleanup_transaction(destination_fd, transaction, recovery)
        elif not journal_written:
            _close_quietly(stage_fd)
            _close_quietly(backup_fd)
            stage_fd = -1
            backup_fd = -1
            _remove_tree_if_identity(
                destination_fd, stage_name, stage_identity
            )
            _remove_tree_if_identity(
                destination_fd, backup_name, backup_identity
            )
        raise
    finally:
        cache.close()
        _close_quietly(stage_fd)
        _close_quietly(backup_fd)

    if transaction is None:
        raise ValueError("restore transaction was not created")
    recovery = _validate_journal_physical(destination_fd, transaction)
    recovery["journal_identity"] = journal_identity
    recovery["cache"].close()
    _cleanup_transaction(destination_fd, transaction, recovery)
    return targets


def _recover_transaction(destination_fd: int, destination_text: str) -> None:
    if _stat_optional(destination_fd, _JOURNAL_NAME) is None:
        return
    transaction, journal_identity = _read_journal(
        destination_fd, destination_text
    )
    recovery = _validate_journal_physical(destination_fd, transaction)
    recovery["journal_identity"] = journal_identity
    try:
        if transaction["status"] == "committed":
            _verify_committed_transaction(transaction, recovery)
        else:
            _rollback_transaction(destination_fd, transaction, recovery)
    except Exception:
        _close_recovery_context(recovery)
        raise
    recovery["cache"].close()
    _cleanup_transaction(destination_fd, transaction, recovery)


def _rollback_transaction(
    destination_fd: int, transaction: dict, recovery: dict
) -> None:
    del destination_fd
    cache = recovery["cache"]
    backup_fd = recovery.get("backup_fd")
    for entry in reversed(transaction["entries"]):
        parent, name = _split_relative(entry["target"])
        parent_fd = cache.existing(parent)
        before = entry["before"]
        if before["kind"] == "missing":
            if parent_fd is not None:
                current = _describe_at(parent_fd, name)
                if current["kind"] in {"dir", "other"}:
                    raise ValueError("invalid restore transaction journal")
                if current["kind"] != "missing":
                    _unlink_durable(parent_fd, name)
        else:
            saved = (
                _describe_at(backup_fd, entry["backup"])
                if backup_fd is not None else {"kind": "missing"}
            )
            if saved != {"kind": "missing"}:
                if saved != before or parent_fd is None:
                    raise ValueError("invalid restore transaction journal")
                _rename_durable(
                    backup_fd, entry["backup"], parent_fd, name
                )
            elif parent_fd is None or _describe_at(parent_fd, name) != before:
                raise ValueError(
                    "restore transaction cannot prove rollback content"
                )
        if parent_fd is not None and _describe_at(parent_fd, name) != before:
            raise ValueError("restore rollback did not restore target state")

    cache.validate_links()
    for parent in reversed(transaction["parents"]):
        relative = parent["path"]
        before = parent["before"]
        descriptor = cache.existing(relative)
        if before["kind"] == "dir":
            if descriptor is None:
                raise ValueError("restore rollback lost an existing parent")
            os.fchmod(descriptor, int(before["mode"], 8))
            _fsync_directory_fd(descriptor)
        elif descriptor is not None:
            cache.remove_empty(relative)


def _verify_committed_transaction(transaction: dict, recovery: dict) -> None:
    if transaction["version"] != 2:
        raise ValueError(
            "committed restore journal lacks verifiable after-state"
        )
    cache = recovery["cache"]
    for entry in transaction["entries"]:
        parent, name = _split_relative(entry["target"])
        parent_fd = cache.existing(parent)
        if parent_fd is None or _describe_at(parent_fd, name) != entry["after"]:
            raise ValueError("committed restore target is absent or changed")
    for parent in transaction["parents"]:
        descriptor = cache.existing(parent["path"])
        if (
            descriptor is None
            or stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o700
        ):
            raise ValueError("committed restore parent is absent or changed")
    cache.validate_links()


def _cleanup_transaction(
    destination_fd: int, transaction: dict, recovery: dict
) -> None:
    stage_identity = recovery.get("stage_identity")
    backup_identity = recovery.get("backup_identity")
    stage_fd = recovery.get("stage_fd")
    backup_fd = recovery.get("backup_fd")
    try:
        _remove_retained_tree_if_identity(
            destination_fd,
            transaction["stage"],
            stage_identity,
            stage_fd,
        )
        _remove_retained_tree_if_identity(
            destination_fd,
            transaction["backup"],
            backup_identity,
            backup_fd,
        )
    finally:
        _close_quietly(stage_fd)
        _close_quietly(backup_fd)
        recovery["stage_fd"] = None
        recovery["backup_fd"] = None
    expected_journal = recovery.get("journal_identity")
    details = _stat_optional(destination_fd, _JOURNAL_NAME)
    if details is not None:
        if (
            expected_journal is not None
            and _identity(details) != expected_journal
        ):
            raise ValueError("restore journal changed during cleanup")
        if not stat.S_ISREG(details.st_mode):
            raise ValueError("invalid restore transaction journal")
        _unlink_durable(destination_fd, _JOURNAL_NAME)


def _close_recovery_context(recovery: dict) -> None:
    recovery["cache"].close()
    _close_quietly(recovery.get("stage_fd"))
    _close_quietly(recovery.get("backup_fd"))
    recovery["stage_fd"] = None
    recovery["backup_fd"] = None


def _validate_journal_physical(destination_fd: int, transaction: dict) -> dict:
    """Open and retain every recovery anchor through rollback or cleanup."""
    cache = _DirectoryCache(destination_fd)
    stage_fd = None  # type: Optional[int]
    backup_fd = None  # type: Optional[int]
    try:
        stage_fd, stage_identity = _open_optional_transaction_directory(
            destination_fd, transaction["stage"]
        )
        backup_fd, backup_identity = _open_optional_transaction_directory(
            destination_fd, transaction["backup"]
        )
        for parent in transaction["parents"]:
            descriptor = cache.existing(parent["path"])
            if parent["before"]["kind"] == "dir" and descriptor is None:
                raise ValueError("invalid restore transaction journal")
        for entry in transaction["entries"]:
            parent, name = _split_relative(entry["target"])
            parent_fd = cache.existing(parent)
            if transaction["status"] == "committed":
                continue
            before = entry["before"]
            current = (
                _describe_at(parent_fd, name)
                if parent_fd is not None else {"kind": "missing"}
            )
            saved = (
                _describe_at(backup_fd, entry["backup"])
                if backup_fd is not None else {"kind": "missing"}
            )
            if before["kind"] == "missing":
                if (
                    saved["kind"] != "missing"
                    or current["kind"] in {"dir", "other"}
                ):
                    raise ValueError("invalid restore transaction journal")
            elif saved["kind"] == "missing":
                if current != before:
                    raise ValueError("invalid restore transaction journal")
            elif saved != before:
                raise ValueError("invalid restore transaction journal")
        cache.validate_links()
        return {
            "cache": cache,
            "stage_fd": stage_fd,
            "backup_fd": backup_fd,
            "stage_identity": stage_identity,
            "backup_identity": backup_identity,
        }
    except (OSError, TypeError, ValueError) as error:
        cache.close()
        _close_quietly(stage_fd)
        _close_quietly(backup_fd)
        if (
            isinstance(error, ValueError)
            and str(error) == "invalid restore transaction journal"
        ):
            raise
        raise ValueError("invalid restore transaction journal") from error


def _write_journal(
    destination_fd: int, transaction: dict
) -> Tuple[int, int]:
    """Atomically publish a journal through the destination descriptor."""
    _validate_journal_schema(transaction, transaction["destination"])
    payload = json.dumps(transaction, sort_keys=True).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        descriptor = os.open(
            _JOURNAL_TEMP_NAME, flags, 0o600, dir_fd=destination_fd
        )
    except FileExistsError as error:
        raise ValueError("journal temporary already exists") from error
    except OSError as error:
        raise ValueError("could not create journal temporary") from error
    renamed = False
    written_identity = _identity(os.fstat(descriptor))
    try:
        _write_all(descriptor, payload)
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
        if _identity(os.fstat(descriptor)) != written_identity:
            raise ValueError("journal temporary changed during write")
        os.close(descriptor)
        descriptor = -1
        try:
            os.rename(
                _JOURNAL_TEMP_NAME,
                _JOURNAL_NAME,
                src_dir_fd=destination_fd,
                dst_dir_fd=destination_fd,
            )
            renamed = True
            _fsync_directory_fd(destination_fd)
        except Exception as error:
            if renamed:
                raise _JournalPublicationUncertain() from error
            raise
    finally:
        _close_quietly(descriptor)
        if not renamed:
            details = _stat_optional(destination_fd, _JOURNAL_TEMP_NAME)
            if (
                details is not None
                and stat.S_ISREG(details.st_mode)
                and _identity(details) == written_identity
            ):
                _unlink_durable(destination_fd, _JOURNAL_TEMP_NAME)
    published = _stat_required(destination_fd, _JOURNAL_NAME)
    if (
        _identity(published) != written_identity
        or not stat.S_ISREG(published.st_mode)
    ):
        raise _JournalPublicationUncertain(
            "restore journal changed during publication"
        )
    return written_identity


def _read_journal(
    destination_fd: int, destination_text: str
) -> Tuple[dict, Tuple[int, int]]:
    try:
        descriptor = os.open(
            _JOURNAL_NAME,
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=destination_fd,
        )
    except OSError as error:
        raise ValueError("invalid restore transaction journal") from error
    try:
        details = os.fstat(descriptor)
        if (
            not stat.S_ISREG(details.st_mode)
            or stat.S_IMODE(details.st_mode) != 0o600
        ):
            raise ValueError("invalid restore transaction journal")
        value = json.loads(_read_all(descriptor).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid restore transaction journal") from error
    finally:
        os.close(descriptor)
    _validate_journal_schema(value, destination_text)
    return value, _identity(details)


def _validate_journal_schema(value: object, destination_text: str) -> None:
    required = {
        "version", "status", "stage", "backup", "entries", "parents",
        "expected", "destination", "snapshot",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("invalid restore transaction journal")
    version = value.get("version")
    status = value.get("status")
    if type(version) is not int or version not in {1, 2}:
        raise ValueError("invalid restore transaction journal")
    if (
        not isinstance(status, str)
        or _has_control(status)
        or status not in {"prepared", "committed"}
    ):
        raise ValueError("invalid restore transaction journal")
    if (
        not isinstance(value.get("entries"), list)
        or not isinstance(value.get("parents"), list)
    ):
        raise ValueError("invalid restore transaction journal")
    if (
        not _clean_string(value.get("destination"))
        or value["destination"] != destination_text
    ):
        raise ValueError("invalid restore transaction journal")
    if (
        not _clean_string(value.get("snapshot"))
        or not _ID_PATTERN.fullmatch(value["snapshot"])
    ):
        raise ValueError("invalid restore transaction journal")
    if (
        not isinstance(value.get("expected"), str)
        or not _HASH_PATTERN.fullmatch(value["expected"])
    ):
        raise ValueError("invalid restore transaction journal")
    for key, prefix in (
        ("stage", ".kingstack-restore-stage-"),
        ("backup", ".kingstack-restore-backup-"),
    ):
        name = value.get(key)
        if (
            not _clean_string(name)
            or not name.startswith(prefix)
            or not _TRANSACTION_NAME_PATTERN.fullmatch(name)
        ):
            raise ValueError("invalid restore transaction journal")
    if value["stage"] == value["backup"]:
        raise ValueError("invalid restore transaction journal")

    targets = set()  # type: Set[str]
    backups = set()  # type: Set[str]
    entry_keys = (
        {"target", "backup", "before"}
        if version == 1
        else {"target", "backup", "before", "after"}
    )
    for entry in value["entries"]:
        if not isinstance(entry, dict) or set(entry) != entry_keys:
            raise ValueError("invalid restore transaction journal")
        target = entry.get("target")
        backup = entry.get("backup")
        if (
            not _valid_journal_relative(target)
            or not isinstance(backup, str)
            or not backup.isdigit()
        ):
            raise ValueError("invalid restore transaction journal")
        if target in targets or backup in backups:
            raise ValueError("invalid restore transaction journal")
        targets.add(target)
        backups.add(backup)
        if not _valid_state(entry.get("before"), target_state=True):
            raise ValueError("invalid restore transaction journal")
        if version == 2 and not _valid_state(
            entry.get("after"), target_state=True, restored=True
        ):
            raise ValueError("invalid restore transaction journal")

    parents = set()  # type: Set[str]
    for parent in value["parents"]:
        if (
            not isinstance(parent, dict)
            or set(parent) != {"path", "before"}
        ):
            raise ValueError("invalid restore transaction journal")
        relative = parent.get("path")
        if (
            not _valid_journal_relative(relative, allow_namespace_root=True)
            or relative in parents
        ):
            raise ValueError("invalid restore transaction journal")
        parents.add(relative)
        if not _valid_state(parent.get("before"), parent_state=True):
            raise ValueError("invalid restore transaction journal")
    expected_parents = set(_parent_relative_paths(sorted(targets)))
    if parents != expected_parents:
        raise ValueError("invalid restore transaction journal")


def _current_destination_hash_fd(
    snapshot_fd: int,
    destination_fd: Optional[int],
    records: List[dict],
    cache: Optional[_DirectoryCache] = None,
) -> str:
    del snapshot_fd
    target_names = [
        (record["path"], _destination_relative_text(record["path"]))
        for record in records
    ]
    parents = _parent_relative_paths(
        [relative for _, relative in target_names]
    )
    state = []
    for manifest_path, relative in target_names:
        if destination_fd is None:
            described = {"kind": "missing"}
        elif cache is not None:
            described = _describe_relative_cached(cache, relative)
        else:
            described = _describe_relative(destination_fd, relative)
        state.append({
            "role": "target",
            "path": manifest_path,
            "state": described,
        })
    for relative in parents:
        if destination_fd is None:
            described = {"kind": "missing"}
        elif cache is not None:
            described = _describe_relative_cached(cache, relative)
        else:
            described = _describe_relative(destination_fd, relative)
        state.append({
            "role": "parent",
            "path": relative,
            "state": described,
        })
    payload = json.dumps(
        state, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _open_selected_source_roots(paths: Paths) -> List[dict]:
    roots = []
    try:
        for namespace, root_path, includes in (
            ("claude", paths.claude_home, CLAUDE_INCLUDE),
            ("codex", paths.codex_home, CODEX_INCLUDE),
        ):
            descriptor, _ = _open_absolute_directory(
                root_path, create=False, private=False
            )
            if descriptor is None:
                continue
            root = {
                "namespace": namespace,
                "path": root_path,
                "fd": descriptor,
                "identity": _identity(os.fstat(descriptor)),
                "entries": [],
            }
            roots.append(root)
            root["entries"] = _select_source_entries(
                namespace, descriptor, includes
            )
        return roots
    except Exception:
        for root in roots:
            _close_quietly(root["fd"])
        raise


def _select_source_entries(
    namespace: str, root_fd: int, includes: Iterable[str]
) -> List[dict]:
    found = {}  # type: Dict[Tuple[str, ...], dict]
    for pattern in includes:
        directory_pattern = pattern.endswith("/")
        parts = tuple(
            part for part in pattern.rstrip("/").split("/") if part
        )
        _select_pattern(
            namespace,
            root_fd,
            root_fd,
            (),
            parts,
            directory_pattern,
            found,
        )
    return [found[key] for key in sorted(found)]


def _select_pattern(
    namespace: str,
    root_fd: int,
    directory_fd: int,
    prefix: Tuple[str, ...],
    pattern: Tuple[str, ...],
    directory_pattern: bool,
    found: Dict[Tuple[str, ...], dict],
) -> None:
    if not pattern:
        return
    segment = pattern[0]
    try:
        names = sorted(os.listdir(directory_fd))
    except OSError as error:
        raise ValueError("could not traverse snapshot source") from error
    for name in names:
        if not fnmatch.fnmatchcase(name, segment):
            continue
        parts = prefix + (name,)
        details = _stat_required(directory_fd, name)
        if len(pattern) > 1:
            if not stat.S_ISDIR(details.st_mode):
                continue
            child_fd = _open_child_directory(directory_fd, name)
            try:
                _select_pattern(
                    namespace,
                    root_fd,
                    child_fd,
                    parts,
                    pattern[1:],
                    directory_pattern,
                    found,
                )
            finally:
                os.close(child_fd)
            continue
        path_text = namespace + "/" + "/".join(parts)
        if directory_pattern:
            _assert_safe_manifest_path(path_text)
            if stat.S_ISLNK(details.st_mode):
                found[parts] = _source_entry(
                    namespace, root_fd, parts, details
                )
            elif stat.S_ISDIR(details.st_mode):
                child_fd = _open_child_directory(directory_fd, name)
                try:
                    _collect_selected_directory(
                        namespace, root_fd, child_fd, parts, found
                    )
                finally:
                    os.close(child_fd)
            else:
                raise ValueError(
                    "refusing non-regular snapshot source: "
                    + "/".join(parts)
                )
        elif stat.S_ISREG(details.st_mode) or stat.S_ISLNK(details.st_mode):
            _assert_safe_manifest_path(path_text)
            found[parts] = _source_entry(
                namespace, root_fd, parts, details
            )
        elif not stat.S_ISDIR(details.st_mode):
            raise ValueError(
                "refusing non-regular snapshot source: " + "/".join(parts)
            )


def _collect_selected_directory(
    namespace: str,
    root_fd: int,
    directory_fd: int,
    prefix: Tuple[str, ...],
    found: Dict[Tuple[str, ...], dict],
) -> None:
    try:
        names = sorted(os.listdir(directory_fd))
    except OSError as error:
        raise ValueError("could not traverse snapshot source") from error
    for name in names:
        parts = prefix + (name,)
        _assert_safe_manifest_path(namespace + "/" + "/".join(parts))
        details = _stat_required(directory_fd, name)
        if stat.S_ISDIR(details.st_mode):
            child_fd = _open_child_directory(directory_fd, name)
            try:
                _collect_selected_directory(
                    namespace, root_fd, child_fd, parts, found
                )
            finally:
                os.close(child_fd)
        elif stat.S_ISREG(details.st_mode) or stat.S_ISLNK(details.st_mode):
            found[parts] = _source_entry(
                namespace, root_fd, parts, details
            )
        else:
            raise ValueError(
                "refusing non-regular snapshot source: " + "/".join(parts)
            )


def _source_entry(
    namespace: str,
    root_fd: int,
    parts: Tuple[str, ...],
    details: os.stat_result,
) -> dict:
    return {
        "namespace": namespace,
        "root_fd": root_fd,
        "parts": parts,
        "identity": _identity(details),
        "mtime_ns": details.st_mtime_ns,
        "size": details.st_size,
        "mode": details.st_mode,
    }


def _copy_source_entry(
    source: dict,
    destination_parent_fd: int,
    destination_name: str,
    path_text: str,
) -> dict:
    source_parent_fd = _open_relative_directory(
        source["root_fd"], source["parts"][:-1]
    )
    try:
        name = source["parts"][-1]
        details = _stat_required(source_parent_fd, name)
        if _identity(details) != source["identity"]:
            raise ValueError(
                "source changed while creating snapshot: " + path_text
            )
        if stat.S_ISLNK(details.st_mode):
            target = os.readlink(name, dir_fd=source_parent_fd)
            if not _clean_string(target):
                raise ValueError("invalid source symlink target: " + path_text)
            after = _stat_required(source_parent_fd, name)
            if (
                _identity(after) != source["identity"]
                or not stat.S_ISLNK(after.st_mode)
            ):
                raise ValueError(
                    "source changed while creating snapshot: " + path_text
                )
            try:
                os.symlink(
                    target, destination_name, dir_fd=destination_parent_fd
                )
            except OSError as error:
                raise ValueError(
                    "could not store snapshot symlink: " + path_text
                ) from error
            _fsync_directory_fd(destination_parent_fd)
            return {
                "path": path_text,
                "kind": "symlink",
                "sha256": None,
                "mode": None,
                "target": target,
            }
        if not stat.S_ISREG(details.st_mode):
            raise ValueError(
                "refusing non-regular snapshot source: " + path_text
            )
        source_fd = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=source_parent_fd
        )
        destination_fd = -1
        try:
            opened = os.fstat(source_fd)
            if (
                not stat.S_ISREG(opened.st_mode)
                or _identity(opened) != source["identity"]
            ):
                raise ValueError(
                    "source changed while creating snapshot: " + path_text
                )
            destination_fd = os.open(
                destination_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=destination_parent_fd,
            )
            digest = hashlib.sha256()
            while True:
                chunk = os.read(source_fd, 65536)
                if not chunk:
                    break
                digest.update(chunk)
                _write_all(destination_fd, chunk)
            final_source = os.fstat(source_fd)
            if (
                _identity(final_source) != source["identity"]
                or final_source.st_mtime_ns != source["mtime_ns"]
                or final_source.st_size != source["size"]
            ):
                raise ValueError(
                    "source changed while creating snapshot: " + path_text
                )
            mode = 0o700 if opened.st_mode & stat.S_IXUSR else 0o600
            os.fchmod(destination_fd, mode)
            os.fsync(destination_fd)
        finally:
            os.close(source_fd)
            _close_quietly(destination_fd)
        _fsync_directory_fd(destination_parent_fd)
        return {
            "path": path_text,
            "kind": "file",
            "sha256": digest.hexdigest(),
            "mode": format(mode, "04o"),
            "target": None,
        }
    finally:
        os.close(source_parent_fd)


def _verify_snapshot_fd(snapshot_fd: int, check_permissions: bool) -> List[str]:
    try:
        manifest = _read_manifest_fd(snapshot_fd)
    except ValueError as error:
        return [str(error)]
    problems = _manifest_problems(manifest)
    records = (
        manifest.get("files")
        if isinstance(manifest.get("files"), list) else []
    )
    expected = _expected_tree(records)
    actual, tree_problems = _actual_tree_fd(snapshot_fd)
    problems.extend(tree_problems)
    for relative, kind in actual.items():
        if expected.get(relative) != kind:
            problems.append("unexpected snapshot entry: " + relative)
    for relative, kind in expected.items():
        if actual.get(relative) != kind:
            problems.append("missing or wrong snapshot entry: " + relative)
    if check_permissions:
        problems.extend(
            _permission_problems_fd(
                snapshot_fd, actual, expected, records
            )
        )
    for record in records:
        if not _record_is_usable(record):
            continue
        relative = "files/" + record["path"]
        if actual.get(relative) != record["kind"]:
            continue
        parts = PurePosixPath(relative).parts
        parent_fd = None
        try:
            parent_fd = _open_relative_directory(snapshot_fd, parts[:-1])
            if (
                record["kind"] == "file"
                and _hash_file_at(parent_fd, parts[-1]) != record["sha256"]
            ):
                problems.append("hash mismatch: " + record["path"])
            if (
                record["kind"] == "symlink"
                and os.readlink(parts[-1], dir_fd=parent_fd)
                != record["target"]
            ):
                problems.append(
                    "symlink target mismatch: " + record["path"]
                )
        except (OSError, ValueError):
            problems.append("invalid snapshot entry: " + record["path"])
        finally:
            _close_quietly(parent_fd)
    return sorted(set(problems))


def _read_manifest_fd(snapshot_fd: int) -> dict:
    details = _stat_optional(snapshot_fd, "manifest.json")
    if details is None or not stat.S_ISREG(details.st_mode):
        raise ValueError("invalid snapshot manifest")
    try:
        descriptor = os.open(
            "manifest.json",
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=snapshot_fd,
        )
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or _identity(opened) != _identity(details)
            ):
                raise ValueError("invalid snapshot manifest")
            value = json.loads(_read_all(descriptor).decode("utf-8"))
        finally:
            os.close(descriptor)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid snapshot manifest") from error
    if (
        not isinstance(value, dict)
        or type(value.get("version")) is not int
        or value.get("version") != SNAPSHOT_VERSION
    ):
        raise ValueError("unsupported snapshot manifest")
    return value


def _manifest_problems(manifest: dict) -> List[str]:
    problems = []
    if set(manifest) != {"version", "label", "files"}:
        problems.append("invalid snapshot manifest")
    label = manifest.get("label")
    if not isinstance(label, str) or not _LABEL_PATTERN.fullmatch(label):
        problems.append("invalid snapshot manifest")
    records = manifest.get("files")
    if not isinstance(records, list):
        return problems + ["invalid snapshot manifest files"]
    seen = set()  # type: Set[str]
    for record in records:
        if (
            not isinstance(record, dict)
            or set(record) != {"path", "kind", "sha256", "mode", "target"}
        ):
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
        kind = record.get("kind")
        if not isinstance(kind, str) or _has_control(kind):
            problems.append("invalid snapshot manifest kind")
            continue
        if kind == "file":
            if (
                not isinstance(record.get("sha256"), str)
                or not _HASH_PATTERN.fullmatch(record["sha256"])
            ):
                problems.append("invalid snapshot manifest hash")
            mode = record.get("mode")
            if (
                not isinstance(mode, str)
                or mode not in {"0600", "0700"}
                or record.get("target") is not None
            ):
                problems.append("invalid snapshot manifest file mode")
        elif kind == "symlink":
            if (
                record.get("sha256") is not None
                or record.get("mode") is not None
                or not _clean_string(record.get("target"))
            ):
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
        relative = "files/" + record["path"]
        expected[relative] = record["kind"]
        parts = relative.split("/")[:-1]
        while parts:
            expected["/".join(parts)] = "dir"
            parts.pop()
    return expected


def _actual_tree_fd(snapshot_fd: int) -> Tuple[Dict[str, str], List[str]]:
    actual = {".": "dir"}
    problems = []

    def visit(directory_fd: int, prefix: str) -> None:
        try:
            names = sorted(os.listdir(directory_fd))
        except OSError:
            problems.append("invalid snapshot directory: " + (prefix or "."))
            return
        for name in names:
            relative = name if not prefix else prefix + "/" + name
            try:
                details = _stat_required(directory_fd, name)
            except ValueError:
                actual[relative] = "other"
                continue
            if stat.S_ISDIR(details.st_mode):
                actual[relative] = "dir"
                try:
                    child_fd = _open_child_directory(directory_fd, name)
                except (OSError, ValueError):
                    problems.append(
                        "symlinked or invalid snapshot directory: " + relative
                    )
                    continue
                try:
                    visit(child_fd, relative)
                finally:
                    os.close(child_fd)
            elif stat.S_ISLNK(details.st_mode):
                actual[relative] = "symlink"
            elif stat.S_ISREG(details.st_mode):
                actual[relative] = "file"
            else:
                actual[relative] = "other"

    visit(snapshot_fd, "")
    if actual.get("files") == "symlink":
        problems.append("symlinked snapshot entry: files")
    return actual, problems


def _permission_problems_fd(
    snapshot_fd: int,
    actual: Dict[str, str],
    expected: Dict[str, str],
    records: object,
) -> List[str]:
    problems = []
    for relative, kind in expected.items():
        if actual.get(relative) != kind:
            continue
        try:
            details = (
                os.fstat(snapshot_fd)
                if relative == "."
                else _stat_relative(snapshot_fd, relative)
            )
            mode = stat.S_IMODE(details.st_mode)
        except (OSError, ValueError):
            continue
        if kind == "dir" and mode != 0o700:
            problems.append(
                "private directory permission mismatch: " + relative
            )
        elif relative == "manifest.json" and mode != 0o600:
            problems.append("permission mismatch: manifest.json")
    if isinstance(records, list):
        for record in records:
            if not (
                _record_is_usable(record) and record["kind"] == "file"
            ):
                continue
            relative = "files/" + record["path"]
            if actual.get(relative) != "file":
                continue
            try:
                mode = stat.S_IMODE(
                    _stat_relative(snapshot_fd, relative).st_mode
                )
            except (OSError, ValueError):
                continue
            if mode != int(record["mode"], 8):
                problems.append("permission mismatch: " + record["path"])
    return problems


def _record_is_usable(record: object) -> bool:
    if (
        not isinstance(record, dict)
        or set(record) != {"path", "kind", "sha256", "mode", "target"}
    ):
        return False
    try:
        _assert_safe_manifest_path(record.get("path"))
    except (TypeError, ValueError):
        return False
    kind = record.get("kind")
    if not isinstance(kind, str):
        return False
    if kind == "file":
        mode = record.get("mode")
        return (
            isinstance(record.get("sha256"), str)
            and bool(_HASH_PATTERN.fullmatch(record["sha256"]))
            and isinstance(mode, str)
            and mode in {"0600", "0700"}
            and record.get("target") is None
        )
    return (
        kind == "symlink"
        and record.get("sha256") is None
        and record.get("mode") is None
        and _clean_string(record.get("target"))
    )


def _assert_safe_manifest_path(path: object) -> None:
    if (
        not _clean_string(path)
        or "\\" in path
        or path != str(PurePosixPath(path))
    ):
        raise ValueError("invalid snapshot manifest path")
    relative = PurePosixPath(path)
    if (
        relative.is_absolute()
        or len(relative.parts) < 2
        or relative.parts[0] not in {"claude", "codex"}
    ):
        raise ValueError("invalid snapshot manifest path")
    if (
        any(part in {"", ".", ".."} for part in relative.parts)
        or _path_is_denylisted(path)
    ):
        raise ValueError("denylisted snapshot manifest path")


def _path_is_denylisted(path: str) -> bool:
    for part in PurePosixPath(path).parts:
        lowered = part.lower()
        pure = PurePosixPath(lowered)
        if (
            lowered in _DENYLISTED_NAMES
            or pure.stem in _DENYLISTED_NAMES
            or pure.suffix in _DENYLISTED_SUFFIXES
        ):
            return True
    return False


def _destination_relative(path_text: str) -> Path:
    return Path(_destination_relative_text(path_text))


def _destination_relative_text(path_text: str) -> str:
    _assert_safe_manifest_path(path_text)
    relative = PurePosixPath(path_text)
    return "." + relative.parts[0] + "/" + "/".join(relative.parts[1:])


def _parent_relative_paths(targets: List[str]) -> List[str]:
    parents = set()  # type: Set[str]
    for target in targets:
        parts = list(PurePosixPath(target).parts[:-1])
        while parts:
            parents.add("/".join(parts))
            parts.pop()
    return sorted(parents, key=lambda item: (item.count("/"), item))


def _valid_journal_relative(
    path: object, allow_namespace_root: bool = False
) -> bool:
    if (
        not _clean_string(path)
        or "\\" in path
        or path != str(PurePosixPath(path))
    ):
        return False
    relative = PurePosixPath(path)
    if (
        relative.is_absolute()
        or len(relative.parts) < 1
        or relative.parts[0] not in {".claude", ".codex"}
    ):
        return False
    if any(part in {"", ".", ".."} for part in relative.parts):
        return False
    if len(relative.parts) == 1:
        return allow_namespace_root
    manifest_path = (
        relative.parts[0][1:] + "/" + "/".join(relative.parts[1:])
    )
    try:
        _assert_safe_manifest_path(manifest_path)
    except ValueError:
        return False
    return True


def _valid_state(
    value: object,
    target_state: bool = False,
    parent_state: bool = False,
    restored: bool = False,
) -> bool:
    if not isinstance(value, dict):
        return False
    kind = value.get("kind")
    if not isinstance(kind, str) or _has_control(kind):
        return False
    if kind == "missing":
        return set(value) == {"kind"} and not restored
    if kind == "symlink":
        return (
            target_state
            and set(value) == {"kind", "target"}
            and _clean_string(value.get("target"))
        )
    if kind == "file":
        return (
            target_state
            and set(value) == {"kind", "sha256", "mode"}
            and isinstance(value.get("sha256"), str)
            and bool(_HASH_PATTERN.fullmatch(value["sha256"]))
            and isinstance(value.get("mode"), str)
            and bool(_MODE_PATTERN.fullmatch(value["mode"]))
        )
    if kind == "dir":
        return (
            parent_state
            and set(value) == {"kind", "mode"}
            and isinstance(value.get("mode"), str)
            and bool(_MODE_PATTERN.fullmatch(value["mode"]))
        )
    return False


def _stage_snapshot_record(
    snapshot_fd: int, record: dict, stage_fd: int, stage_name: str
) -> dict:
    relative = "files/" + record["path"]
    parts = PurePosixPath(relative).parts
    parent_fd = _open_relative_directory(snapshot_fd, parts[:-1])
    try:
        if record["kind"] == "symlink":
            details = _stat_required(parent_fd, parts[-1])
            if not stat.S_ISLNK(details.st_mode):
                raise ValueError("invalid snapshot payload during staging")
            target = os.readlink(parts[-1], dir_fd=parent_fd)
            if target != record["target"]:
                raise ValueError("snapshot symlink changed during staging")
            os.symlink(target, stage_name, dir_fd=stage_fd)
            _fsync_directory_fd(stage_fd)
            return {"kind": "symlink", "target": target}
        source_fd = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd
        )
        destination_file_fd = -1
        digest = hashlib.sha256()
        try:
            if not stat.S_ISREG(os.fstat(source_fd).st_mode):
                raise ValueError("invalid snapshot payload during staging")
            destination_file_fd = os.open(
                stage_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=stage_fd,
            )
            while True:
                chunk = os.read(source_fd, 65536)
                if not chunk:
                    break
                digest.update(chunk)
                _write_all(destination_file_fd, chunk)
            if digest.hexdigest() != record["sha256"]:
                raise ValueError("snapshot payload changed during staging")
            mode = int(record["mode"], 8)
            os.fchmod(destination_file_fd, mode)
            os.fsync(destination_file_fd)
        finally:
            os.close(source_fd)
            _close_quietly(destination_file_fd)
        _fsync_directory_fd(stage_fd)
        return {
            "kind": "file",
            "sha256": digest.hexdigest(),
            "mode": record["mode"],
        }
    finally:
        os.close(parent_fd)


def _describe_relative(root_fd: int, relative: str) -> dict:
    parts = PurePosixPath(relative).parts
    try:
        parent_fd = _open_relative_directory(root_fd, parts[:-1])
    except FileNotFoundError:
        return {"kind": "missing"}
    except (OSError, ValueError):
        return {"kind": "blocked"}
    try:
        return _describe_at(parent_fd, parts[-1])
    finally:
        os.close(parent_fd)


def _describe_relative_cached(
    cache: _DirectoryCache, relative: str
) -> dict:
    parent, name = _split_relative(relative)
    try:
        parent_fd = cache.existing(parent)
    except ValueError:
        return {"kind": "blocked"}
    if parent_fd is None:
        return {"kind": "missing"}
    return _describe_at(parent_fd, name)


def _describe_at(parent_fd: Optional[int], name: str) -> dict:
    if parent_fd is None:
        return {"kind": "missing"}
    details = _stat_optional(parent_fd, name)
    if details is None:
        return {"kind": "missing"}
    mode = format(stat.S_IMODE(details.st_mode), "04o")
    if stat.S_ISLNK(details.st_mode):
        try:
            target = os.readlink(name, dir_fd=parent_fd)
            after = _stat_required(parent_fd, name)
        except (OSError, ValueError) as error:
            raise ValueError(
                "filesystem entry changed while describing state"
            ) from error
        if (
            _identity(after) != _identity(details)
            or not stat.S_ISLNK(after.st_mode)
        ):
            raise ValueError("filesystem entry changed while describing state")
        return {"kind": "symlink", "target": target}
    if stat.S_ISREG(details.st_mode):
        return {
            "kind": "file",
            "sha256": _hash_file_at(parent_fd, name),
            "mode": mode,
        }
    if stat.S_ISDIR(details.st_mode):
        return {"kind": "dir", "mode": mode}
    return {"kind": "other", "mode": mode}


def _hash_file_at(parent_fd: int, name: str) -> str:
    descriptor = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd
    )
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("refusing non-regular hash source")
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _stat_relative(root_fd: int, relative: str) -> os.stat_result:
    parts = PurePosixPath(relative).parts
    parent_fd = _open_relative_directory(root_fd, parts[:-1])
    try:
        return _stat_required(parent_fd, parts[-1])
    finally:
        os.close(parent_fd)


def _open_relative_directory(
    root_fd: int, parts: Tuple[str, ...]
) -> int:
    descriptor = os.dup(root_fd)
    try:
        for part in parts:
            child = _open_child_directory(descriptor, part)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _open_absolute_directory(
    path: Path, create: bool, private: bool
) -> Tuple[Optional[int], str]:
    _require_primitives()
    parts, canonical = _absolute_parts(path)
    descriptor = os.open(
        "/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    )
    try:
        for index, part in enumerate(parts):
            details = _stat_optional(descriptor, part)
            if details is None:
                if not create:
                    os.close(descriptor)
                    return None, canonical
                _mkdir_durable(
                    descriptor, part, 0o700 if private else 0o755
                )
            elif not stat.S_ISDIR(details.st_mode):
                raise ValueError(
                    "refusing symlinked or invalid directory ancestor: "
                    + canonical
                )
            child = _open_child_directory(descriptor, part)
            os.close(descriptor)
            descriptor = child
            if private and index == len(parts) - 1:
                os.fchmod(descriptor, 0o700)
                _fsync_directory_fd(descriptor)
        return descriptor, canonical
    except Exception:
        _close_quietly(descriptor)
        raise


def _absolute_parts(path: Path) -> Tuple[Tuple[str, ...], str]:
    text = os.path.abspath(os.fspath(Path(path).expanduser()))
    if not _clean_string(text):
        raise ValueError("invalid filesystem path")
    pure = PurePosixPath(text)
    parts = list(pure.parts[1:])
    if (
        parts
        and parts[0] in {"var", "tmp", "etc"}
        and os.uname().sysname == "Darwin"
    ):
        parts.insert(0, "private")
    canonical = "/" + "/".join(parts)
    return tuple(parts), canonical


def _verify_open_path_identity(
    path: Path, expected_fd: int, message: str
) -> None:
    try:
        descriptor, _ = _open_absolute_directory(
            path, create=False, private=False
        )
    except (OSError, ValueError) as error:
        raise ValueError(message) from error
    if descriptor is None:
        raise ValueError(message)
    try:
        if _identity(os.fstat(descriptor)) != _identity(os.fstat(expected_fd)):
            raise ValueError(message)
    finally:
        os.close(descriptor)


def _open_child_directory(parent_fd: int, name: str) -> int:
    _require_primitives()
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        dir_fd=parent_fd,
    )
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("refusing non-directory anchor")
    return descriptor


def _create_private_child_directory(parent_fd: int, name: str) -> int:
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
    except FileExistsError as error:
        raise ValueError(
            "restore transaction directory already exists"
        ) from error
    descriptor = _open_child_directory(parent_fd, name)
    os.fchmod(descriptor, 0o700)
    _fsync_directory_fd(descriptor)
    _fsync_directory_fd(parent_fd)
    return descriptor


def _mkdir_durable(parent_fd: int, name: str, mode: int) -> None:
    try:
        os.mkdir(name, mode, dir_fd=parent_fd)
    except OSError as error:
        raise ValueError("could not create directory entry") from error
    child_fd = _open_child_directory(parent_fd, name)
    try:
        os.fchmod(child_fd, mode)
        _fsync_directory_fd(child_fd)
    finally:
        os.close(child_fd)
    _fsync_directory_fd(parent_fd)


def _open_optional_transaction_directory(
    destination_fd: int, name: str
) -> Tuple[Optional[int], Optional[Tuple[int, int]]]:
    details = _stat_optional(destination_fd, name)
    if details is None:
        return None, None
    if not stat.S_ISDIR(details.st_mode):
        raise ValueError("invalid restore transaction journal")
    descriptor = _open_child_directory(destination_fd, name)
    opened_identity = _identity(os.fstat(descriptor))
    if opened_identity != _identity(details):
        os.close(descriptor)
        raise ValueError("invalid restore transaction journal")
    return descriptor, opened_identity


def _write_new_regular_at(
    parent_fd: int, name: str, payload: bytes, mode: int
) -> None:
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        mode,
        dir_fd=parent_fd,
    )
    try:
        _write_all(descriptor, payload)
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory_fd(parent_fd)


def _rename_durable(
    source_fd: int, source: str, target_fd: int, target: str
) -> None:
    os.rename(
        source,
        target,
        src_dir_fd=source_fd,
        dst_dir_fd=target_fd,
    )
    if _identity(os.fstat(source_fd)) == _identity(os.fstat(target_fd)):
        _fsync_directory_fd(source_fd)
        return
    # Persist the new name before the old name's removal. If power is lost
    # between these fsyncs, recovery still has at least one durable link to the
    # inode rather than a durable deletion with an uncommitted destination.
    _fsync_directory_fd(target_fd)
    _fsync_directory_fd(source_fd)


def _unlink_durable(parent_fd: int, name: str) -> None:
    os.unlink(name, dir_fd=parent_fd)
    _fsync_directory_fd(parent_fd)


def _remove_tree_if_identity(
    parent_fd: int,
    name: str,
    expected: Optional[Tuple[int, int]],
) -> None:
    details = _stat_optional(parent_fd, name)
    if details is None:
        return
    if expected is None:
        raise ValueError("transaction directory appeared during cleanup")
    if expected is not None and _identity(details) != expected:
        raise ValueError("transaction directory changed during cleanup")
    if not stat.S_ISDIR(details.st_mode):
        raise ValueError("invalid transaction directory during cleanup")
    _remove_tree_at(parent_fd, name, _identity(details))


def _remove_retained_tree_if_identity(
    parent_fd: int,
    name: str,
    expected: Optional[Tuple[int, int]],
    directory_fd: Optional[int],
) -> None:
    """Empty the validated inode before requiring its original name for rmdir."""
    if directory_fd is None:
        _remove_tree_if_identity(parent_fd, name, expected)
        return
    opened = os.fstat(directory_fd)
    if (
        expected is None
        or not stat.S_ISDIR(opened.st_mode)
        or _identity(opened) != expected
    ):
        raise ValueError("transaction directory changed during cleanup")
    _empty_directory_fd(directory_fd)
    _fsync_directory_fd(directory_fd)
    linked = _stat_optional(parent_fd, name)
    if (
        linked is None
        or not stat.S_ISDIR(linked.st_mode)
        or _identity(linked) != expected
    ):
        raise ValueError("transaction directory changed during cleanup")
    _remove_tree_if_identity(parent_fd, name, expected)


def _remove_tree_at(
    parent_fd: int, name: str, expected: Tuple[int, int]
) -> None:
    directory_fd = _open_child_directory(parent_fd, name)
    try:
        if _identity(os.fstat(directory_fd)) != expected:
            raise ValueError("directory changed during cleanup")
        _empty_directory_fd(directory_fd)
        details = _stat_optional(parent_fd, name)
        if (
            details is None
            or _identity(details) != expected
            or not stat.S_ISDIR(details.st_mode)
        ):
            raise ValueError("directory changed during cleanup")
    finally:
        os.close(directory_fd)
    os.rmdir(name, dir_fd=parent_fd)
    _fsync_directory_fd(parent_fd)


def _empty_directory_fd(directory_fd: int) -> None:
    for name in sorted(os.listdir(directory_fd)):
        details = _stat_required(directory_fd, name)
        if stat.S_ISDIR(details.st_mode):
            _remove_tree_at(directory_fd, name, _identity(details))
        else:
            os.unlink(name, dir_fd=directory_fd)
            _fsync_directory_fd(directory_fd)


def _fsync_directory_fd(descriptor: int) -> None:
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        raise ValueError("refusing non-directory durability target")
    os.fsync(descriptor)


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("short write")
        offset += written


def _read_all(descriptor: int) -> bytes:
    chunks = []
    while True:
        chunk = os.read(descriptor, 65536)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _stat_optional(
    parent_fd: int, name: str
) -> Optional[os.stat_result]:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as error:
        if error.errno == errno.ENOENT:
            return None
        raise


def _stat_required(parent_fd: int, name: str) -> os.stat_result:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as error:
        raise ValueError("could not inspect filesystem entry") from error


def _identity(details: os.stat_result) -> Tuple[int, int]:
    return details.st_dev, details.st_ino


def _split_relative(relative: str) -> Tuple[str, str]:
    parts = PurePosixPath(relative).parts
    return "/".join(parts[:-1]), parts[-1]


def _has_control(value: str) -> bool:
    return any(
        unicodedata.category(character) == "Cc" for character in value
    )


def _clean_string(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not _has_control(value)
    )


def _close_quietly(descriptor: object) -> None:
    if not isinstance(descriptor, int) or descriptor < 0:
        return
    try:
        os.close(descriptor)
    except OSError:
        pass


def _require_primitives() -> None:
    if not _REQUIRED_PRIMITIVES_AVAILABLE:
        raise ValueError(
            "platform lacks required descriptor-relative no-follow primitives"
        )
