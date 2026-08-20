"""Deterministic, descriptor-confined rendering for agent instruction files."""

import errno
import json
import os
from pathlib import Path
import stat
from typing import Any, List, Tuple

from kingstack.adapter_contract import (
    ADAPTER_ID_PATTERN,
    AdapterContractError,
    load_adapter_document,
    load_capability_catalog_document,
    validate_adapter,
)


class RenderError(ValueError):
    """Raised when instruction sources or staged output violate the contract."""


_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY_FLAGS = os.O_RDONLY | _DIRECTORY


def _require_descriptor_guards() -> None:
    if not _NOFOLLOW or not _DIRECTORY:
        raise RenderError("this platform lacks descriptor no-follow directory guards")


def _open_root(root: Path) -> int:
    _require_descriptor_guards()
    try:
        descriptor = os.open(str(root), _DIRECTORY_FLAGS | _NOFOLLOW)
    except OSError as error:
        raise RenderError("cannot anchor canonical repository: {}".format(error)) from error
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise RenderError("canonical repository is not a directory: {}".format(root))
    return descriptor


def _open_directory_at(parent: int, name: str, label: str) -> int:
    if Path(name).name != name or name in ("", ".", ".."):
        raise RenderError("invalid {} component: {}".format(label, name))
    try:
        descriptor = os.open(
            name, _DIRECTORY_FLAGS | _NOFOLLOW, dir_fd=parent
        )
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise RenderError(
                "{} may not be a symbolic link".format(label)
            ) from error
        if error.errno == errno.ENOTDIR:
            try:
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except OSError:
                current = None
            if current is not None and stat.S_ISLNK(current.st_mode):
                raise RenderError(
                    "{} may not be a symbolic link".format(label)
                ) from error
            raise RenderError("{} is not a directory".format(label)) from error
        raise RenderError("cannot open {}: {}".format(label, error)) from error
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise RenderError("{} is not a directory".format(label))
    return descriptor


def _file_identity(metadata) -> Tuple[int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _read_file_at(
    parent: int, name: str, label: str
) -> Tuple[bytes, Tuple[int, int, int, int, int]]:
    if Path(name).name != name or name in ("", ".", ".."):
        raise RenderError("invalid {} filename: {}".format(label, name))
    try:
        descriptor = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=parent)
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise RenderError("{} may not be a symbolic link".format(label)) from error
        if error.errno == errno.ENOENT:
            raise RenderError("missing {}: {}".format(label, name)) from error
        raise RenderError("cannot open {}: {}".format(label, error)) from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RenderError("{} must be a regular file: {}".format(label, name))
        chunks = []
        while True:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if _file_identity(before) != _file_identity(after):
            raise RenderError("{} changed during render".format(label))
        return b"".join(chunks), _file_identity(after)
    finally:
        os.close(descriptor)


def _decode_utf8(content: bytes, label: str, allow_empty: bool = False) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RenderError("{} must be valid UTF-8".format(label)) from error
    if allow_empty and not content:
        return ""
    if b"\r" in content or not content.endswith(b"\n") or content.endswith(b"\n\n"):
        raise RenderError(
            "{} must use LF endings and exactly one trailing newline: one terminal LF byte".format(
                label
            )
        )
    return text


def _decode_json(content: bytes, label: str) -> Any:
    try:
        return json.loads(content.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise RenderError("{} must be valid UTF-8".format(label)) from error
    except json.JSONDecodeError as error:
        raise RenderError("invalid {}: {}".format(label, error)) from error


def _load_order(content: bytes, fragment_names: List[str]) -> List[str]:
    order = _decode_json(content, "instruction order")
    if not isinstance(order, list) or not all(isinstance(name, str) for name in order):
        raise RenderError("instruction order must be an array of fragment filenames")
    if len(order) != len(set(order)):
        raise RenderError("instruction order contains a duplicate fragment")
    for name in order:
        if Path(name).name != name or not name.endswith(".md"):
            raise RenderError(
                "instruction order contains an invalid fragment name: {}".format(name)
            )
    actual = set(fragment_names)
    listed = set(order)
    missing = sorted(listed - actual)
    unlisted = sorted(actual - listed)
    if missing:
        raise RenderError(
            "instruction order names missing fragments: {}".format(", ".join(missing))
        )
    if unlisted:
        raise RenderError(
            "instruction directory contains unlisted fragments: {}".format(
                ", ".join(unlisted)
            )
        )
    return order


def _identity(metadata) -> Tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _assert_root_identity(root: Path, root_fd: int) -> None:
    try:
        current = os.stat(str(root), follow_symlinks=False)
    except OSError as error:
        raise RenderError("canonical repository changed during render") from error
    if not stat.S_ISDIR(current.st_mode) or _identity(current) != _identity(
        os.fstat(root_fd)
    ):
        raise RenderError("canonical repository changed during render")


def _assert_entry_identity(parent: int, name: str, descriptor: int, label: str) -> None:
    try:
        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except OSError as error:
        raise RenderError("{} changed during render".format(label)) from error
    held = os.fstat(descriptor)
    if not stat.S_ISDIR(current.st_mode) or _identity(current) != _identity(held):
        raise RenderError("{} changed during render".format(label))


def _assert_file_identity(
    parent: int, name: str, expected: Tuple[int, int, int, int, int], label: str
) -> None:
    try:
        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except OSError as error:
        raise RenderError("{} changed during render".format(label)) from error
    if not stat.S_ISREG(current.st_mode) or _file_identity(current) != expected:
        raise RenderError("{} changed during render".format(label))


def _load_declaration(
    adapter: str, root: Path, adapter_bytes: bytes, catalog_bytes: bytes
):
    adapter_document = _decode_json(adapter_bytes, "adapter declaration")
    catalog_document = _decode_json(catalog_bytes, "capability catalog")
    try:
        declaration = load_adapter_document(
            adapter_document, root / "adapters" / adapter / "adapter.json"
        )
        catalog = load_capability_catalog_document(catalog_document)
        errors = validate_adapter(declaration, catalog)
    except AdapterContractError as error:
        raise RenderError("invalid adapter '{}': {}".format(adapter, error)) from error
    if declaration.id != adapter:
        raise RenderError(
            "adapter selector '{}' loaded declaration id '{}'".format(
                adapter, declaration.id
            )
        )
    if errors:
        raise RenderError("invalid adapter '{}': {}".format(adapter, "; ".join(errors)))
    return declaration


def _render_with_declaration(adapter: str, root: Path):
    if not isinstance(adapter, str) or ADAPTER_ID_PATTERN.fullmatch(adapter) is None:
        raise RenderError("adapter must be a stable adapter ID")
    descriptors: List[int] = []
    file_identities = []
    try:
        root_fd = _open_root(root)
        descriptors.append(root_fd)
        core_fd = _open_directory_at(root_fd, "core", "core source directory")
        descriptors.append(core_fd)
        instructions_fd = _open_directory_at(
            core_fd, "instructions", "instruction source directory"
        )
        descriptors.append(instructions_fd)
        capabilities_fd = _open_directory_at(
            core_fd, "capabilities", "capability source directory"
        )
        descriptors.append(capabilities_fd)
        adapters_fd = _open_directory_at(
            root_fd, "adapters", "adapter source directory"
        )
        descriptors.append(adapters_fd)
        adapter_fd = _open_directory_at(
            adapters_fd, adapter, "selected adapter directory"
        )
        descriptors.append(adapter_fd)

        adapter_bytes, identity = _read_file_at(
            adapter_fd, "adapter.json", "adapter declaration"
        )
        file_identities.append(
            (adapter_fd, "adapter.json", identity, "adapter declaration")
        )
        catalog_bytes, identity = _read_file_at(
            capabilities_fd, "catalog.json", "capability catalog"
        )
        file_identities.append(
            (capabilities_fd, "catalog.json", identity, "capability catalog")
        )
        declaration = _load_declaration(adapter, root, adapter_bytes, catalog_bytes)

        order_bytes, identity = _read_file_at(
            instructions_fd, "order.json", "instruction order"
        )
        file_identities.append(
            (instructions_fd, "order.json", identity, "instruction order")
        )
        names = []
        for name in os.listdir(instructions_fd):
            if not name.endswith(".md"):
                continue
            metadata = os.stat(name, dir_fd=instructions_fd, follow_symlinks=False)
            if not stat.S_ISREG(metadata.st_mode):
                raise RenderError(
                    "instruction fragment may not be a symbolic link: {}".format(name)
                )
            names.append(name)
        order = _load_order(order_bytes, names)
        fragments = []
        for name in order:
            content, identity = _read_file_at(
                instructions_fd, name, "instruction fragment"
            )
            file_identities.append(
                (
                    instructions_fd,
                    name,
                    identity,
                    "instruction fragment '{}'".format(name),
                )
            )
            fragments.append(
                _decode_utf8(content, "instruction fragment '{}'".format(name))
            )

        appendix_bytes, identity = _read_file_at(
            adapter_fd, "instructions-appendix.md", "adapter instruction appendix"
        )
        file_identities.append(
            (
                adapter_fd,
                "instructions-appendix.md",
                identity,
                "adapter instruction appendix",
            )
        )
        appendix = _decode_utf8(
            appendix_bytes, "adapter instruction appendix", allow_empty=True
        )

        _assert_root_identity(root, root_fd)
        _assert_entry_identity(root_fd, "core", core_fd, "core source directory")
        _assert_entry_identity(
            core_fd, "instructions", instructions_fd, "instruction source directory"
        )
        _assert_entry_identity(
            core_fd, "capabilities", capabilities_fd, "capability source directory"
        )
        _assert_entry_identity(
            root_fd, "adapters", adapters_fd, "adapter source directory"
        )
        _assert_entry_identity(
            adapters_fd, adapter, adapter_fd, "selected adapter directory"
        )
        for parent, name, expected, label in file_identities:
            _assert_file_identity(parent, name, expected, label)
        return "".join(fragments) + appendix, declaration
    except OSError as error:
        raise RenderError("descriptor-confined render failed: {}".format(error)) from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def render_instructions(adapter: str, root: Path) -> str:
    """Render ordered shared fragments and the selected adapter appendix."""
    content, _ = _render_with_declaration(adapter, Path(root).resolve())
    return content


def _instruction_filename(adapter: str, declaration) -> str:
    expected = {"claude": "CLAUDE.md", "codex": "AGENTS.md"}.get(adapter)
    if expected is None or expected not in declaration.owned_paths:
        raise RenderError(
            "adapter '{}' does not declare an owned instruction file".format(adapter)
        )
    return expected


def _confined_output(adapter: str, output: Path, supplied_root: Path, root: Path) -> Path:
    expected = root / ".staging" / adapter
    supplied_output = Path(output)
    if supplied_output.is_absolute():
        try:
            relative_output = supplied_output.relative_to(supplied_root)
        except ValueError as error:
            raise RenderError("output must be inside the canonical repository") from error
        candidate = Path(os.path.abspath(str(root / relative_output)))
    else:
        candidate = Path(os.path.abspath(str(root / supplied_output)))
    if candidate != expected:
        raise RenderError("output must be the adapter staging directory: {}".format(expected))
    return expected


def _open_or_create_directory_at(
    parent: int, name: str, label: str, mode: int = 0o700
) -> int:
    created = False
    try:
        os.mkdir(name, mode=mode, dir_fd=parent)
        created = True
    except FileExistsError:
        pass
    try:
        return _open_directory_at(parent, name, label)
    except RenderError:
        if created:
            try:
                os.rmdir(name, dir_fd=parent)
            except OSError:
                pass
        raise


def write_staged_instructions(adapter: str, output: Path, root: Path) -> Path:
    """Exclusively write one instruction file below an anchored staging directory."""
    supplied_root = Path(root)
    root = supplied_root.resolve()
    destination = _confined_output(adapter, output, supplied_root, root)
    content, declaration = _render_with_declaration(adapter, root)
    filename = _instruction_filename(adapter, declaration)
    descriptors: List[int] = []
    output_fd = None
    output_identity = None
    created_output = False
    published = False
    try:
        root_fd = _open_root(root)
        descriptors.append(root_fd)
        staging_fd = _open_or_create_directory_at(
            root_fd, ".staging", "staged output root"
        )
        descriptors.append(staging_fd)
        adapter_fd = _open_or_create_directory_at(
            staging_fd, adapter, "adapter staged output"
        )
        descriptors.append(adapter_fd)
        if os.listdir(adapter_fd):
            raise RenderError(
                "staged output directory is not empty: {}".format(destination)
            )
        try:
            output_fd = os.open(
                filename,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                0o644,
                dir_fd=adapter_fd,
            )
            created_output = True
        except FileExistsError as error:
            raise RenderError(
                "staged instruction output already exists: {}".format(
                    destination / filename
                )
            ) from error
        data = content.encode("utf-8")
        offset = 0
        while offset < len(data):
            written = os.write(output_fd, data[offset:])
            if written <= 0:
                raise RenderError("staged instruction write made no progress")
            offset += written
        os.fsync(output_fd)
        output_identity = _file_identity(os.fstat(output_fd))
        os.close(output_fd)
        output_fd = None

        _assert_root_identity(root, root_fd)
        _assert_entry_identity(root_fd, ".staging", staging_fd, "staged output root")
        _assert_entry_identity(
            staging_fd, adapter, adapter_fd, "adapter staged output"
        )
        metadata = os.stat(filename, dir_fd=adapter_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or _file_identity(metadata) != output_identity
        ):
            raise RenderError("staged instruction output changed during render")
        published = True
        return destination / filename
    except RenderError:
        raise
    except OSError as error:
        raise RenderError("staged render failed: {}".format(error)) from error
    finally:
        if output_fd is not None:
            os.close(output_fd)
        if created_output and not published and len(descriptors) >= 3:
            adapter_fd = descriptors[-1]
            try:
                os.unlink(filename, dir_fd=adapter_fd)
            except OSError:
                pass
        for descriptor in reversed(descriptors):
            os.close(descriptor)
