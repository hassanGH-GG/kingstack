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
    portable_path_key,
)


class SkillCatalogError(ValueError):
    """Raised when skill catalog data or sources violate the contract."""


_OWNERS = frozenset({"kingstack", "pstack", "adopted", "plugin-manager"})
_TARGETS = frozenset({"claude", "codex"})
_ENTRY_REQUIRED = frozenset({"name", "owner", "source", "targets", "dependencies"})
_ENTRY_ALLOWED = _ENTRY_REQUIRED | {"transform"}
_CATALOG_KEYS = frozenset({"schema_version", "upstreams", "entries"})
_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_TRANSFORM_KINDS = frozenset({"frontmatter", "model", "tool", "path", "host"})
_TEXT_EXTENSIONS = frozenset({".md", ".ts", ".sh", ".json"})


@dataclass(frozen=True)
class SkillEntry:
    name: str
    owner: str
    source: str
    targets: Tuple[str, ...]
    dependencies: Tuple[str, ...]
    transform: Optional[str] = None


@dataclass(frozen=True)
class _TransformRule:
    text_extensions: Tuple[str, ...]
    replacements: Tuple[Tuple[re.Pattern, str, str], ...]
    forbidden: Tuple[re.Pattern, ...]


@dataclass(frozen=True)
class SkillCatalog:
    entries: Tuple[SkillEntry, ...]
    upstreams: Mapping[str, Mapping[str, str]]
    root: Path
    upstream_root: Path
    transforms: Mapping[str, Mapping[str, _TransformRule]]

    def available_names(self, adapter: str) -> Tuple[str, ...]:
        _require_adapter(adapter)
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


def _require_adapter(adapter: object) -> str:
    if not isinstance(adapter, str) or adapter not in _TARGETS:
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


def _read_json(path: Path, label: str) -> Any:
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise SkillCatalogError("{} must be a regular file, not a symbolic link".format(label))
        return json.loads(path.read_text(encoding="utf-8"))
    except SkillCatalogError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SkillCatalogError("cannot load {}: {}".format(label, error)) from error


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


def _frontmatter_name(content: bytes, label: str) -> str:
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
    for line in text[4:end].splitlines():
        if line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    if not fields.get("name") or "description" not in fields:
        raise SkillCatalogError("{} frontmatter requires name and description".format(label))
    return fields["name"].strip("'\"")


def _read_source_tree(path: Path, expected_name: str) -> Mapping[str, bytes]:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise SkillCatalogError("missing source for '{}': {}".format(expected_name, path)) from error
    if stat.S_ISLNK(metadata.st_mode):
        raise SkillCatalogError("skill source may not be a symbolic link: {}".format(path))
    if not stat.S_ISDIR(metadata.st_mode):
        raise SkillCatalogError("skill source must be a directory: {}".format(path))
    entries = []
    seen = set()
    for directory, directory_names, filenames in os.walk(str(path), followlinks=False):
        directory_path = Path(directory)
        for name in tuple(directory_names):
            child = directory_path / name
            if child.is_symlink():
                raise SkillCatalogError("skill source contains a symbolic link: {}".format(child))
        for filename in filenames:
            child = directory_path / filename
            child_metadata = child.lstat()
            if stat.S_ISLNK(child_metadata.st_mode):
                raise SkillCatalogError("skill source contains a symbolic link: {}".format(child))
            if not stat.S_ISREG(child_metadata.st_mode):
                raise SkillCatalogError("skill source contains a non-file: {}".format(child))
            relative = child.relative_to(path).as_posix()
            try:
                canonical = canonicalize_portable_relative_path(relative, "skill resource path")
            except AdapterContractError as error:
                raise SkillCatalogError(str(error)) from error
            key = portable_path_key(canonical)
            if key in seen:
                raise SkillCatalogError("duplicate skill resource path '{}'".format(canonical))
            seen.add(key)
            before = child_metadata
            content = child.read_bytes()
            after = child.lstat()
            identity = lambda value: (
                value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns
            )
            if identity(before) != identity(after):
                raise SkillCatalogError("skill source changed while reading: {}".format(child))
            entries.append((canonical, content))
    files = MappingProxyType(OrderedDict(sorted(entries)))
    if "SKILL.md" not in files:
        raise SkillCatalogError("missing source SKILL.md for '{}'".format(expected_name))
    actual_name = _frontmatter_name(files["SKILL.md"], "skill '{}'".format(expected_name))
    normalized_name = re.sub(r"[^a-z0-9]+", "-", actual_name.casefold()).strip("-")
    if normalized_name != expected_name:
        raise SkillCatalogError("skill '{}' frontmatter name is '{}'".format(expected_name, actual_name))
    return files


def _load_transforms(root: Path) -> Mapping[str, Mapping[str, _TransformRule]]:
    adapters = {}
    for adapter in sorted(_TARGETS):
        label = "{} skill transforms".format(adapter)
        document = _mapping(
            _read_json(root / "core/skills/transforms/{}.json".format(adapter), label), label
        )
        required = {"schema_version", "adapter", "transforms"}
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
            compiled = []
            for replacement in replacements:
                replacement = _mapping(replacement, "transform replacement")
                required_replacement = {"pattern", "replacement", "kind"}
                _exact_keys(replacement, required_replacement, required_replacement, "replacement")
                if (
                    not isinstance(replacement["pattern"], str)
                    or not isinstance(replacement["replacement"], str)
                    or replacement["kind"] not in _TRANSFORM_KINDS
                ):
                    raise SkillCatalogError("transform replacement is invalid")
                try:
                    compiled.append((re.compile(replacement["pattern"]), replacement["replacement"], replacement["kind"]))
                except re.error as error:
                    raise SkillCatalogError("invalid transform pattern: {}".format(error)) from error
            if not all(isinstance(pattern, str) for pattern in forbidden):
                raise SkillCatalogError("forbidden host patterns must be strings")
            try:
                forbidden_patterns = tuple(re.compile(pattern) for pattern in forbidden)
            except re.error as error:
                raise SkillCatalogError("invalid forbidden host pattern: {}".format(error)) from error
            rules[name] = _TransformRule(tuple(extensions), tuple(compiled), forbidden_patterns)
        adapters[adapter] = MappingProxyType(rules)
    return MappingProxyType(adapters)


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
    """Load and validate the authoritative catalog and every owned source tree."""
    root = Path(root).resolve()
    upstream_root = Path(
        upstream_root
        or os.environ.get(
            "KINGSTACK_UPSTREAM_ROOT", Path.home() / "Desktop/Work/plugins"
        )
    ).resolve()
    document = _mapping(_read_json(root / "core/skills/catalog.json", "skill catalog"), "skill catalog")
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
        unknown_targets = sorted(set(targets) - _TARGETS)
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
        entry = SkillEntry(name, owner, source, tuple(targets), tuple(dependencies), transform)
        _validate_owner_source(entry)
        entries.append(entry)

    _validate_dependencies(entries)
    transforms = _load_transforms(root)
    for entry in entries:
        if entry.owner == "plugin-manager":
            if entry.transform is not None:
                raise SkillCatalogError("plugin-manager skill '{}' may not declare a transform".format(entry.name))
            continue
        for adapter in entry.targets:
            if entry.transform is None or entry.transform not in transforms[adapter]:
                raise SkillCatalogError("skill '{}' has an unknown transform for '{}'".format(entry.name, adapter))
        _read_source_tree(_source_path(root, upstream_root, entry), entry.name)
    return SkillCatalog(
        entries=tuple(entries), upstreams=MappingProxyType(upstreams), root=root,
        upstream_root=upstream_root, transforms=transforms,
    )


def _transform_content(content: bytes, path: str, rule: _TransformRule, label: str) -> bytes:
    if Path(path).suffix not in rule.text_extensions:
        return content
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SkillCatalogError("{} text resource '{}' must be UTF-8".format(label, path)) from error
    for pattern, replacement, _kind in rule.replacements:
        text = pattern.sub(lambda _match, value=replacement: value, text)
    for forbidden in rule.forbidden:
        if forbidden.search(text):
            raise SkillCatalogError(
                "forbidden foreign-host term '{}' remains in {} '{}'".format(forbidden.pattern, label, path)
            )
    return text.encode("utf-8")


def render_skill_files(adapter: str, root: Path, upstream_root: Optional[Path] = None) -> Mapping[str, bytes]:
    """Return immutable catalog-relative portable skill files without writing."""
    adapter = _require_adapter(adapter)
    catalog = load_catalog(root, upstream_root=upstream_root)
    output = []
    seen = set()
    for entry in catalog.entries:
        if adapter not in entry.targets or entry.owner == "plugin-manager":
            continue
        source_files = _read_source_tree(_source_path(catalog.root, catalog.upstream_root, entry), entry.name)
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
    adapter = _require_adapter(adapter)
    catalog = load_catalog(root, upstream_root=upstream_root)
    files = render_skill_files(adapter, root, upstream_root=catalog.upstream_root)
    skills = []
    for entry in catalog.entries:
        status = (
            "unsupported" if adapter not in entry.targets
            else "plugin-managed" if entry.owner == "plugin-manager"
            else "bundled"
        )
        skills.append({"name": entry.name, "owner": entry.owner, "status": status, "source": entry.source})
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


def semantic_parity_errors(adapter: str, root: Path, upstream_root: Optional[Path] = None) -> Tuple[str, ...]:
    """Compare resource names, headings, paragraphs, and normalized script bytes."""
    adapter = _require_adapter(adapter)
    catalog = load_catalog(root, upstream_root=upstream_root)
    rendered = render_skill_files(adapter, root, upstream_root=catalog.upstream_root)
    errors = []
    for entry in catalog.entries:
        if adapter not in entry.targets or entry.owner == "plugin-manager":
            continue
        source_files = _read_source_tree(_source_path(catalog.root, catalog.upstream_root, entry), entry.name)
        actual_names = {path.split("/", 1)[1] for path in rendered if path.startswith(entry.name + "/")}
        if actual_names != set(source_files):
            errors.append("{} resource names changed".format(entry.name))
            continue
        rule = catalog.transforms[adapter][entry.transform]
        for resource, source in source_files.items():
            expected = _transform_content(source, resource, rule, "skill '{}'".format(entry.name))
            actual = rendered["{}/{}".format(entry.name, resource)]
            if actual != expected:
                errors.append("{}:{} differs beyond named transforms".format(entry.name, resource))
                continue
            if resource == "SKILL.md":
                expected_headings = tuple(line for line in expected.splitlines() if line.startswith(b"#"))
                actual_headings = tuple(line for line in actual.splitlines() if line.startswith(b"#"))
                if actual_headings != expected_headings:
                    errors.append("{} headings changed".format(entry.name))
            if Path(resource).suffix in (".sh", ".py", ".ts", ".js"):
                if hashlib.sha256(actual).digest() != hashlib.sha256(expected).digest():
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
    adapter = _require_adapter(adapter)
    catalog = load_catalog(root, upstream_root=upstream_root)
    try:
        text = manifest.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SkillCatalogError("clobber manifest must be UTF-8") from error
    installed_root = Path(installed_root)
    seen = set()
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
        name = path.split("/", 1)[0]
        entry = catalog.entry(name)
        if entry.owner not in ("pstack", "adopted") or adapter not in entry.targets:
            raise SkillCatalogError("clobber manifest path '{}' is not generated content".format(path))
        installed = installed_root / path
        try:
            metadata = installed.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise SkillCatalogError("installed generated path '{}' has unsafe type".format(path))
            actual = hashlib.sha256(installed.read_bytes()).hexdigest()
        except SkillCatalogError:
            raise
        except OSError as error:
            raise SkillCatalogError("installed generated path '{}' is missing".format(path)) from error
        if actual != expected:
            raise SkillCatalogError("hand-edited generated file refused: {}".format(path))
