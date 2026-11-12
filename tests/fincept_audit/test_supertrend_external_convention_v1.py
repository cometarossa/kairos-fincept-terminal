"""Exact synthetic-source and convention QA for #46 external Supertrend review.

All fixtures are synthetic and the CLI is a read-only local QtCore executable.
The test suite does not require a host Qt installation or broker access to run.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import random
import unittest

from tools.fincept_audit import supertrend_external_convention_audit_v1 as ref
from tools.fincept_audit.supertrend_external_audit import run_native_convention_audit_v1 as audit

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/audits/FINCEPT_SUPERTREND_EXTERNAL_CONVENTION_AGGREGATES_20261112.json"
CMAKE = ROOT / "tools/fincept_audit/supertrend_external_audit/CMakeLists.txt"
CPP = ROOT / "tools/fincept_audit/supertrend_external_audit/native_prefix_dump.cpp"


class ExternalSupertrendAudit(unittest.TestCase):
    def test_exact_candidate_engine_source_pin(self):
        self.assertEqual(audit.git_blob(audit.CODE), audit.CANDIDATE_GIT_BLOB)
        self.assertEqual(audit.CANDIDATE_GIT_BLOB,
                         "7d3c32ca4d9f4a265a77dbbe56d59b52129ecfb5")

    def test_reversible_fixture_and_shock_matrix_reproduces(self):
        for kind in audit.CASES:
            with self.subTest(kind=kind):
                d = ref.diagnostics(kind)
                for label, (direction, line) in audit.EXPECTED_COUNTS[kind].items():
                    self.assertEqual(
                        (d[label]["direction_diff_count"],
                         d[label]["line_diff_count"]),
                        (direction, line),
                    )
                self.assertEqual(
                    d["tradingview_state_EMA_matched_seed"]["direction_diff_count"], 0)
                self.assertEqual(
                    d["tradingview_state_EMA_matched_seed"]["line_diff_count"], 0)

    def test_matched_ema_and_initial_state_parity_on_32_bounded_synthetic_stresses(self):
        # 32 deterministic independent synthetic gap + range fixtures, no market data.
        for seed in range(32):
            rnd = random.Random(20261112 + seed)
            rows = []
            close = 10000
            for i in range(240):
                open_ = close + rnd.randint(-500, 500)
                close = open_ + rnd.randint(-700, 700)
                high = max(open_, close) + rnd.randint(0, 350)
                low = min(open_, close) - rnd.randint(0, 350)
                rows.append((open_, high, low, close, 1000 + i))
            direct = ref.compute(rows, smoothing="ema", variant="candidate", initial_dir=1)
            reference = ref.compute(rows, smoothing="ema", variant="tradingview", initial_dir=1)
            with self.subTest(seed=seed):
                self.assertEqual(direct, reference)

    def test_rma_smoothing_and_seed_choice_are_observable_differences(self):
        for kind in audit.CASES:
            with self.subTest(kind=kind):
                data = ref.make_fixture(kind)
                candidate = ref.compute(data, smoothing="ema", variant="candidate", initial_dir=1)
                default_tv = ref.compute(data, smoothing="wilder",
                                         variant="tradingview", initial_dir=-1)
                self.assertTrue(
                    any(candidate[i] != default_tv[i] for i in range(ref.PERIOD, len(data)))
                )
        self.assertEqual(audit.EXPECTED_COUNTS["shock"][
            "tradingview_state_Wilder_matched_seed"], (43, 167))

    def test_native_schema_parse_and_locale_fail_closed(self):
        header = audit.CLI_HEADER + "\n"
        valid = header + "".join("%d,%.17g,%d\n" % (i, 100.0 + .05*i, 1)
                                 for i in range(10, 200))
        parsed = audit.parse_native_output(valid)
        self.assertEqual(len(parsed), 190)
        self.assertEqual(parsed[10], (100.5, 1))
        for bad in (
            valid.replace("10,100.5,1", "10,100,5,1"),
            valid.replace("10,100.5,1", "10,nan,1"),
            valid.replace("10,100.5,1", "10,100.5,0"),
            valid.replace("10,100.5,1", "12,100.5,1"),
            header + "10,100.5,1\n",
            valid.replace(audit.CLI_HEADER, "wrong_header"),
        ):
            with self.subTest(malformed=bad[:70]):
                with self.assertRaises(ValueError):
                    audit.parse_native_output(bad)

    def test_native_build_is_source_real_and_offline(self):
        cmake = CMAKE.read_text(encoding="utf-8")
        cpp = CPP.read_text(encoding="utf-8")
        for fragment in (
            "find_package(Qt6 6.8.3 EXACT REQUIRED COMPONENTS Core)",
            'IndicatorEngine.cpp")',
            "native_prefix_dump.cpp",
            "Qt6::Core",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, cmake)
        for fragment in (
            "IndicatorEngine::compute(",
            "series.mid(0, n)",
            'std::setlocale(LC_NUMERIC, "C")',
            "if (series.size() != 200)",
            "c.is_closed = true",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, cpp)
        for forbidden in (
            "BrokerRegistry", "ExecuteMarketOrder", "QNetworkAccessManager",
            "QWebEngine", "IG_DEMO", "IG_LIVE",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, cpp)

    def test_aggregate_report_has_no_prices_or_broker_claims(self):
        report = json.loads(DOC.read_text(encoding="utf-8"))
        self.assertEqual(report["schema"], audit.SCHEMA)
        self.assertEqual(report["indicator_engine_git_blob"], audit.CANDIDATE_GIT_BLOB)
        self.assertEqual(report["status"], "RESEARCH_ONLY_NOT_PIT_NOT_TRADING")
        self.assertEqual([x["name"] for x in report["fixtures"]], list(audit.CASES))
        for item in report["fixtures"]:
            with self.subTest(kind=item["name"]):
                self.assertEqual(item["native_prefixes"], 190)
                self.assertEqual(item["cpp_vs_fraction_direction_mismatches"], 0)
                self.assertLess(item["cpp_vs_fraction_max_abs_error"], 1e-8)
                self.assertEqual(item["synthetic_source_rows"], 200)
                for label, (dir_changes, line_changes) in audit.EXPECTED_COUNTS[item["name"]].items():
                    self.assertEqual(
                        (item["comparison"][label]["direction_diff_count"],
                         item["comparison"][label]["line_diff_count"]),
                        (dir_changes, line_changes))
                self.assertEqual(set(item), {
                    "name", "synthetic_source_rows", "native_prefixes",
                    "cpp_vs_fraction_direction_mismatches", "cpp_vs_fraction_max_abs_error",
                    "comparison",
                })


if __name__ == "__main__":
    unittest.main()
