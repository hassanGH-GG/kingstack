"""Portable work-class routing with adapter-owned model selection."""

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple

from kingstack.adapter_contract import (
    ADAPTER_ID_PATTERN,
    MODEL_ID_PATTERN,
    STABLE_ID_PATTERN,
    AdapterContractError,
    AdapterDeclaration,
    load_adapter,
)


ROOT = Path(__file__).resolve().parents[2]
WORK_CLASS_POLICY = {
    "waiting": ("none", "none"),
    "mechanical": ("economical", "low"),
    "precise": ("balanced", "medium"),
    "judgment": ("frontier", "high"),
}
PORTABLE_TIERS = ("economical", "balanced", "frontier")
MODEL_MAP_KEYS = frozenset({"adapter", "model_tiers", "fallbacks"})
FALLBACK_KEYS = frozenset({"from", "to", "reason"})
OVERRIDE_KEYS = frozenset({"tier", "model", "reason"})


class RoutingError(ValueError):
    """Raised when routing data or a requested route is invalid."""


def _immutable(values: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(values))


def _require_string_keys(value: Mapping[str, Any], label: str) -> None:
    if not all(isinstance(key, str) for key in value):
        raise RoutingError("{} keys must be strings".format(label))


def _require_exact_keys(value: Mapping[str, Any], expected, label: str) -> None:
    _require_string_keys(value, label)
    actual = set(value)
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        extra = sorted(actual - set(expected))
        details = []
        if missing:
            details.append("missing {}".format(", ".join(missing)))
        if extra:
            details.append("unknown keys {}".format(", ".join(extra)))
        raise RoutingError("{} has {}".format(label, "; ".join(details)))


def _validate_policy(document: Any) -> Mapping[str, Mapping[str, str]]:
    if not isinstance(document, dict):
        raise RoutingError("routing policy must be an object of work classes")
    _require_string_keys(document, "routing policy")
    if set(document) != set(WORK_CLASS_POLICY):
        raise RoutingError("routing policy must contain exactly the portable work classes")

    policy = {}
    for work_class, expected in WORK_CLASS_POLICY.items():
        route = document[work_class]
        if not isinstance(route, dict):
            raise RoutingError("policy work class '{}' must be an object".format(work_class))
        _require_exact_keys(route, {"tier", "effort"}, "policy work class '{}'".format(work_class))
        if not all(isinstance(route[key], str) for key in ("tier", "effort")):
            raise RoutingError("policy tier and effort must be strings")
        actual = route["tier"], route["effort"]
        if actual != expected:
            raise RoutingError(
                "policy work class '{}' must use the portable mapping {}/{}".format(
                    work_class, expected[0], expected[1]
                )
            )
        policy[work_class] = _immutable(route)
    return MappingProxyType(policy)


def _has_cycle(edges: Mapping[str, str]) -> bool:
    for origin in edges:
        seen = set()
        current = origin
        while current in edges:
            if current in seen:
                return True
            seen.add(current)
            current = edges[current]
    return False


def _validate_model_map(
    document: Any, declaration: AdapterDeclaration
) -> Tuple[Mapping[str, str], Mapping[str, Mapping[str, str]]]:
    if not isinstance(document, dict):
        raise RoutingError("adapter model map must be an object")
    _require_exact_keys(document, MODEL_MAP_KEYS, "adapter model map")
    if document["adapter"] != declaration.id:
        raise RoutingError("adapter model map does not match declaration adapter")

    tiers = document["model_tiers"]
    if not isinstance(tiers, dict):
        raise RoutingError("model_tiers must be an object")
    _require_string_keys(tiers, "model_tiers")
    missing = sorted(set(PORTABLE_TIERS) - set(tiers))
    extra = sorted(set(tiers) - set(PORTABLE_TIERS))
    if missing:
        raise RoutingError("adapter model map has missing tiers: {}".format(", ".join(missing)))
    if extra:
        raise RoutingError("adapter model map has extra tiers: {}".format(", ".join(extra)))
    for tier, model in tiers.items():
        if STABLE_ID_PATTERN.fullmatch(tier) is None:
            raise RoutingError("portable tier must use the stable ID grammar")
        if not isinstance(model, str) or MODEL_ID_PATTERN.fullmatch(model) is None:
            raise RoutingError("native model must use the exact model ID grammar")
    _require_string_keys(declaration.model_tiers, "declaration model_tiers")
    if dict(declaration.model_tiers) != tiers:
        raise RoutingError("adapter model map does not match declaration model_tiers")

    records = document["fallbacks"]
    if not isinstance(records, list):
        raise RoutingError("fallbacks must be an array")
    edges = {}
    reasons = {}
    seen_edges = set()
    for index, record in enumerate(records):
        label = "fallback record {}".format(index)
        if not isinstance(record, dict):
            raise RoutingError("{} must be an object".format(label))
        _require_exact_keys(record, FALLBACK_KEYS, label)
        source = record["from"]
        target = record["to"]
        reason = record["reason"]
        if source not in PORTABLE_TIERS or target not in PORTABLE_TIERS:
            raise RoutingError("{} names an unknown tier".format(label))
        if not isinstance(reason, str) or not reason.strip():
            raise RoutingError("{} requires a non-empty reason".format(label))
        edge = source, target
        if edge in seen_edges:
            raise RoutingError("fallback graph contains a duplicate edge")
        seen_edges.add(edge)
        if source in edges:
            raise RoutingError("fallback graph is ambiguous for tier '{}'".format(source))
        edges[source] = target
        reasons[source] = reason

    if _has_cycle(edges):
        raise RoutingError("fallback graph contains a cycle")
    positions = {tier: index for index, tier in enumerate(PORTABLE_TIERS)}
    for source, target in edges.items():
        if positions[target] != positions[source] - 1:
            raise RoutingError(
                "fallback from '{}' to '{}' must move one adjacent lower tier".format(
                    source, target
                )
            )

    fallbacks = {
        source: _immutable({"tier": target, "reason": reasons[source]})
        for source, target in edges.items()
    }
    return MappingProxyType(dict(tiers)), MappingProxyType(fallbacks)


def _validate_overrides(
    records: Optional[Sequence[Mapping[str, str]]],
) -> Mapping[str, Mapping[str, str]]:
    if records is None:
        records = ()
    if not isinstance(records, (list, tuple)):
        raise RoutingError("availability overrides must be an injected sequence")
    overrides = {}
    for index, record in enumerate(records):
        label = "availability override {}".format(index)
        if not isinstance(record, dict):
            raise RoutingError("{} must be an object".format(label))
        _require_exact_keys(record, OVERRIDE_KEYS, label)
        tier = record["tier"]
        model = record["model"]
        reason = record["reason"]
        if tier not in PORTABLE_TIERS:
            raise RoutingError("{} names an unknown tier".format(label))
        if not isinstance(model, str) or MODEL_ID_PATTERN.fullmatch(model) is None:
            raise RoutingError("{} model must use the exact model ID grammar".format(label))
        if not isinstance(reason, str) or not reason.strip():
            raise RoutingError("{} requires a non-empty reason".format(label))
        if tier in overrides:
            raise RoutingError("availability overrides are ambiguous for tier '{}'".format(tier))
        overrides[tier] = _immutable({"model": model, "reason": reason})
    return MappingProxyType(overrides)


@dataclass(frozen=True)
class RoutingTable:
    adapter: str
    policy: Mapping[str, Mapping[str, str]]
    model_tiers: Mapping[str, str]
    fallbacks: Mapping[str, Mapping[str, str]]

    def resolve(
        self,
        work_class: str,
        availability_overrides: Optional[Sequence[Mapping[str, str]]] = None,
    ) -> Mapping[str, Any]:
        if (
            not isinstance(work_class, str)
            or STABLE_ID_PATTERN.fullmatch(work_class) is None
        ):
            raise RoutingError("work class must be a stable ID")
        if work_class not in self.policy:
            raise RoutingError("unknown work class '{}'".format(work_class))
        route = self.policy[work_class]
        tier = route["tier"]
        overrides = _validate_overrides(availability_overrides)
        if tier == "none":
            return _immutable(
                {
                    "adapter": self.adapter,
                    "work_class": work_class,
                    "tier": tier,
                    "effort": route["effort"],
                    "model": None,
                    "evidence": "portable policy requires no model turn",
                    "reason": "portable policy routes waiting and polling outside model turns",
                }
            )

        override = overrides.get(tier)
        model = override["model"] if override else self.model_tiers[tier]
        evidence = (
            "injected private runtime override for tier '{}'".format(tier)
            if override
            else "checked-in adapter default for tier '{}'".format(tier)
        )
        reason = (
            override["reason"]
            if override
            else "portable policy selects '{}' work at tier '{}' and effort '{}'".format(
                work_class, tier, route["effort"]
            )
        )
        return _immutable(
            {
                "adapter": self.adapter,
                "work_class": work_class,
                "tier": tier,
                "effort": route["effort"],
                "model": model,
                "evidence": evidence,
                "reason": reason,
            }
        )

    def fallback(
        self,
        tier: str,
        availability_overrides: Optional[Sequence[Mapping[str, str]]] = None,
    ) -> Mapping[str, Any]:
        if not isinstance(tier, str) or STABLE_ID_PATTERN.fullmatch(tier) is None:
            raise RoutingError("tier must be a stable ID")
        if tier not in PORTABLE_TIERS:
            raise RoutingError("unknown tier '{}'".format(tier))
        edge = self.fallbacks.get(tier)
        if edge is None:
            raise RoutingError("no adjacent fallback exists for tier '{}'".format(tier))
        target = edge["tier"]
        overrides = _validate_overrides(availability_overrides)
        override = overrides.get(target)
        return _immutable(
            {
                "adapter": self.adapter,
                "from": tier,
                "tier": target,
                "model": override["model"] if override else self.model_tiers[target],
                "evidence": (
                    "injected private runtime override for fallback tier '{}'".format(target)
                    if override
                    else "checked-in adapter default for fallback tier '{}'".format(target)
                ),
                "reason": edge["reason"],
            }
        )


def routing_from_documents(
    policy_document: Any,
    model_document: Any,
    declaration: AdapterDeclaration,
) -> RoutingTable:
    """Compile path-independent documents into one immutable routing table."""
    policy = _validate_policy(policy_document)
    model_tiers, fallbacks = _validate_model_map(model_document, declaration)
    return RoutingTable(
        adapter=declaration.id,
        policy=policy,
        model_tiers=model_tiers,
        fallbacks=fallbacks,
    )


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RoutingError("missing {}: {}".format(label, path)) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RoutingError("invalid {}: {}".format(label, error)) from error


def load_routing(adapter: str, root: Path = ROOT) -> RoutingTable:
    if not isinstance(adapter, str) or ADAPTER_ID_PATTERN.fullmatch(adapter) is None:
        raise RoutingError("adapter must be a stable adapter ID")
    root = Path(root)
    adapter_directory = root / "adapters" / adapter
    try:
        declaration = load_adapter(adapter_directory / "adapter.json")
    except AdapterContractError as error:
        raise RoutingError("invalid adapter declaration: {}".format(error)) from error
    if declaration.id != adapter:
        raise RoutingError("adapter selector does not match declaration")
    policy = _load_json(root / "core/routing/policy.json", "routing policy")
    models = _load_json(adapter_directory / "models.json", "adapter model map")
    return routing_from_documents(policy, models, declaration)


def resolve(
    adapter: str,
    work_class: str,
    *,
    root: Path = ROOT,
    availability_overrides: Optional[Sequence[Mapping[str, str]]] = None,
) -> Mapping[str, Any]:
    return load_routing(adapter, root).resolve(work_class, availability_overrides)


def fallback(
    adapter: str,
    tier: str,
    *,
    root: Path = ROOT,
    availability_overrides: Optional[Sequence[Mapping[str, str]]] = None,
) -> Mapping[str, Any]:
    return load_routing(adapter, root).fallback(tier, availability_overrides)
