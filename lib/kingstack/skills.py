"""Validated, agent-neutral skill catalog and pure skill bundle rendering."""

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple

from kingstack.adapter_contract import (
    AdapterContractError,
    canonicalize_portable_relative_path,
    load_adapter_document,
    portable_path_key,
)


class SkillCatalogError(ValueError):
    """Raised when skill catalog data or sources violate the contract."""


_OWNERS = frozenset({"kingstack", "pstack", "adopted", "plugin-manager"})
_ENTRY_REQUIRED = frozenset({"name", "owner", "source", "targets", "dependencies"})
_ENTRY_ALLOWED = _ENTRY_REQUIRED | {"transform", "frontmatter_name"}
_CATALOG_KEYS = frozenset({"schema_version", "upstreams", "entries"})
_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_TRANSFORM_KINDS = frozenset({"frontmatter", "model", "tool", "path", "host"})
_TEXT_EXTENSIONS = frozenset({".md", ".ts", ".sh", ".json"})
_MODEL_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_TOOL_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_-]{0,127}\Z")
_HOST_TOKEN = re.compile(r"[A-Z][A-Za-z]*(?: [A-Z][A-Za-z]*)?\Z")
_UNSUPPORTED_CONSTRUCT_TOKENS = MappingProxyType({
    "Task syntax": b"Task",
    "subagent_type": b"subagent_type",
    "run_in_background": b"run_in_background",
    "AskQuestion": b"AskQuestion",
    "/loop": b"/loop",
    "agent-transcripts": b"agent-transcripts",
})


@dataclass(frozen=True)
class SkillEntry:
    name: str
    owner: str
    source: str
    targets: Tuple[str, ...]
    dependencies: Tuple[str, ...]
    transform: Optional[str] = None
    frontmatter_name: Optional[str] = None


@dataclass(frozen=True)
class _TransformRule:
    text_extensions: Tuple[str, ...]
    replacements: Tuple[Mapping[str, str], ...]
    forbidden: Tuple[str, ...]


@dataclass(frozen=True)
class SkillCatalog:
    entries: Tuple[SkillEntry, ...]
    upstreams: Mapping[str, Mapping[str, str]]
    root: Path
    upstream_root: Path
    transforms: Mapping[str, Mapping[str, _TransformRule]]
    unsupported: Mapping[str, Mapping[str, Tuple[Mapping[str, str], ...]]]
    sources: Mapping[str, Mapping[str, bytes]]
    adapter_ids: Tuple[str, ...]

    def available_names(self, adapter: str) -> Tuple[str, ...]:
        _require_adapter(adapter, self.adapter_ids)
        return tuple(entry.name for entry in self.entries if adapter in entry.targets)

    def upstream_revision(self, upstream: str) -> str:
        try:
            return self.upstreams[upstream]["revision"]
        except KeyError as error:
            raise SkillCatalogError("unknown upstream '{}'".format(upstream)) from error

    def owner(self, name: str) -> str:
        return self.entry(name).owner

    def entry(self, name: str) -> SkillEntry:
        for entry in self.entries:
            if entry.name == name:
                return entry
        raise SkillCatalogError("unknown skill '{}'".format(name))


def _require_adapter(adapter: object, adapter_ids: Sequence[str]) -> str:
    if not isinstance(adapter, str) or adapter not in adapter_ids:
        raise SkillCatalogError("unknown target adapter '{}'".format(adapter))
    return adapter


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SkillCatalogError("{} must be an object".format(label))
    if not all(isinstance(key, str) for key in value):
        raise SkillCatalogError("{} keys must be strings".format(label))
    return value


def _exact_keys(value, required, allowed, label: str) -> None:
    unknown = sorted(set(value) - set(allowed))
    missing = sorted(set(required) - set(value))
    if unknown:
        raise SkillCatalogError("unknown {} keys: {}".format(label, ", ".join(unknown)))
    if missing:
        raise SkillCatalogError("missing {} keys: {}".format(label, ", ".join(missing)))


def _stable_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise SkillCatalogError("{} must be a stable lowercase ID".format(label))
    return value


def _portable_source(value: object) -> str:
    try:
        return canonicalize_portable_relative_path(value, "source path")
    except AdapterContractError as error:
        raise SkillCatalogError(str(error)) from error


def _read_json_bytes(content: bytes, label: str) -> Any:
    try:
        return json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SkillCatalogError("cannot load {}: {}".format(label, error)) from error


def _identity(metadata: os.stat_result) -> Tuple[int, int, int, int, int]:
    return (
        metadata.st_dev, metadata.st_ino, metadata.st_size,
        metadata.st_mtime_ns, metadata.st_ctime_ns,
    )


def _open_absolute_dir(path: Path, label: str) -> int:
    """Open an absolute directory component-wise without following links."""
    absolute = Path(os.path.abspath(str(path)))
    if not absolute.is_absolute():
        raise SkillCatalogError("{} must be absolute".format(label))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open("/", flags)
    try:
        for component in absolute.parts[1:]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as error:
        os.close(descriptor)
        raise SkillCatalogError(
            "{} has a symbolic link or unsafe ancestor: {}".format(label, absolute)
        ) from error


def _open_relative(root_fd: int, path: str, directory: bool = False) -> int:
    components = path.split("/")
    descriptor = os.dup(root_fd)
    try:
        for index, component in enumerate(components):
            final = index == len(components) - 1
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            if not final or directory:
                flags |= getattr(os, "O_DIRECTORY", 0)
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError:
        os.close(descriptor)
        raise


def _read_fd(descriptor: int, label: str) -> bytes:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode):
        raise SkillCatalogError("{} must be a regular file, not a symbolic link".format(label))
    chunks = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
    after = os.fstat(descriptor)
    if _identity(before) != _identity(after):
        raise SkillCatalogError("{} changed while reading".format(label))
    return b"".join(chunks)


def _read_relative(root_fd: int, path: str, label: str) -> bytes:
    try:
        descriptor = _open_relative(root_fd, path)
    except OSError as error:
        raise SkillCatalogError("cannot load {}: {}".format(label, error)) from error
    try:
        identity = _identity(os.fstat(descriptor))
        content = _read_fd(descriptor, label)
    finally:
        os.close(descriptor)
    try:
        check_descriptor = _open_relative(root_fd, path)
    except OSError as error:
        raise SkillCatalogError("{} identity changed while reading".format(label)) from error
    try:
        if identity != _identity(os.fstat(check_descriptor)):
            raise SkillCatalogError("{} identity changed while reading".format(label))
    finally:
        os.close(check_descriptor)
    return content


def _source_path(root: Path, upstream_root: Path, entry: SkillEntry) -> Optional[Path]:
    if entry.owner == "plugin-manager":
        return None
    return (root if entry.owner == "kingstack" else upstream_root) / entry.source


def _validate_owner_source(entry: SkillEntry) -> None:
    matches = (
        entry.owner == "kingstack" and entry.source.startswith("core/skills/authored/"),
        entry.owner == "pstack" and entry.source.startswith("pstack/skills/"),
        entry.owner == "adopted" and entry.source.startswith(
            ("cursor-team-kit/skills/", "cli-for-agent/skills/", "thermos/skills/")
        ),
        entry.owner == "plugin-manager" and entry.source.startswith("plugin:"),
    )
    if not any(matches):
        raise SkillCatalogError(
            "owner/source contradiction for '{}': {} cannot own {}".format(
                entry.name, entry.owner, entry.source
            )
        )


def _frontmatter(content: bytes, label: str) -> Tuple[Mapping[str, str], str]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SkillCatalogError("{} frontmatter must be UTF-8".format(label)) from error
    if not text.startswith("---\n"):
        raise SkillCatalogError("{} has invalid frontmatter".format(label))
    end = text.find("\n---\n", 4)
    if end < 0:
        raise SkillCatalogError("{} has unterminated frontmatter".format(label))
    fields = {}
    lines = text[4:end].splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if any(ord(character) < 32 and character not in "\n\r" for character in line):
            raise SkillCatalogError("{} has invalid frontmatter control characters".format(label))
        match = re.fullmatch(r"([a-z][a-z0-9-]*):(?: (.*))?", line)
        if match is None:
            raise SkillCatalogError("{} has malformed frontmatter".format(label))
        key, value = match.group(1), match.group(2) or ""
        if key in fields:
            raise SkillCatalogError("{} has duplicate frontmatter key '{}'".format(label, key))
        if value in (">", ">-", "|", "|-"):
            if key == "description" and value != ">-":
                raise SkillCatalogError("{} description must use folded >- frontmatter".format(label))
            block = []
            index += 1
            while index < len(lines) and lines[index].startswith("  "):
                block.append(lines[index][2:])
                index += 1
            if not block:
                raise SkillCatalogError("{} has malformed frontmatter block".format(label))
            fields[key] = "\n".join(block)
            if key == "description" and not fields[key].strip():
                raise SkillCatalogError("{} description frontmatter must be nonempty".format(label))
            continue
        if key == "description":
            if value.startswith('"'):
                try:
                    parsed = json.loads(value)
                except json.JSONDecodeError as error:
                    raise SkillCatalogError("{} has malformed quoted description frontmatter".format(label)) from error
                if not isinstance(parsed, str) or not parsed.strip():
                    raise SkillCatalogError("{} description frontmatter must be nonempty".format(label))
                value = parsed
            elif (
                not value.strip()
                or value.startswith(("#", "'", "[", "{", "&", "*", "!", "?", "- "))
                or value.casefold() in {"null", "~", "true", "false"}
            ):
                raise SkillCatalogError("{} description frontmatter must be a nonempty string".format(label))
        elif value.startswith(('"', "'")):
            quote = value[0]
            if len(value) < 2 or not value.endswith(quote):
                raise SkillCatalogError("{} has unterminated frontmatter value".format(label))
            value = value[1:-1]
        elif value.startswith(("[", "{", "&", "*", "!", "?", "- ")):
            raise SkillCatalogError("{} has unsupported frontmatter value".format(label))
        fields[key] = value
        index += 1
    if not fields.get("name") or not fields.get("description", "").strip():
        raise SkillCatalogError("{} frontmatter requires name and description".format(label))
    return MappingProxyType(fields), text[end + 5:]


def _frontmatter_name(content: bytes, label: str) -> str:
    return _frontmatter(content, label)[0]["name"]


def _read_source_tree(
    root_fd: int, source: str, expected_name: str, validate_frontmatter: bool = True,
    expected_frontmatter_name: Optional[str] = None,
) -> Mapping[str, bytes]:
    try:
        source_fd = _open_relative(root_fd, source, directory=True)
    except OSError as error:
        raise SkillCatalogError("missing source for '{}': {}".format(expected_name, source)) from error
    source_identity = _identity(os.fstat(source_fd))
    entries = []
    seen = set()
    def visit(directory_fd: int, prefix: str) -> None:
        before = _identity(os.fstat(directory_fd))
        names = sorted(os.listdir(directory_fd))
        for name in names:
            relative = name if not prefix else prefix + "/" + name
            try:
                canonical = canonicalize_portable_relative_path(relative, "skill resource path")
                child_fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory_fd)
            except (AdapterContractError, OSError) as error:
                raise SkillCatalogError("skill source contains a symbolic link or unsafe path: {}".format(relative)) from error
            try:
                metadata = os.fstat(child_fd)
                if stat.S_ISDIR(metadata.st_mode):
                    visit(child_fd, canonical)
                elif stat.S_ISREG(metadata.st_mode):
                    key = portable_path_key(canonical)
                    if key in seen:
                        raise SkillCatalogError("duplicate skill resource path '{}'".format(canonical))
                    seen.add(key)
                    entries.append((canonical, _read_fd(child_fd, "skill resource '{}'".format(canonical))))
                else:
                    raise SkillCatalogError("skill source contains a non-file: {}".format(relative))
            finally:
                os.close(child_fd)
        if names != sorted(os.listdir(directory_fd)) or before != _identity(os.fstat(directory_fd)):
            raise SkillCatalogError("skill source directory changed while reading: {}".format(prefix or source))
    try:
        visit(source_fd, "")
        try:
            check_fd = _open_relative(root_fd, source, directory=True)
        except OSError as error:
            raise SkillCatalogError("skill source identity changed while reading: {}".format(source)) from error
        try:
            if source_identity != _identity(os.fstat(check_fd)):
                raise SkillCatalogError("skill source identity changed while reading: {}".format(source))
        finally:
            os.close(check_fd)
    finally:
        os.close(source_fd)
    files = MappingProxyType(OrderedDict(sorted(entries)))
    if "SKILL.md" not in files:
        raise SkillCatalogError("missing source SKILL.md for '{}'".format(expected_name))
    if validate_frontmatter:
        actual_name = _frontmatter_name(files["SKILL.md"], "skill '{}'".format(expected_name))
        if actual_name != (expected_frontmatter_name or expected_name):
            raise SkillCatalogError("skill '{}' frontmatter name is '{}'".format(expected_name, actual_name))
    return files


def _adapter_ids(root_fd: int) -> Tuple[str, ...]:
    """Discover validated declarations beneath the held repository descriptor."""
    identifiers = []
    try:
        adapters_fd = _open_relative(root_fd, "adapters", directory=True)
    except OSError as error:
        raise SkillCatalogError("cannot enumerate adapter declarations: {}".format(error)) from error
    adapters_identity = _identity(os.fstat(adapters_fd))
    names = sorted(os.listdir(adapters_fd))
    try:
        for name in names:
            try:
                canonical = canonicalize_portable_relative_path(name, "adapter directory")
                candidate_fd = os.open(
                    canonical,
                    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=adapters_fd,
                )
            except (AdapterContractError, OSError) as error:
                raise SkillCatalogError("adapter directory is a symbolic link or unsafe: {}".format(name)) from error
            candidate_identity = _identity(os.fstat(candidate_fd))
            try:
                try:
                    probe_fd = _open_relative(candidate_fd, "adapter.json")
                except FileNotFoundError:
                    continue
                else:
                    os.close(probe_fd)
                raw = _mapping(
                    _read_json_bytes(
                        _read_relative(candidate_fd, "adapter.json", "adapter '{}'".format(name)),
                        "adapter '{}'".format(name),
                    ),
                    "adapter '{}'".format(name),
                )
                inline = dict(raw)
                for field in ("owned_paths", "model_tiers", "capability_matrix"):
                    reference = inline.get(field)
                    if not isinstance(reference, str):
                        continue
                    try:
                        reference = canonicalize_portable_relative_path(reference, "adapter reference")
                    except AdapterContractError as error:
                        raise SkillCatalogError(str(error)) from error
                    document = _read_json_bytes(
                        _read_relative(candidate_fd, reference, "adapter '{}' {}".format(name, field)),
                        "adapter '{}' {}".format(name, field),
                    )
                    if field == "model_tiers" and isinstance(document, dict) and "model_tiers" in document:
                        document = document["model_tiers"]
                    elif field == "owned_paths" and isinstance(document, dict) and "owned_paths" in document:
                        document = document["owned_paths"]
                    inline[field] = document
                try:
                    declaration = load_adapter_document(inline, Path("adapters") / name / "adapter.json")
                except AdapterContractError as error:
                    raise SkillCatalogError("invalid adapter declaration '{}': {}".format(name, error)) from error
                if declaration.id != name:
                    raise SkillCatalogError("adapter declaration directory/ID mismatch")
                identifiers.append(declaration.id)
                try:
                    check_fd = os.open(
                        name,
                        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=adapters_fd,
                    )
                except OSError as error:
                    raise SkillCatalogError("adapter directory identity changed: {}".format(name)) from error
                try:
                    if candidate_identity != _identity(os.fstat(check_fd)):
                        raise SkillCatalogError("adapter directory identity changed: {}".format(name))
                finally:
                    os.close(check_fd)
            finally:
                os.close(candidate_fd)
        if names != sorted(os.listdir(adapters_fd)) or adapters_identity != _identity(os.fstat(adapters_fd)):
            raise SkillCatalogError("adapter directory changed while reading")
        check_adapters_fd = _open_relative(root_fd, "adapters", directory=True)
        try:
            if adapters_identity != _identity(os.fstat(check_adapters_fd)):
                raise SkillCatalogError("adapter directory identity changed while reading")
        finally:
            os.close(check_adapters_fd)
    finally:
        os.close(adapters_fd)
    if not identifiers:
        raise SkillCatalogError("no validated adapter declarations")
    return tuple(identifiers)


def _load_transforms(root_fd: int, adapter_ids: Sequence[str]) -> Tuple[Mapping[str, Mapping[str, _TransformRule]], Mapping[str, Mapping[str, Tuple[Mapping[str, str], ...]]]]:
    adapters = {}
    unsupported_by_adapter = {}
    for adapter in sorted(adapter_ids):
        label = "{} skill transforms".format(adapter)
        document = _mapping(
            _read_json_bytes(_read_relative(root_fd, "core/skills/transforms/{}.json".format(adapter), label), label), label
        )
        required = {"schema_version", "adapter", "transforms", "unsupported"}
        _exact_keys(document, required, required, "transform document")
        if document["schema_version"] != 1 or document["adapter"] != adapter:
            raise SkillCatalogError("invalid {} transform identity".format(adapter))
        raw_rules = _mapping(document["transforms"], "transform rules")
        rules = {}
        for name, raw_rule in raw_rules.items():
            _stable_id(name, "transform name")
            rule = _mapping(raw_rule, "transform '{}'".format(name))
            required_rule = {"text_extensions", "replacements", "forbidden"}
            _exact_keys(rule, required_rule, required_rule, "transform")
            extensions = rule["text_extensions"]
            replacements = rule["replacements"]
            forbidden = rule["forbidden"]
            if (
                not isinstance(extensions, list) or not extensions
                or not all(isinstance(item, str) and item in _TEXT_EXTENSIONS for item in extensions)
                or len(extensions) != len(set(extensions))
            ):
                raise SkillCatalogError("transform text_extensions are invalid")
            if not isinstance(replacements, list) or not isinstance(forbidden, list):
                raise SkillCatalogError("transform replacements and forbidden must be arrays")
            typed = []
            for replacement in replacements:
                replacement = _mapping(replacement, "transform replacement")
                kind = replacement.get("kind")
                if kind == "frontmatter":
                    required_replacement = {"kind", "field", "action"}
                    _exact_keys(replacement, required_replacement, required_replacement, "replacement")
                    if replacement["action"] != "remove" or _ID.fullmatch(str(replacement["field"])) is None:
                        raise SkillCatalogError("frontmatter transform replacement is invalid")
                else:
                    required_replacement = {"kind", "source", "target"}
                    _exact_keys(replacement, required_replacement, required_replacement, "replacement")
                    if kind not in _TRANSFORM_KINDS - {"frontmatter"}:
                        raise SkillCatalogError("transform replacement kind is invalid")
                    source, target = replacement["source"], replacement["target"]
                    if not isinstance(source, str) or not source or not isinstance(target, str) or not target:
                        raise SkillCatalogError("transform replacement must use non-destructive exact tokens")
                    if source in (".*", ".+", "^", "$") or source == target:
                        raise SkillCatalogError("transform replacement must use non-destructive exact tokens")
                    if kind == "model" and (
                        _MODEL_TOKEN.fullmatch(source) is None or _MODEL_TOKEN.fullmatch(target) is None
                    ):
                        raise SkillCatalogError("model transform must use exact model tokens")
                    if kind == "tool" and (
                        _TOOL_TOKEN.fullmatch(source) is None or _TOOL_TOKEN.fullmatch(target) is None
                    ):
                        raise SkillCatalogError("tool transform must use exact tool tokens")
                    if kind == "path" and (
                        any(character.isspace() or ord(character) < 32 for character in source + target)
                        or len(source) > 512 or len(target) > 512
                        or not any(marker in source for marker in ("/", ".", "$", "~"))
                        or not any(marker in target for marker in ("/", ".", "$", "~"))
                    ):
                        raise SkillCatalogError("path transform must use exact path tokens")
                    if kind == "host" and (
                        source not in {"Cursor", "Claude", "Claude Code"}
                        or _HOST_TOKEN.fullmatch(target) is None
                    ):
                        raise SkillCatalogError("host transform source and target must be explicit host tokens")
                typed.append(MappingProxyType(dict(replacement)))
            if not all(isinstance(token, str) and token for token in forbidden):
                raise SkillCatalogError("forbidden host tokens must be non-empty strings")
            rules[name] = _TransformRule(tuple(extensions), tuple(typed), tuple(forbidden))
        adapters[adapter] = MappingProxyType(rules)
        raw_unsupported = _mapping(document["unsupported"], "unsupported skills")
        unsupported = {}
        for skill, raw_evidence in raw_unsupported.items():
            _stable_id(skill, "unsupported skill")
            if not isinstance(raw_evidence, list) or not raw_evidence:
                raise SkillCatalogError("unsupported skill evidence must be a non-empty array")
            evidence = []
            for record in raw_evidence:
                record = _mapping(record, "unsupported evidence")
                _exact_keys(record, {"resource", "construct"}, {"resource", "construct"}, "unsupported evidence")
                if not all(isinstance(record[key], str) and record[key] for key in record):
                    raise SkillCatalogError("unsupported evidence values must be non-empty strings")
                evidence.append(MappingProxyType(dict(record)))
            unsupported[skill] = tuple(evidence)
        unsupported_by_adapter[adapter] = MappingProxyType(unsupported)
    return MappingProxyType(adapters), MappingProxyType(unsupported_by_adapter)


def _validate_dependencies(entries: Sequence[SkillEntry]) -> None:
    by_name = {entry.name: entry for entry in entries}
    for entry in entries:
        for dependency in entry.dependencies:
            if dependency not in by_name:
                raise SkillCatalogError("missing dependency '{}' for '{}'".format(dependency, entry.name))
            for target in entry.targets:
                if target not in by_name[dependency].targets:
                    raise SkillCatalogError("dependency '{}' is unavailable for target '{}'".format(dependency, target))
    visiting = set()
    visited = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise SkillCatalogError("dependency cycle includes '{}'".format(name))
        if name in visited:
            return
        visiting.add(name)
        for dependency in by_name[name].dependencies:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)

    for name in sorted(by_name):
        visit(name)


def load_catalog(root: Path, upstream_root: Optional[Path] = None) -> SkillCatalog:
    """Load the catalog while owning each root descriptor from acquisition."""
    root = Path(os.path.abspath(str(root)))
    upstream_root = Path(os.path.abspath(str(
        upstream_root
        or os.environ.get(
            "KINGSTACK_UPSTREAM_ROOT", Path.home() / "Desktop/Work/plugins"
        )
    )))
    root_fd = _open_absolute_dir(root, "kingstack root")
    try:
        upstream_fd = _open_absolute_dir(upstream_root, "upstream root")
    except BaseException:
        os.close(root_fd)
        raise
    try:
        return _load_catalog_opened(root, upstream_root, root_fd, upstream_fd)
    finally:
        try:
            os.close(upstream_fd)
        finally:
            os.close(root_fd)


def _load_catalog_opened(
    root: Path, upstream_root: Path, root_fd: int, upstream_fd: int
) -> SkillCatalog:
    root_identity = _identity(os.fstat(root_fd))
    upstream_identity = _identity(os.fstat(upstream_fd))
    adapter_ids = _adapter_ids(root_fd)
    document = _mapping(
        _read_json_bytes(_read_relative(root_fd, "core/skills/catalog.json", "skill catalog"), "skill catalog"),
        "skill catalog",
    )
    _exact_keys(document, _CATALOG_KEYS, _CATALOG_KEYS, "catalog")
    if document["schema_version"] != 1 or isinstance(document["schema_version"], bool):
        raise SkillCatalogError("skill catalog schema_version must be 1")
    upstreams_document = _mapping(document["upstreams"], "upstreams")
    upstreams = {}
    for name, value in upstreams_document.items():
        _stable_id(name, "upstream name")
        value = _mapping(value, "upstream '{}'".format(name))
        required = {"revision", "source"}
        _exact_keys(value, required, required, "upstream")
        if not all(isinstance(value[field], str) and value[field] for field in required):
            raise SkillCatalogError("upstream fields must be non-empty strings")
        upstreams[name] = MappingProxyType(dict(value))

    raw_entries = document["entries"]
    if not isinstance(raw_entries, list) or not raw_entries:
        raise SkillCatalogError("skill catalog entries must be a non-empty array")
    entries = []
    names = set()
    sources = set()
    for index, raw_entry in enumerate(raw_entries):
        raw_entry = _mapping(raw_entry, "entry {}".format(index))
        _exact_keys(raw_entry, _ENTRY_REQUIRED, _ENTRY_ALLOWED, "entry")
        name = _stable_id(raw_entry["name"], "skill name")
        name_key = portable_path_key(name)
        if name_key in names:
            raise SkillCatalogError("duplicate skill name '{}'".format(name))
        names.add(name_key)
        owner = raw_entry["owner"]
        if owner not in _OWNERS:
            raise SkillCatalogError("unknown owner '{}'".format(owner))
        source_value = raw_entry["source"]
        if owner == "plugin-manager":
            if not isinstance(source_value, str) or re.fullmatch(r"plugin:[a-z0-9-]+/[a-z0-9-]+", source_value) is None:
                raise SkillCatalogError("plugin-manager source path must be a plugin reference")
            source = source_value
        else:
            source = _portable_source(source_value)
        source_key = portable_path_key(source)
        if source_key in sources:
            raise SkillCatalogError("duplicate source path '{}'".format(source))
        sources.add(source_key)
        targets = raw_entry["targets"]
        dependencies = raw_entry["dependencies"]
        if (
            not isinstance(targets, list) or not targets
            or not all(isinstance(target, str) for target in targets)
            or len({target.casefold() for target in targets}) != len(targets)
        ):
            raise SkillCatalogError("target list must contain unique adapter IDs")
        unknown_targets = sorted(set(targets) - set(adapter_ids))
        if unknown_targets:
            raise SkillCatalogError("unknown target '{}'".format(unknown_targets[0]))
        if (
            not isinstance(dependencies, list)
            or not all(isinstance(dependency, str) and _ID.fullmatch(dependency) for dependency in dependencies)
            or len(dependencies) != len(set(dependencies))
        ):
            raise SkillCatalogError("dependencies must contain unique skill IDs")
        transform = raw_entry.get("transform")
        if transform is not None:
            transform = _stable_id(transform, "transform")
        frontmatter_name = raw_entry.get("frontmatter_name")
        if frontmatter_name is not None and (
            not isinstance(frontmatter_name, str)
            or not frontmatter_name.strip()
            or any(ord(character) < 32 for character in frontmatter_name)
        ):
            raise SkillCatalogError("frontmatter_name must be a nonempty display identity")
        entry = SkillEntry(
            name, owner, source, tuple(targets), tuple(dependencies), transform,
            frontmatter_name,
        )
        _validate_owner_source(entry)
        entries.append(entry)

    _validate_dependencies(entries)
    transforms, unsupported = _load_transforms(root_fd, adapter_ids)
    sources = {}
    try:
        for entry in entries:
            if entry.owner == "plugin-manager":
                if entry.transform is not None:
                    raise SkillCatalogError("plugin-manager skill '{}' may not declare a transform".format(entry.name))
                continue
            for adapter in entry.targets:
                if entry.transform is None or entry.transform not in transforms[adapter]:
                    raise SkillCatalogError("skill '{}' has an unknown transform for '{}'".format(entry.name, adapter))
            descriptor = root_fd if entry.owner == "kingstack" else upstream_fd
            sources[entry.name] = _read_source_tree(
                descriptor, entry.source, entry.name,
                expected_frontmatter_name=entry.frontmatter_name,
            )
        for adapter, records in unsupported.items():
            for name in records:
                if name not in {entry.name for entry in entries}:
                    raise SkillCatalogError("unsupported evidence names unknown skill '{}'".format(name))
                entry = next(item for item in entries if item.name == name)
                if adapter not in entry.targets or entry.owner == "plugin-manager":
                    raise SkillCatalogError("unsupported evidence contradicts catalog for '{}'".format(name))
                for evidence in records[name]:
                    try:
                        resource = canonicalize_portable_relative_path(
                            evidence["resource"], "unsupported evidence resource"
                        )
                    except AdapterContractError as error:
                        raise SkillCatalogError(str(error)) from error
                    construct = evidence["construct"]
                    if construct not in _UNSUPPORTED_CONSTRUCT_TOKENS:
                        raise SkillCatalogError("unknown unsupported construct '{}'".format(construct))
                    if resource not in sources[name] or _UNSUPPORTED_CONSTRUCT_TOKENS[construct] not in sources[name][resource]:
                        raise SkillCatalogError(
                            "unsupported evidence is not present in '{}:{}'".format(name, resource)
                        )
        root_check = None
        upstream_check = None
        try:
            root_check = _open_absolute_dir(root, "kingstack root")
            upstream_check = _open_absolute_dir(upstream_root, "upstream root")
            if root_identity != _identity(os.fstat(root_check)) or upstream_identity != _identity(os.fstat(upstream_check)):
                raise SkillCatalogError("source root identity changed while reading")
        finally:
            if upstream_check is not None:
                os.close(upstream_check)
            if root_check is not None:
                os.close(root_check)
        return SkillCatalog(
            entries=tuple(entries), upstreams=MappingProxyType(upstreams), root=root,
            upstream_root=upstream_root, transforms=transforms, unsupported=unsupported,
            sources=MappingProxyType(sources), adapter_ids=adapter_ids,
        )
    finally:
        pass


def _transform_content(content: bytes, path: str, rule: _TransformRule, label: str) -> bytes:
    if Path(path).suffix not in rule.text_extensions:
        return content
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SkillCatalogError("{} text resource '{}' must be UTF-8".format(label, path)) from error
    frontmatter_end = text.find("\n---\n", 4) if text.startswith("---\n") else -1
    for replacement in rule.replacements:
        kind = replacement["kind"]
        if kind == "frontmatter":
            if path != "SKILL.md" or frontmatter_end < 0:
                continue
            field = replacement["field"]
            lines = text[4:frontmatter_end].splitlines()
            lines = [line for line in lines if not line.startswith(field + ":")]
            text = "---\n" + "\n".join(lines) + "\n---\n" + text[frontmatter_end + 5:]
            frontmatter_end = text.find("\n---\n", 4)
            continue
        source, target = replacement["source"], replacement["target"]
        if kind in ("model", "tool", "host"):
            pattern = re.compile(r"(?<![A-Za-z0-9_.-]){}(?![A-Za-z0-9_.-])".format(re.escape(source)))
            text = pattern.sub(lambda _match, value=target: value, text)
        else:
            text = text.replace(source, target)
    for forbidden in rule.forbidden:
        if forbidden in text:
            raise SkillCatalogError(
                "forbidden foreign-host term '{}' remains in {} '{}'".format(forbidden, label, path)
            )
    result = text.encode("utf-8")
    if path == "SKILL.md":
        _frontmatter(result, label)
    return result


def _unsupported_names(catalog: SkillCatalog, adapter: str) -> Mapping[str, Tuple[Mapping[str, str], ...]]:
    direct = dict(catalog.unsupported[adapter])
    changed = True
    while changed:
        changed = False
        for entry in catalog.entries:
            if adapter not in entry.targets or entry.name in direct:
                continue
            blocked = sorted(set(entry.dependencies) & set(direct))
            if blocked:
                direct[entry.name] = (
                    MappingProxyType({"resource": "catalog.json", "construct": "unsupported dependency: {}".format(blocked[0])}),
                )
                changed = True
    return MappingProxyType(direct)


def render_skill_files(adapter: str, root: Path, upstream_root: Optional[Path] = None) -> Mapping[str, bytes]:
    """Return immutable catalog-relative portable skill files without writing."""
    catalog = load_catalog(root, upstream_root=upstream_root)
    adapter = _require_adapter(adapter, catalog.adapter_ids)
    unsupported = _unsupported_names(catalog, adapter)
    output = []
    seen = set()
    for entry in catalog.entries:
        if adapter not in entry.targets or entry.owner == "plugin-manager" or entry.name in unsupported:
            continue
        source_files = catalog.sources[entry.name]
        rule = catalog.transforms[adapter][entry.transform]
        for resource, content in source_files.items():
            path = "{}/{}".format(entry.name, resource)
            key = portable_path_key(path)
            if key in seen:
                raise SkillCatalogError("duplicate rendered skill path '{}'".format(path))
            seen.add(key)
            output.append((path, _transform_content(content, resource, rule, "skill '{}'".format(entry.name))))
    return MappingProxyType(OrderedDict(sorted(output)))


def _freeze(value: object):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def bundle_manifest(adapter: str, root: Path, upstream_root: Optional[Path] = None) -> Mapping[str, object]:
    """Return immutable hashes plus explicit bundled/plugin/gap accounting."""
    catalog = load_catalog(root, upstream_root=upstream_root)
    adapter = _require_adapter(adapter, catalog.adapter_ids)
    unsupported = _unsupported_names(catalog, adapter)
    files = render_skill_files(adapter, root, upstream_root=catalog.upstream_root)
    skills = []
    for entry in catalog.entries:
        status = (
            "unsupported" if adapter not in entry.targets or entry.name in unsupported
            else "plugin-managed" if entry.owner == "plugin-manager"
            else "bundled"
        )
        record = {"name": entry.name, "owner": entry.owner, "status": status, "source": entry.source}
        if entry.name in unsupported:
            record["evidence"] = [dict(item) for item in unsupported[entry.name]]
        elif adapter not in entry.targets:
            record["evidence"] = [{"resource": "catalog.json", "construct": "adapter target is not declared"}]
        skills.append(record)
    return _freeze({
        "schema_version": 1,
        "adapter": adapter,
        "upstreams": {name: dict(value) for name, value in catalog.upstreams.items()},
        "skills": skills,
        "files": [
            {"path": path, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for path, content in files.items()
        ],
    })


def _canonical_allowed_pair(source: str, rendered: str, rule: _TransformRule) -> Optional[str]:
    pairs = [
        (item["source"], item["target"], item["kind"])
        for item in rule.replacements if item["kind"] != "frontmatter"
    ]
    left = right = 0
    canonical = []
    while left < len(source) or right < len(rendered):
        matches = [
            pair for pair in pairs
            if source.startswith(pair[0], left) and rendered.startswith(pair[1], right)
        ]
        if matches:
            original, replacement, kind = max(matches, key=lambda item: len(item[0]))
            canonical.append("__KINGSTACK_ALLOWED_{}__".format(kind.upper()))
            left += len(original)
            right += len(replacement)
        elif left < len(source) and right < len(rendered) and source[left] == rendered[right]:
            canonical.append(source[left])
            left += 1
            right += 1
        else:
            return None
    return "".join(canonical)


def semantic_parity_errors(adapter: str, root: Path, upstream_root: Optional[Path] = None) -> Tuple[str, ...]:
    """Compare resource names, headings, paragraphs, and normalized script bytes."""
    catalog = load_catalog(root, upstream_root=upstream_root)
    adapter = _require_adapter(adapter, catalog.adapter_ids)
    unsupported = _unsupported_names(catalog, adapter)
    rendered = render_skill_files(adapter, root, upstream_root=catalog.upstream_root)
    errors = []
    for entry in catalog.entries:
        if adapter not in entry.targets or entry.owner == "plugin-manager" or entry.name in unsupported:
            continue
        source_files = catalog.sources[entry.name]
        actual_names = {path.split("/", 1)[1] for path in rendered if path.startswith(entry.name + "/")}
        if actual_names != set(source_files):
            errors.append("{} resource names changed".format(entry.name))
            continue
        rule = catalog.transforms[adapter][entry.transform]
        for resource, source in source_files.items():
            actual = rendered["{}/{}".format(entry.name, resource)]
            if resource == "SKILL.md":
                try:
                    source_fields, source_body = _frontmatter(source, "source")
                    actual_fields, actual_body = _frontmatter(actual, "rendered")
                except SkillCatalogError as error:
                    errors.append("{} frontmatter invalid: {}".format(entry.name, error))
                    continue
                removed = {item["field"] for item in rule.replacements if item["kind"] == "frontmatter"}
                if set(source_fields) - removed != set(actual_fields):
                    errors.append("{} frontmatter fields changed".format(entry.name))
                for field in (set(source_fields) - removed) & set(actual_fields):
                    if _canonical_allowed_pair(source_fields[field], actual_fields[field], rule) is None:
                        errors.append("{} frontmatter value '{}' changed".format(entry.name, field))
                source_text, actual_text = source_body, actual_body
            else:
                try:
                    source_text, actual_text = source.decode("utf-8"), actual.decode("utf-8")
                except UnicodeDecodeError:
                    if source != actual:
                        errors.append("{}:{} binary resource changed".format(entry.name, resource))
                    continue
            source_blocks = tuple(block.strip() for block in re.split(r"\n\s*\n", source_text) if block.strip())
            actual_blocks = tuple(block.strip() for block in re.split(r"\n\s*\n", actual_text) if block.strip())
            if len(source_blocks) != len(actual_blocks) or any(
                _canonical_allowed_pair(left, right, rule) is None
                for left, right in zip(source_blocks, actual_blocks)
            ):
                errors.append("{}:{} instruction paragraphs changed".format(entry.name, resource))
            if resource == "SKILL.md":
                source_headings = tuple(line for line in source_text.splitlines() if line.startswith("#"))
                actual_headings = tuple(line for line in actual_text.splitlines() if line.startswith("#"))
                if len(source_headings) != len(actual_headings) or any(
                    _canonical_allowed_pair(left, right, rule) is None
                    for left, right in zip(source_headings, actual_headings)
                ):
                    errors.append("{} headings changed".format(entry.name))
            if Path(resource).suffix in (".sh", ".py", ".ts", ".js"):
                canonical = _canonical_allowed_pair(source_text, actual_text, rule)
                if canonical is None:
                    errors.append("{}:{} normalized script hash changed".format(entry.name, resource))
    return tuple(errors)


def check_upstream(upstream: str, root: Path, upstream_root: Path) -> Mapping[str, str]:
    """Verify the frozen upstream revision against the source checkout."""
    catalog = load_catalog(root, upstream_root=upstream_root)
    expected = catalog.upstream_revision(upstream)
    source = catalog.upstreams[upstream]["source"]
    try:
        result = subprocess.run(
            ["git", "-C", str(catalog.upstream_root), "log", "-1", "--format=%h", "--", source + "/"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise SkillCatalogError("cannot inspect upstream '{}': {}".format(upstream, error)) from error
    actual = result.stdout.strip()
    if actual != expected:
        raise SkillCatalogError("upstream '{}' revision drift: catalog {} != source {}".format(upstream, expected, actual))
    return MappingProxyType({"upstream": upstream, "revision": actual, "status": "clean"})


def check_clobber_manifest(
    adapter: str, root: Path, installed_root: Path, manifest: bytes,
    upstream_root: Optional[Path] = None,
) -> None:
    """Reject changed generated files and non-generated ownership claims."""
    catalog = load_catalog(root, upstream_root=upstream_root)
    adapter = _require_adapter(adapter, catalog.adapter_ids)
    unsupported = _unsupported_names(catalog, adapter)
    expected_files = {
        "{}/{}".format(entry.name, resource)
        for entry in catalog.entries
        if entry.owner in ("pstack", "adopted")
        and adapter in entry.targets
        and entry.name not in unsupported
        for resource in catalog.sources[entry.name]
    }
    try:
        text = manifest.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SkillCatalogError("clobber manifest must be UTF-8") from error
    installed_root = Path(installed_root)
    seen = set()
    manifest_hashes = {}
    for number, line in enumerate(text.splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise SkillCatalogError("invalid clobber manifest line {}".format(number))
        expected, raw_path = match.groups()
        try:
            path = canonicalize_portable_relative_path(raw_path, "clobber manifest path")
        except AdapterContractError as error:
            raise SkillCatalogError(str(error)) from error
        key = portable_path_key(path)
        if key in seen:
            raise SkillCatalogError("duplicate clobber manifest path '{}'".format(path))
        seen.add(key)
        manifest_hashes[path] = expected
        name = path.split("/", 1)[0]
        try:
            entry = catalog.entry(name)
        except SkillCatalogError as error:
            raise SkillCatalogError("clobber manifest has extra out-of-catalog path '{}'".format(path)) from error
        if entry.owner not in ("pstack", "adopted") or adapter not in entry.targets:
            raise SkillCatalogError("clobber manifest path '{}' is not generated content".format(path))
    actual_paths = set(manifest_hashes)
    missing = sorted(expected_files - actual_paths)
    extra = sorted(actual_paths - expected_files)
    if missing or extra:
        raise SkillCatalogError(
            "clobber manifest is not the exact generated set (missing: {}; extra: {})".format(
                ", ".join(missing) or "none", ", ".join(extra) or "none"
            )
        )
    installed_fd = _open_absolute_dir(installed_root, "installed skill root")
    try:
        for entry in catalog.entries:
            if entry.owner not in ("pstack", "adopted") or adapter not in entry.targets or entry.name in unsupported:
                continue
            try:
                installed_files = _read_source_tree(
                    installed_fd, entry.name, entry.name, validate_frontmatter=False
                )
            except SkillCatalogError as error:
                raise SkillCatalogError("installed generated path is missing or unsafe: {}".format(entry.name)) from error
            expected_resources = set(catalog.sources[entry.name])
            actual_resources = set(installed_files)
            if actual_resources != expected_resources:
                raise SkillCatalogError(
                    "installed generated tree has missing or extra resources for '{}'".format(entry.name)
                )
            for resource, content in installed_files.items():
                path = "{}/{}".format(entry.name, resource)
                actual = hashlib.sha256(content).hexdigest()
                if actual != manifest_hashes[path]:
                    raise SkillCatalogError("hand-edited generated file refused: {}".format(path))
    finally:
        os.close(installed_fd)
