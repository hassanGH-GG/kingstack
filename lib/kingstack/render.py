"""Pure, deterministic, descriptor-confined rendering of adapter bundles."""

from collections import OrderedDict
from collections.abc import Mapping
import errno
import json
import os
from pathlib import Path, PurePosixPath
import stat
from types import MappingProxyType
from typing import Any, List, Tuple
import unicodedata

from kingstack.adapter_contract import (
    ADAPTER_ID_PATTERN,
    AdapterContractError,
    load_adapter_document,
    load_capability_catalog_document,
    validate_adapter,
)


class RenderError(ValueError):
    """Raised when render sources or provider output violate the contract."""


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
    adapter: str, root: Path, adapter_document: Any, catalog_bytes: bytes
):
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


def _inline_adapter_references(
    document: Any, adapter_fd: int, file_identities: list
) -> Any:
    if not isinstance(document, dict):
        return document
    inlined = dict(document)
    for field in ("owned_paths", "model_tiers", "capability_matrix"):
        reference = inlined.get(field)
        if not isinstance(reference, str):
            continue
        if Path(reference).name != reference or not reference.endswith(".json"):
            raise RenderError(
                "render-time adapter reference '{}' must be an adjacent JSON file".format(
                    reference
                )
            )
        content, identity = _read_file_at(
            adapter_fd, reference, "adapter {} reference".format(field)
        )
        file_identities.append(
            (
                adapter_fd,
                reference,
                identity,
                "adapter {} reference".format(field),
            )
        )
        value = _decode_json(content, "adapter {} reference".format(field))
        if field in ("owned_paths", "model_tiers") and isinstance(value, dict):
            value = value.get(field, value)
        inlined[field] = value
    return inlined


def _read_provider_source(
    root_fd: int,
    adapter_fd: int,
    declaration,
    descriptors: List[int],
    directory_identities: list,
    file_identities: list,
) -> bytes:
    components = declaration.render_module.split(".")
    if components[:2] == ["kingstack", "adapters"]:
        if len(components) != 3:
            raise RenderError("first-party render modules must name one adapter provider")
        parent = root_fd
        for component, label in (
            ("lib", "provider lib directory"),
            ("kingstack", "provider package directory"),
            ("adapters", "provider adapter package directory"),
        ):
            descriptor = _open_directory_at(parent, component, label)
            descriptors.append(descriptor)
            directory_identities.append((parent, component, descriptor, label))
            parent = descriptor
        filename = components[-1] + ".py"
    else:
        if components[0] == "kingstack":
            raise RenderError("render module may not escape the provider namespace")
        parent = adapter_fd
        for component in components[:-1]:
            label = "local provider package '{}'".format(component)
            descriptor = _open_directory_at(parent, component, label)
            descriptors.append(descriptor)
            directory_identities.append((parent, component, descriptor, label))
            parent = descriptor
        filename = components[-1] + ".py"

    source, identity = _read_file_at(parent, filename, "render provider")
    file_identities.append((parent, filename, identity, "render provider"))
    try:
        source.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RenderError("render provider must be valid UTF-8") from error
    return source


def _load_render_context(adapter: str, root: Path):
    if not isinstance(adapter, str) or ADAPTER_ID_PATTERN.fullmatch(adapter) is None:
        raise RenderError("adapter must be a stable adapter ID")
    descriptors: List[int] = []
    directory_identities = []
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
        adapter_document = _inline_adapter_references(
            _decode_json(adapter_bytes, "adapter declaration"),
            adapter_fd,
            file_identities,
        )
        declaration = _load_declaration(adapter, root, adapter_document, catalog_bytes)

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

        try:
            appendix_metadata = os.stat(
                "instructions-appendix.md",
                dir_fd=adapter_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            appendix_bytes = b""
        else:
            if not stat.S_ISREG(appendix_metadata.st_mode):
                raise RenderError("adapter instruction appendix may not be a symbolic link")
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
        provider_source = _read_provider_source(
            root_fd,
            adapter_fd,
            declaration,
            descriptors,
            directory_identities,
            file_identities,
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
        for parent, name, descriptor, label in directory_identities:
            _assert_entry_identity(parent, name, descriptor, label)
        for parent, name, expected, label in file_identities:
            _assert_file_identity(parent, name, expected, label)
        shared_sources = MappingProxyType(
            {
                "instructions": "".join(fragments).encode("utf-8"),
                "appendix": appendix.encode("utf-8"),
            }
        )
        return declaration, shared_sources, provider_source
    except OSError as error:
        raise RenderError("descriptor-confined render failed: {}".format(error)) from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _provider_callable(module_name: str, source: bytes):
    namespace = {
        "__name__": module_name,
        "__package__": module_name.rpartition(".")[0],
        "__file__": "<kingstack-provider:{}>".format(module_name),
    }
    try:
        code = compile(source, namespace["__file__"], "exec")
        exec(code, namespace)
    except Exception as error:
        raise RenderError(
            "render provider '{}' could not be loaded: {}".format(module_name, error)
        ) from error
    provider = namespace.get("render")
    if not callable(provider):
        raise RenderError(
            "render provider '{}' must expose callable render".format(module_name)
        )
    return provider


def _canonical_output_path(path: object) -> str:
    if not isinstance(path, str) or not path:
        raise RenderError("provider output path must be a nonempty string")
    if any(ord(character) <= 0x1F or ord(character) == 0x7F for character in path):
        raise RenderError("provider output path must be a canonical relative path")
    if "\\" in path or path.startswith("/") or "//" in path or path.endswith("/"):
        raise RenderError("provider output path must be a canonical relative path")
    normalized = unicodedata.normalize("NFC", path)
    portable = PurePosixPath(normalized)
    canonical = portable.as_posix()
    if ".." in portable.parts or canonical in ("", ".") or canonical != normalized:
        raise RenderError("provider output path must be a canonical relative path")
    return canonical


def _validate_provider_output(output: object, declaration):
    if not isinstance(output, Mapping):
        raise RenderError("render provider must return a mapping of paths to bytes")
    entries = []
    seen = set()
    for raw_path, content in output.items():
        path = _canonical_output_path(raw_path)
        portable_key = path.casefold()
        if portable_key in seen:
            raise RenderError("render provider returned duplicate output path '{}'".format(path))
        seen.add(portable_key)
        if not isinstance(content, bytes):
            raise RenderError("render provider output '{}' must be bytes".format(path))
        if not any(path == owned or path.startswith(owned + "/") for owned in declaration.owned_paths):
            raise RenderError(
                "render provider output '{}' is not covered by owned_paths".format(path)
            )
        entries.append((path, content))
    if not entries:
        raise RenderError("render provider returned an empty bundle")
    return MappingProxyType(OrderedDict(sorted(entries)))


def render_bundle(adapter: str, root: Path):
    """Return an immutable ordered path-to-bytes bundle without filesystem writes."""
    root = Path(root).resolve()
    declaration, shared_sources, source = _load_render_context(adapter, root)
    provider = _provider_callable(declaration.render_module, source)
    try:
        output = provider(root, declaration, shared_sources)
    except RenderError:
        raise
    except Exception as error:
        raise RenderError(
            "render provider '{}' failed: {}".format(declaration.render_module, error)
        ) from error
    return _validate_provider_output(output, declaration)


def render_instructions(adapter: str, root: Path) -> str:
    """Compatibility helper for single-file instruction adapters."""
    bundle = render_bundle(adapter, root)
    if len(bundle) != 1:
        raise RenderError("instruction renderer requires a single-file bundle")
    content = next(iter(bundle.values()))
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RenderError("rendered instruction file must be valid UTF-8") from error
