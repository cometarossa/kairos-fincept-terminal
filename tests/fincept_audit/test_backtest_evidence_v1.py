"""The allowlisted evidence envelope: what is copied, and everything that is refused."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

from tools.fincept_audit import backtest_evidence_v1 as evidence
from tools.fincept_audit import backtest_provider_probe_v1 as probe

ROOT = Path(__file__).resolve().parents[2]
HAVE_PROVIDER_DEPS = all(importlib.util.find_spec(name) for name in ("numpy", "pandas"))


def scenario(name="next_open_costs", **changes):
    item = {
        "scenario": name, "bars": 160, "trades": 3, "exit_reasons": ["signal"],
        "exit_bars": [24, 81, 137], "periods_per_year": 365,
        "oracle_total_return": 0.13091580863076163, "oracle_total_fees": 619.0279160367897,
        "oracle_max_drawdown": 0.03267130931081698,
        "oracle_sharpe_as_stated_by_provider": 5.3795184384714,
        "oracle_sharpe_arithmetic_mean_convention": 4.720910593662738,
        "network_attempts_denied": 0, "status": "ORIGINAL_PROVIDER_MATCHES_EXACT_ORACLE",
        "provider_using_synthetic_data": False, "provider_data_source": "kairos_synthetic_fixture",
        "provider_total_slippage": 0,
        # A field the envelope must never carry forward.
        "private_note": "do not forward",
    }
    item.update(changes)
    return item


def probe_result(*scenarios):
    return {"schema": probe.SCHEMA, "source_kind": "SYNTHETIC_FIXTURE_NOT_MARKET_DATA",
            "scientific_status": "NOT_EVALUATED", "broker_authority": False,
            "promotion_eligible": False, "scenario_count": len(scenarios) or 1,
            "scenarios": list(scenarios) or [scenario()],
            "operator_comment": "also not forwarded"}


def rehash(envelope):
    envelope["evidence_sha256"] = evidence._self_hash(envelope)
    return envelope


class BuildTests(unittest.TestCase):
    def test_envelope_has_exactly_the_allowlisted_fields_and_fixed_labels(self):
        envelope = evidence.build(probe_result())
        self.assertEqual(set(envelope), evidence.ENVELOPE_FIELDS)
        self.assertEqual(envelope["schema_version"], "kairos_fincept_backtest_evidence_v1")
        self.assertEqual(envelope["tool_id"], "fincept.research.backtest.sma_crossover.fixture.v1")
        self.assertEqual(envelope["dataset_class"], "SYNTHETIC_FIXTURE")
        self.assertEqual(envelope["scientific_status"], "NOT_EVALUATED")
        self.assertIs(envelope["broker_authority"], False)
        self.assertIs(envelope["promotion_eligible"], False)
        self.assertEqual(envelope["cost"], {"external_api_calls": 0, "provider_credits": 0})
        self.assertEqual(envelope["quality_flags"], ["SYNTHETIC", "NOT_MARKET_OBSERVED",
                                                     "NO_PIT_CERTIFICATION", "NO_INDEPENDENT_EVALUATOR"])
        self.assertEqual(envelope["sources"], probe.PINNED_SOURCES)
        self.assertEqual(envelope["fixtures"], probe.FIXTURE_SHA256)

    def test_only_allowlisted_scenario_values_are_copied(self):
        envelope = evidence.build(probe_result())
        item = envelope["result"]["scenarios"][0]
        self.assertEqual(set(item), evidence.SCENARIO_FIELDS)
        self.assertEqual(item["name"], "next_open_costs")
        self.assertEqual(item["sharpe_cagr_based"], 5.3795184384714)
        text = evidence.canonical(envelope).decode()
        for leaked in ("private_note", "do not forward", "operator_comment", "exit_bars",
                       "arithmetic", "provider_data_source", "kairos_synthetic_fixture"):
            self.assertNotIn(leaked, text)
        self.assertIs(envelope["result"]["provider_flags_fixture_as_market_data"], True)

    def test_envelope_is_deterministic_and_round_trips_as_text(self):
        first = evidence.build(probe_result(scenario(), scenario("take_profit", exit_reasons=["signal", "take_profit"])))
        second = evidence.build(probe_result(scenario(), scenario("take_profit", exit_reasons=["signal", "take_profit"])))
        self.assertEqual(first, second)
        self.assertEqual(len(first["evidence_sha256"]), 64)
        self.assertEqual(evidence.loads(evidence.canonical(first).decode()), first)
        changed = evidence.build(probe_result(scenario(oracle_total_fees=619.03)))
        self.assertNotEqual(changed["evidence_sha256"], evidence.build(probe_result())["evidence_sha256"])

    def test_unverified_or_networked_probe_results_are_not_packaged(self):
        cases = {
            "NOT_A_PROBE_RESULT": {"schema": "something_else", "scenarios": [scenario()]},
            "PROBE_RESULT_HAS_NO_SCENARIOS": {"schema": probe.SCHEMA, "scenarios": []},
            "SCENARIO_NOT_VERIFIED": probe_result(scenario(status="FAILED_OR_UNVERIFIED")),
            "SCENARIO_ATTEMPTED_NETWORK": probe_result(scenario(network_attempts_denied=1)),
            "INVALID_SCENARIO_NUMBER:total_return": probe_result(scenario(oracle_total_return=float("nan"))),
            "INVALID_SCENARIO_NUMBER:sharpe_cagr_based": probe_result(scenario(oracle_sharpe_as_stated_by_provider=None)),
            "INVALID_SCENARIO_NAME": probe_result(scenario(), scenario()),
            "INVALID_SCENARIO_INTEGER:trades": probe_result(scenario(trades=0)),
        }
        for reason, source in cases.items():
            with self.subTest(reason=reason):
                with self.assertRaises(evidence.EvidenceRejected) as raised:
                    evidence.build(source)
                self.assertIn(str(raised.exception), (reason, "NON_FINITE_NUMBER"))
        with self.assertRaises(evidence.EvidenceRejected):
            evidence.build(["not", "a", "dict"])


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.good = evidence.build(probe_result())

    def rejected(self, mutate, reason, keep_hash=False):
        envelope = copy.deepcopy(self.good)
        mutate(envelope)
        if not keep_hash:
            rehash(envelope)
        with self.assertRaises(evidence.EvidenceRejected) as raised:
            evidence.validate(envelope)
        self.assertEqual(str(raised.exception), reason)

    def test_authority_and_label_escalations_are_refused_even_with_a_fresh_hash(self):
        for key, value in (("broker_authority", True), ("promotion_eligible", True),
                           ("scientific_status", "EVALUATED"), ("dataset_class", "MARKET_DATA"),
                           ("rights", "LICENSED"), ("capability", "broker.order"),
                           ("tool_id", "fincept.live.backtest"), ("schema_version", "v2"),
                           ("observed_at", "2024-06-08T00:00:00Z"), ("broker_authority", 0),
                           ("promotion_eligible", None)):
            with self.subTest(key=key, value=value):
                self.rejected(lambda e: e.__setitem__(key, value), "INVALID_FIXED_FIELD:" + key)

    def test_unknown_and_missing_fields_are_refused_at_every_level(self):
        self.rejected(lambda e: e.__setitem__("signal", "BUY"), "INVALID_ENVELOPE_FIELDS", keep_hash=True)
        self.rejected(lambda e: e.pop("quality_flags"), "INVALID_ENVELOPE_FIELDS", keep_hash=True)
        self.rejected(lambda e: e["result"].__setitem__("recommendation", "long"), "INVALID_RESULT_FIELDS")
        self.rejected(lambda e: e["result"].pop("comparison"), "INVALID_RESULT_FIELDS")
        self.rejected(lambda e: e["result"]["scenarios"][0].__setitem__("order", {}), "INVALID_SCENARIO_FIELDS")
        self.rejected(lambda e: e["result"]["scenarios"][0].pop("bars"), "INVALID_SCENARIO_FIELDS")
        self.rejected(lambda e: e["cost"].__setitem__("extra", 0), "NONZERO_OR_INVALID_COST")
        self.rejected(lambda e: e["cost"].__setitem__("provider_credits", 1), "NONZERO_OR_INVALID_COST")
        self.rejected(lambda e: e["cost"].__setitem__("external_api_calls", False), "NONZERO_OR_INVALID_COST")

    def test_sources_fixtures_and_flags_must_be_the_pinned_ones(self):
        self.rejected(lambda e: e["sources"].__setitem__("vectorbt/vbt_portfolio.py", "0" * 64),
                      "UNPINNED_OR_CHANGED_SOURCES")
        self.rejected(lambda e: e["sources"].__setitem__("evil.py", "0" * 64), "UNPINNED_OR_CHANGED_SOURCES")
        self.rejected(lambda e: e["fixtures"].pop("130"), "UNPINNED_OR_CHANGED_FIXTURES")
        self.rejected(lambda e: e["quality_flags"].remove("SYNTHETIC"), "INVALID_QUALITY_FLAGS")
        self.rejected(lambda e: e.__setitem__("quality_flags", tuple(e["quality_flags"])), "INVALID_QUALITY_FLAGS")

    def test_numbers_must_be_real_finite_and_in_range(self):
        first = lambda e: e["result"]["scenarios"][0]
        for key, value in (("total_return", True), ("total_return", "0.1"), ("total_return", -1.5),
                           ("max_drawdown", 1.2), ("total_fees", -1.0), ("sharpe_cagr_based", 1e9)):
            with self.subTest(key=key, value=value):
                self.rejected(lambda e: first(e).__setitem__(key, value), "INVALID_SCENARIO_NUMBER:" + key)
        for key, value in (("bars", 160.0), ("bars", 5), ("trades", True), ("periods_per_year", 0)):
            with self.subTest(key=key, value=value):
                self.rejected(lambda e: first(e).__setitem__(key, value), "INVALID_SCENARIO_INTEGER:" + key)
        # NaN / infinity cannot even be hashed canonically.
        self.rejected(lambda e: first(e).__setitem__("total_fees", float("inf")),
                      "INVALID_SCENARIO_NUMBER:total_fees", keep_hash=True)

    def test_scenario_names_reasons_counts_and_comparison(self):
        first = lambda e: e["result"]["scenarios"][0]
        for name in ("", "Has Space", "../etc", "x" * 65, 7):
            with self.subTest(name=name):
                self.rejected(lambda e: first(e).__setitem__("name", name), "INVALID_SCENARIO_NAME")
        for reasons in ([], ["manual_override"], ["signal", "signal"], ["stop_loss", "signal"], "signal"):
            with self.subTest(reasons=reasons):
                self.rejected(lambda e: first(e).__setitem__("exit_reasons", reasons), "INVALID_EXIT_REASONS")
        self.rejected(lambda e: e["result"].__setitem__("scenario_count", 2), "SCENARIO_COUNT_MISMATCH")
        self.rejected(lambda e: e["result"].__setitem__("scenarios", []), "INVALID_SCENARIO_LIST")
        self.rejected(lambda e: e["result"].__setitem__("comparison", "PASS"), "INVALID_COMPARISON")
        self.rejected(lambda e: e["result"].__setitem__("relative_tolerance", 0.5), "INVALID_TOLERANCE")
        self.rejected(lambda e: e["result"].__setitem__("provider_flags_fixture_as_market_data", "yes"),
                      "INVALID_PROVIDER_FLAG")

    def test_self_hash_binds_every_value(self):
        self.rejected(lambda e: e["result"]["scenarios"][0].__setitem__("total_return", 0.2),
                      "EVIDENCE_HASH_MISMATCH", keep_hash=True)
        self.rejected(lambda e: e.__setitem__("evidence_sha256", "0" * 64), "EVIDENCE_HASH_MISMATCH", keep_hash=True)
        self.rejected(lambda e: e.__setitem__("evidence_sha256", "abc"), "INVALID_EVIDENCE_HASH", keep_hash=True)
        self.rejected(lambda e: e.__setitem__("evidence_sha256", None), "INVALID_EVIDENCE_HASH", keep_hash=True)

    def test_non_dict_and_oversize_envelopes(self):
        for value in (None, [], "text", 3):
            with self.assertRaises(evidence.EvidenceRejected):
                evidence.validate(value)
        big = probe_result(*[scenario("s%d" % i) for i in range(evidence.MAX_SCENARIOS + 1)])
        with self.assertRaises(evidence.EvidenceRejected) as raised:
            evidence.build(big)
        self.assertEqual(str(raised.exception), "INVALID_SCENARIO_LIST")

    def test_validation_does_not_mutate_or_upgrade_the_envelope(self):
        before = copy.deepcopy(self.good)
        self.assertIs(evidence.validate(self.good), self.good)
        self.assertEqual(self.good, before)


class TextBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.text = evidence.canonical(evidence.build(probe_result())).decode()

    def test_duplicate_keys_constants_and_garbage_are_refused(self):
        duplicate = self.text.replace('"broker_authority":false',
                                      '"broker_authority":true,"broker_authority":false', 1)
        self.assertNotEqual(duplicate, self.text)
        cases = {
            "DUPLICATE_JSON_KEY": duplicate,
            "NON_FINITE_NUMBER": self.text.replace('"total_fees":619.0279160367897', '"total_fees":NaN', 1),
            "INVALID_JSON": self.text[:-1],
            "INVALID_ENVELOPE_FIELDS": "[]",
            "OVERSIZE_ENVELOPE": " " * (evidence.MAX_ENVELOPE_BYTES + 1),
        }
        for reason, text in cases.items():
            with self.subTest(reason=reason):
                with self.assertRaises(evidence.EvidenceRejected) as raised:
                    evidence.loads(text)
                self.assertEqual(str(raised.exception), reason)
        with self.assertRaises(evidence.EvidenceRejected):
            evidence.loads(b"bytes")

    def test_module_has_no_network_file_write_or_process_capability(self):
        source = (ROOT / "tools/fincept_audit/backtest_evidence_v1.py").read_text(encoding="utf-8")
        for forbidden in ("socket", "urllib", "requests", "subprocess", "open(", ".write_text",
                          ".write_bytes", "os.system", "eval(", "exec("):
            self.assertNotIn(forbidden, source)


@unittest.skipUnless(HAVE_PROVIDER_DEPS, "original provider needs numpy and pandas")
class RealProbeEnvelopeTests(unittest.TestCase):
    def test_real_probe_run_packages_into_a_valid_envelope(self):
        result = probe.run_all(ROOT / probe.BACKTESTING_RELATIVE)
        envelope = evidence.build(result)
        self.assertEqual(envelope["result"]["scenario_count"], 17)
        self.assertEqual([s["name"] for s in envelope["result"]["scenarios"]],
                         [s["scenario"] for s in result["scenarios"]])
        self.assertIs(envelope["result"]["provider_flags_fixture_as_market_data"], True)
        self.assertLess(len(evidence.canonical(envelope)), evidence.MAX_ENVELOPE_BYTES // 2)
        self.assertEqual(evidence.loads(json.dumps(envelope)), envelope)


if __name__ == "__main__":
    unittest.main()
