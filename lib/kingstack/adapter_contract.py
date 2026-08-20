"""Agent-neutral adapter declarations and capability reporting."""

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
from typing import Any, Dict, FrozenSet, List, Mapping, Set, Tuple


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_VERSION = 1
ADAPTER_SCHEMA = ROOT / "adapters/contract/adapter.schema.json"
CAPABILITY_SCHEMA = ROOT / "adapters/contract/capability.schema.json"
CAPABILITY_STATUSES = frozenset({"native", "emulated", "degraded", "unsupported"})
STABLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ADAPTER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
WINDOWS_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
WINDOWS_DEVICE_NAME = re.compile(
    r"^(?:con|prn|aux|nul|com(?:[1-9]|[¹²³])|lpt(?:[1-9]|[¹²³]))(?:\..*)?$",
    re.IGNORECASE,
)
WINDOWS_FORBIDDEN_CHARACTERS = frozenset('<>:"|?*')


class AdapterContractError(ValueError):
    """Raised when an adapter document cannot satisfy the structural contract."""


@dataclass(frozen=True)
class CapabilityCatalog:
    capabilities: FrozenSet[str]
    model_tiers: FrozenSet[str]


@dataclass(frozen=True)
class CapabilityState:
    capability: str
    status: str
    evidence: str
    impact: str
    strict_parity: bool


@dataclass(frozen=True)
class CapabilityMatrix:
    adapter_id: str
    states: Tuple[CapabilityState, ...]


@dataclass(frozen=True)
class CapabilityReport:
    required: FrozenSet[str]
    native: FrozenSet[str]
    emulated: FrozenSet[str]
    degraded: FrozenSet[str]
    unsupported: FrozenSet[str]
    missing: FrozenSet[str]
    strict_parity: bool


@dataclass(frozen=True)
class AdapterDeclaration:
    id: str
    contract_version: int
    render_module: str
    native_home: str
    owned_paths: Tuple[str, ...]
    model_tiers: Mapping[str, str]
    capability_matrix: CapabilityMatrix
    source: Path
    raw: Mapping[str, Any]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise AdapterContractError("missing contract document: {}".format(path)) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdapterContractError("invalid JSON in {}: {}".format(path, error)) from error


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def _schema_errors(value: Any, schema: Mapping[str, Any], location: str = "$") -> List[str]:
    """Validate the deliberately small JSON-Schema subset used by the contract."""
    if "oneOf" in schema:
        branches = [
            _schema_errors(value, branch, location) for branch in schema["oneOf"]
        ]
        matching = [errors for errors in branches if not errors]
        if len(matching) != 1:
            details = "; ".join(error for branch in branches for error in branch)
            return [
                "{} must match exactly one allowed shape ({})".format(location, details)
            ]
        return []

    expected_type = schema.get("type")
    if expected_type is not None and not _json_type_matches(value, expected_type):
        return ["{} must be {}".format(location, expected_type)]

    errors: List[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append("{} must equal {!r}".format(location, schema["const"]))
    if "enum" in schema and value not in schema["enum"]:
        errors.append("{} must be one of {}".format(location, schema["enum"]))

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append("{} must not be empty".format(location))
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, value) is None:
            errors.append("{} does not match required pattern".format(location))

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append("{} has too few items".format(location))
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append("{} contains duplicate items".format(location))
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                errors.extend(_schema_errors(item, item_schema, "{}[{}]".format(location, index)))

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        property_names = schema.get("propertyNames")
        if property_names is not None:
            for name in value:
                errors.extend(
                    _schema_errors(name, property_names, "{} key".format(location))
                )
        for name in schema.get("required", []):
            if name not in value:
                errors.append("{} missing required property '{}'".format(location, name))
        additional = schema.get("additionalProperties", True)
        if additional is False:
            for name in value:
                if name not in properties:
                    errors.append("{} has unknown property '{}'".format(location, name))
        for name, item in value.items():
            if name in properties:
                errors.extend(_schema_errors(item, properties[name], "{}.{}".format(location, name)))
            elif isinstance(additional, dict):
                errors.extend(_schema_errors(item, additional, "{}.{}".format(location, name)))
    return errors


def _require_schema(value: Any, schema_path: Path, label: str) -> None:
    schema = _load_json(schema_path)
    errors = _schema_errors(value, schema)
    if errors:
        raise AdapterContractError("{} schema: {}".format(label, "; ".join(errors)))


def _resolve_reference(source: Path, reference: str) -> Path:
    candidate = Path(reference)
    if candidate.is_absolute():
        raise AdapterContractError("contract references must be relative: {}".format(reference))
    local = source.parent / candidate
    if local.is_file():
        return local
    repository = ROOT / candidate
    if repository.is_file():
        return repository
    raise AdapterContractError("missing referenced document '{}'".format(reference))


def _load_owned_paths(source: Path, value: Any) -> Tuple[str, ...]:
    if isinstance(value, str):
        document = _load_json(_resolve_reference(source, value))
        value = document.get("owned_paths") if isinstance(document, dict) else document
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AdapterContractError("owned_paths must be an array of strings")

    canonical_paths = []
    for path in value:
        if any(
            ord(character) <= 0x1F or ord(character) == 0x7F
            for character in path
        ):
            raise AdapterContractError(
                "owned_paths entries may not contain C0 or DEL control characters"
            )
        path = unicodedata.normalize("NFC", path)
        if "\\" in path:
            raise AdapterContractError(
                "owned_paths entries must use portable POSIX separators, not backslashes"
            )
        if WINDOWS_DRIVE_PREFIX.match(path):
            raise AdapterContractError("owned_paths entries may not use a Windows drive prefix")
        if any(character in WINDOWS_FORBIDDEN_CHARACTERS for character in path):
            raise AdapterContractError(
                "owned_paths entries contain characters that are not portable to Windows"
            )
        normalized = PurePosixPath(path)
        if normalized.is_absolute():
            raise AdapterContractError("owned_paths entries must be relative")
        if ".." in normalized.parts:
            raise AdapterContractError("owned_paths entries may not contain backtracking")
        canonical = normalized.as_posix()
        if canonical in ("", "."):
            raise AdapterContractError("owned_paths may not own the native home root")
        if path.endswith("/"):
            raise AdapterContractError("owned_paths entries may not have a trailing slash")
        if "//" in path:
            raise AdapterContractError("owned_paths entries may not contain empty components")
        for component in normalized.parts:
            if component.endswith((".", " ")):
                raise AdapterContractError(
                    "owned_paths components may not end in a Windows-ambiguous dot or space"
                )
            if WINDOWS_DEVICE_NAME.fullmatch(component) is not None:
                raise AdapterContractError(
                    "owned_paths entries may not use a Windows device name"
                )
        canonical_paths.append(canonical)
    portable_keys = [path.casefold() for path in canonical_paths]
    if len(portable_keys) != len(set(portable_keys)):
        raise AdapterContractError("owned_paths contains a duplicate canonical path")
    return tuple(canonical_paths)


def _load_model_tiers(source: Path, value: Any) -> Mapping[str, str]:
    if isinstance(value, str):
        document = _load_json(_resolve_reference(source, value))
        value = (
            document.get("model_tiers")
            if isinstance(document, dict) and "model_tiers" in document
            else document
        )
    if not isinstance(value, dict):
        raise AdapterContractError("model_tiers must map portable tiers to native models")
    if not all(
        isinstance(key, str)
        and STABLE_ID_PATTERN.fullmatch(key) is not None
        and isinstance(model, str)
        and MODEL_ID_PATTERN.fullmatch(model) is not None
        for key, model in value.items()
    ):
        raise AdapterContractError(
            "model_tiers keys and values must use the portable exact-ID grammar"
        )
    return dict(value)


def _load_matrix(source: Path, value: Any) -> CapabilityMatrix:
    if isinstance(value, str):
        value = _load_json(_resolve_reference(source, value))
    _require_schema(value, CAPABILITY_SCHEMA, "capability matrix")

    states = tuple(CapabilityState(**entry) for entry in value["capabilities"])
    names = [state.capability for state in states]
    if len(names) != len(set(names)):
        raise AdapterContractError("capability matrix contains a duplicate capability")
    for state in states:
        if state.status not in CAPABILITY_STATUSES:
            raise AdapterContractError("unknown capability status '{}'".format(state.status))
        if state.status != "native":
            if not state.evidence.strip():
                raise AdapterContractError("non-native capability '{}' requires evidence".format(state.capability))
            if not state.impact.strip():
                raise AdapterContractError("non-native capability '{}' requires impact".format(state.capability))
        if state.status == "native" and not state.strict_parity:
            raise AdapterContractError("native capability '{}' must preserve strict_parity".format(state.capability))
        if state.status in {"degraded", "unsupported"} and state.strict_parity:
            raise AdapterContractError("{} capability '{}' cannot claim strict_parity".format(state.status, state.capability))
    return CapabilityMatrix(adapter_id=value["adapter_id"], states=states)


def load_adapter(path: Path) -> AdapterDeclaration:
    """Load an adapter and every referenced contract document without importing it."""
    source = Path(path)
    if source.is_dir():
        source = source / "adapter.json"
    raw = _load_json(source)
    _require_schema(raw, ADAPTER_SCHEMA, "adapter")

    owned_paths = _load_owned_paths(source, raw["owned_paths"])
    model_tiers = _load_model_tiers(source, raw["model_tiers"])
    matrix = _load_matrix(source, raw["capability_matrix"])
    if matrix.adapter_id != raw["id"]:
        raise AdapterContractError(
            "capability matrix adapter_id '{}' does not match '{}'".format(
                matrix.adapter_id, raw["id"]
            )
        )
    return AdapterDeclaration(
        id=raw["id"],
        contract_version=raw["contract_version"],
        render_module=raw["render_module"],
        native_home=raw["native_home"],
        owned_paths=owned_paths,
        model_tiers=model_tiers,
        capability_matrix=matrix,
        source=source,
        raw=dict(raw),
    )


def load_capability_catalog(path: Path) -> CapabilityCatalog:
    document = _load_json(path)
    if not isinstance(document, dict) or set(document) != {
        "contract_version", "model_tiers", "capabilities"
    }:
        raise AdapterContractError("capability catalog has an invalid top-level shape")
    if (
        type(document["contract_version"]) is not int
        or document["contract_version"] != CONTRACT_VERSION
    ):
        raise AdapterContractError("unsupported capability catalog contract_version")
    tiers = document["model_tiers"]
    entries = document["capabilities"]
    if not isinstance(tiers, list) or not tiers or not all(
        isinstance(tier, str) and STABLE_ID_PATTERN.fullmatch(tier) is not None
        for tier in tiers
    ):
        raise AdapterContractError("capability catalog model tier IDs are invalid")
    if not isinstance(entries, list) or not all(
        isinstance(entry, dict)
        and set(entry) == {"id", "description"}
        and isinstance(entry["id"], str)
        and STABLE_ID_PATTERN.fullmatch(entry["id"]) is not None
        and isinstance(entry["description"], str)
        and entry["description"].strip()
        for entry in entries
    ):
        raise AdapterContractError("capability catalog capability IDs or entries are invalid")
    capabilities = [entry["id"] for entry in entries]
    if len(capabilities) != len(set(capabilities)) or len(tiers) != len(set(tiers)):
        raise AdapterContractError("capability catalog contains duplicate IDs")
    return CapabilityCatalog(frozenset(capabilities), frozenset(tiers))


def validate_adapter(
    declaration: AdapterDeclaration, catalog: CapabilityCatalog
) -> List[str]:
    """Return all catalog-level errors for a structurally valid declaration."""
    errors: List[str] = []
    mapped = set(declaration.model_tiers)
    for tier in sorted(mapped - set(catalog.model_tiers)):
        errors.append("unknown model tier '{}'".format(tier))
    for tier in sorted(set(catalog.model_tiers) - mapped):
        errors.append("unmapped model tier '{}'".format(tier))
    for state in declaration.capability_matrix.states:
        if state.capability not in catalog.capabilities:
            errors.append("unknown capability '{}'".format(state.capability))
    declared_capabilities = {
        state.capability for state in declaration.capability_matrix.states
    }
    for capability in sorted(set(catalog.capabilities) - declared_capabilities):
        errors.append("missing capability '{}'".format(capability))
    return errors


def compare_capabilities(
    required: Set[str], matrix: CapabilityMatrix
) -> CapabilityReport:
    """Compare required capability IDs and derive strict parity from their states."""
    by_name = {state.capability: state for state in matrix.states}
    groups: Dict[str, Set[str]] = {status: set() for status in CAPABILITY_STATUSES}
    missing = set(required) - set(by_name)
    parity = not missing
    for capability in required & set(by_name):
        state = by_name[capability]
        groups[state.status].add(capability)
        parity = parity and state.strict_parity
    return CapabilityReport(
        required=frozenset(required),
        native=frozenset(groups["native"]),
        emulated=frozenset(groups["emulated"]),
        degraded=frozenset(groups["degraded"]),
        unsupported=frozenset(groups["unsupported"]),
        missing=frozenset(missing),
        strict_parity=parity,
    )
