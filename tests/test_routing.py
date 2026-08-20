import json
from pathlib import Path
from types import MappingProxyType
from unittest import TestCase

from kingstack.adapter_contract import AdapterDeclaration, CapabilityMatrix
from kingstack.routing import (
    RoutingError,
    fallback,
    resolve,
    routing_from_documents,
)


ROOT = Path(__file__).parents[1]


def declaration(adapter, model_tiers):
    return AdapterDeclaration(
        id=adapter,
        contract_version=1,
        render_module="example.render",
        native_home=".{}".format(adapter),
        owned_paths=("GUIDANCE.md",),
        model_tiers=model_tiers,
        capability_matrix=CapabilityMatrix(adapter_id=adapter, states=()),
        source=Path("adapter.json"),
        raw={},
    )


def portable_policy():
    return {
        "waiting": {"tier": "none", "effort": "none"},
        "mechanical": {"tier": "economical", "effort": "low"},
        "precise": {"tier": "balanced", "effort": "medium"},
        "judgment": {"tier": "frontier", "effort": "high"},
    }


def model_map(adapter="sample"):
    return {
        "adapter": adapter,
        "model_tiers": {
            "economical": "small",
            "balanced": "middle",
            "frontier": "large",
        },
        "fallbacks": [
            {
                "from": "balanced",
                "to": "economical",
                "reason": "balanced unavailable; use one adjacent lower tier",
            },
            {
                "from": "frontier",
                "to": "balanced",
                "reason": "frontier unavailable; use one adjacent lower tier",
            },
        ],
    }


class RoutingTest(TestCase):
    def test_checked_in_policy_is_exactly_portable(self):
        """A vendor token or extra policy field must make this contract fail."""
        document = json.loads(
            (ROOT / "core/routing/policy.json").read_text(encoding="utf-8")
        )
        self.assertEqual(document, portable_policy())
        serialized = json.dumps(document).lower()
        for foreign in (
            "claude",
            "codex",
            "haiku",
            "sonnet",
            "opus",
            "fable",
            "gpt-5.6",
        ):
            self.assertNotIn(foreign, serialized)

    def test_resolve_maps_both_adapters_and_returns_explainable_immutable_data(self):
        """A wrong model, effort, tier, class, or missing evidence must fail."""
        claude = resolve("claude", "mechanical", root=ROOT)
        codex = resolve("codex", "mechanical", root=ROOT)
        precise = resolve("codex", "precise", root=ROOT)
        waiting = resolve("codex", "waiting", root=ROOT)

        self.assertIsInstance(claude, MappingProxyType)
        self.assertEqual(claude["model"], "haiku")
        self.assertEqual(codex["model"], "gpt-5.6-luna")
        self.assertEqual(precise["effort"], "medium")
        self.assertEqual(precise["tier"], "balanced")
        self.assertEqual(precise["work_class"], "precise")
        self.assertIn("adapter default", precise["evidence"])
        self.assertIn("portable policy", precise["reason"])
        self.assertIsNone(waiting["model"])
        self.assertEqual(waiting["tier"], "none")
        with self.assertRaises(TypeError):
            precise["model"] = "changed"

    def test_fallback_is_one_adjacent_step_with_a_stable_reason(self):
        """Skipping a tier, using a vendor-global override, or varying output must fail."""
        first = fallback("codex", "frontier", root=ROOT)
        second = fallback("codex", "frontier", root=ROOT)

        self.assertEqual(first, second)
        self.assertIsInstance(first, MappingProxyType)
        self.assertEqual(first["from"], "frontier")
        self.assertEqual(first["tier"], "balanced")
        self.assertEqual(first["model"], "gpt-5.6-terra")
        self.assertIn("adjacent", first["reason"])
        with self.assertRaisesRegex(RoutingError, "no adjacent fallback"):
            fallback("codex", "economical", root=ROOT)

    def test_private_availability_override_is_injected_and_tier_scoped(self):
        """Ignoring or leaking a runtime-only alternate model must fail."""
        overrides = (
            {
                "tier": "frontier",
                "model": "fable",
                "reason": "fable is available in this private Claude runtime",
            },
        )
        overridden = resolve(
            "claude",
            "judgment",
            root=ROOT,
            availability_overrides=overrides,
        )
        default = resolve("claude", "judgment", root=ROOT)

        self.assertEqual(overridden["model"], "fable")
        self.assertIn("private runtime override", overridden["evidence"])
        self.assertIn("available", overridden["reason"])
        self.assertEqual(default["model"], "opus")
        checked_in = (ROOT / "adapters/claude/models.json").read_text(
            encoding="utf-8"
        ).lower()
        self.assertNotIn("fable", checked_in)
        self.assertNotIn("availability", checked_in)

    def test_unknown_work_class_and_tier_fail_visibly(self):
        """Silently defaulting an unknown selector must fail."""
        with self.assertRaisesRegex(RoutingError, "unknown work class"):
            resolve("codex", "unknown", root=ROOT)
        with self.assertRaisesRegex(RoutingError, "unknown tier"):
            fallback("codex", "unknown", root=ROOT)
        with self.assertRaisesRegex(RoutingError, "work class must be a stable ID"):
            resolve("codex", [], root=ROOT)
        with self.assertRaisesRegex(RoutingError, "tier must be a stable ID"):
            fallback("codex", [], root=ROOT)

    def test_policy_rejects_unknown_keys_types_and_nonportable_values(self):
        """Schema drift or model syntax in shared policy must fail at compile time."""
        cases = []
        unknown_top = portable_policy()
        unknown_top["vendor"] = {"tier": "economical", "effort": "low"}
        cases.append((unknown_top, "work classes"))
        unknown_entry = portable_policy()
        unknown_entry["precise"] = {
            "tier": "balanced",
            "effort": "medium",
            "model": "middle",
        }
        cases.append((unknown_entry, "keys"))
        wrong_type = portable_policy()
        wrong_type["precise"] = {"tier": "balanced", "effort": 2}
        cases.append((wrong_type, "strings"))
        vendor_value = portable_policy()
        vendor_value["precise"] = {"tier": "sonnet", "effort": "medium"}
        cases.append((vendor_value, "portable mapping"))

        models = model_map()
        adapter = declaration("sample", models["model_tiers"])
        for policy, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(RoutingError, message):
                    routing_from_documents(policy, models, adapter)

    def test_non_string_unknown_keys_raise_stable_routing_errors(self):
        """Diagnostic formatting must never leak TypeError for malformed keys."""
        policy_route = portable_policy()
        policy_route["precise"][7] = "bad"

        model_top = model_map()
        model_top[7] = "bad"

        fallback_record = model_map()
        fallback_record["fallbacks"][0][7] = "bad"

        cases = (
            (
                "policy route",
                lambda: routing_from_documents(
                    policy_route,
                    model_map(),
                    declaration("sample", model_map()["model_tiers"]),
                ),
            ),
            (
                "model top level",
                lambda: routing_from_documents(
                    portable_policy(),
                    model_top,
                    declaration("sample", model_top["model_tiers"]),
                ),
            ),
            (
                "fallback record",
                lambda: routing_from_documents(
                    portable_policy(),
                    fallback_record,
                    declaration("sample", fallback_record["model_tiers"]),
                ),
            ),
            (
                "availability override",
                lambda: resolve(
                    "codex",
                    "precise",
                    root=ROOT,
                    availability_overrides=(
                        {
                            "tier": "balanced",
                            "model": "private",
                            "reason": "available",
                            7: "bad",
                        },
                    ),
                ),
            ),
        )
        for label, operation in cases:
            with self.subTest(label=label):
                with self.assertRaisesRegex(RoutingError, "keys must be strings"):
                    operation()

    def test_model_map_must_exactly_match_declaration_and_known_tiers(self):
        """A missing, extra, malformed, or declaration-divergent tier must fail."""
        cases = []
        missing = model_map()
        del missing["model_tiers"]["frontier"]
        cases.append((missing, declaration("sample", model_map()["model_tiers"]), "missing"))
        extra = model_map()
        extra["model_tiers"]["ultra"] = "huge"
        cases.append((extra, declaration("sample", model_map()["model_tiers"]), "extra"))
        malformed = model_map()
        malformed["model_tiers"]["balanced"] = "not a model"
        cases.append((malformed, declaration("sample", malformed["model_tiers"]), "model ID"))
        divergent = model_map()
        declared = dict(divergent["model_tiers"])
        declared["balanced"] = "different"
        cases.append((divergent, declaration("sample", declared), "declaration"))
        unknown_key = model_map()
        unknown_key["availability"] = {"frontier": "private"}
        cases.append((unknown_key, declaration("sample", unknown_key["model_tiers"]), "unknown keys"))

        for models, adapter, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(RoutingError, message):
                    routing_from_documents(portable_policy(), models, adapter)

    def test_fallback_graph_rejects_duplicates_ambiguity_nonadjacency_and_cycles(self):
        """Any graph that permits zero, two, or cyclic fallback choices must fail."""
        cases = []
        duplicate = model_map()
        duplicate["fallbacks"].append(dict(duplicate["fallbacks"][0]))
        cases.append((duplicate, "duplicate"))
        ambiguous = model_map()
        ambiguous["fallbacks"].append(
            {"from": "frontier", "to": "economical", "reason": "second choice"}
        )
        cases.append((ambiguous, "ambiguous"))
        nonadjacent = model_map()
        nonadjacent["fallbacks"][1]["to"] = "economical"
        cases.append((nonadjacent, "adjacent"))
        cycle = model_map()
        cycle["fallbacks"] = [
            {"from": "balanced", "to": "frontier", "reason": "up"},
            {"from": "frontier", "to": "balanced", "reason": "down"},
        ]
        cases.append((cycle, "cycle"))
        malformed = model_map()
        malformed["fallbacks"][0]["reason"] = ""
        cases.append((malformed, "reason"))

        for models, message in cases:
            with self.subTest(message=message):
                adapter = declaration("sample", models["model_tiers"])
                with self.assertRaisesRegex(RoutingError, message):
                    routing_from_documents(portable_policy(), models, adapter)

    def test_availability_overrides_reject_ambiguous_and_malformed_records(self):
        """Two private choices for a tier or malformed values must fail."""
        cases = (
            (
                (
                    {"tier": "frontier", "model": "one", "reason": "available"},
                    {"tier": "frontier", "model": "two", "reason": "also available"},
                ),
                "ambiguous",
            ),
            (({"tier": "unknown", "model": "one", "reason": "available"},), "unknown tier"),
            (({"tier": "frontier", "model": "bad model", "reason": "available"},), "model ID"),
            (({"tier": "frontier", "model": "one", "reason": ""},), "reason"),
            (({"tier": "frontier", "model": "one", "reason": "ok", "path": "/tmp"},), "keys"),
        )
        for overrides, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(RoutingError, message):
                    resolve(
                        "claude",
                        "judgment",
                        root=ROOT,
                        availability_overrides=overrides,
                    )

    def test_waiting_validates_malformed_and_ambiguous_availability_overrides(self):
        """The no-model branch must not bypass caller-supplied validation."""
        cases = (
            (
                ({"tier": "frontier", "model": "bad model", "reason": "bad"},),
                "model ID",
            ),
            (
                (
                    {"tier": "frontier", "model": "one", "reason": "available"},
                    {"tier": "frontier", "model": "two", "reason": "also available"},
                ),
                "ambiguous",
            ),
        )
        for overrides, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(RoutingError, message):
                    resolve(
                        "codex",
                        "waiting",
                        root=ROOT,
                        availability_overrides=overrides,
                    )
