"""Offline source/provenance contracts for frozen TRAIN-era CC0 signal replay.

Does not open the research quarantine or require market archives in CI.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.fincept_audit.recorded_replay import run_public_cc0_replay_v1 as replay

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "docs/audits/FINCEPT_CC0_RECORDED_SIGNAL_AGGREGATES_20261112.json"
CPP = ROOT / "tools/fincept_audit/recorded_replay/recorded_conditions.cpp"
CMAKE = ROOT / "tools/fincept_audit/recorded_replay/CMakeLists.txt"
CONSUMER = ROOT / "fincept-qt/src/algo_engine/ConditionEvaluator.cpp"
ENGINE = ROOT / "fincept-qt/src/algo_engine/IndicatorEngine.cpp"


class FrozenCC0ReplayContract(unittest.TestCase):
    def test_source_and_consumer_git_identities(self):
        self.assertEqual(replay.git_blob(ENGINE), replay.FIX_ENGINE_BLOB)
        self.assertEqual(replay.git_blob(CONSUMER), replay.CONSUMER_BLOB)
        self.assertEqual(
            replay.SOURCE_SHA256,
            "d9317c8fb2d63b9b00db5f933b6c9639d2bf7ea3b918169bb5cec5903dce85a1",
        )
        self.assertEqual(set(replay.MEMBERS), {"AAPL", "IBM", "SPY"})
        self.assertEqual(replay.EXPECTED_ROWS, 974)
        self.assertEqual(replay.EXPECTED_REPLAY_ROWS, 722)

    def test_native_replay_compiles_both_engines_with_original_condition_evaluator(self):
        c = CMAKE.read_text(encoding="utf-8")
        for fragment in (
            "OLD_INDICATOR_ENGINE_SOURCE",
            "recorded_conditions.cpp",
            "ConditionEvaluator.cpp",
            "IndicatorEngine.cpp",
            "find_package(Qt6 6.8.3 EXACT REQUIRED COMPONENTS Core Gui)",
            "recorded_replay_",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, c)
        self.assertIn("message(FATAL_ERROR", c)

    def test_cpp_replay_is_asof_closed_bars_and_broker_free(self):
        cpp = CPP.read_text(encoding="utf-8")
        for fragment in (
            "ConditionEvaluator::evaluate_single",
            "all.mid(0, n)",
            "candle.is_closed = true",
            "date < QDate(2014, 1, 1)",
            "date > QDate(2017, 11, 10)",
            "dates[n - 1] < QDate(2015, 1, 1)",
            "INVALID_OHLCV",
            "INVALID_CONDITION",
            "EXPECTED_REPLAY_WINDOW_NOT_PRESENT",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, cpp)
        for prohibited in ("BrokerRegistry", "place_order", "QNetworkAccessManager",
                           "IG_DEMO", "IG_LIVE", "QWebEngine", "QApplication"):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, cpp)

    def test_signal_mask_parser_and_delta_oracle(self):
        header = "#schema=fincept_recorded_signal_mask_v1;rules=" + "|".join(replay.RULES)
        old = replay.parse_masks(header + "\n2015-01-02,5\n2015-01-05,64\n")
        fixed = replay.parse_masks(header + "\n2015-01-02,9\n2015-01-05,320\n")
        differences = {row["rule"]: row for row in replay.compare(old, fixed)}
        self.assertEqual(differences["ADX_DI_CROSS_UP"]["changed"], 0)
        self.assertEqual(differences["ST_VALUE_FALLING"]["old_only"], 1)
        self.assertEqual(differences["ST_VALUE_RISING"]["fixed_only"], 1)
        self.assertEqual(differences["ST_LINE_ABOVE_CLOSE"]["fixed_only"], 1)
        self.assertEqual(differences["ST_LONG_STATE"]["changed"], 0)

    def test_replay_fails_closed_for_malformed_masks(self):
        header = "#schema=fincept_recorded_signal_mask_v1;rules=" + "|".join(replay.RULES)
        for input_text in (
            "", "wrong\n2015-01-02,1\n", header + "\n2015-01-02,abc\n",
            header + "\n2015-01-02,512\n",
            header + "\n2015-01-02,1\n2015-01-02,1\n",
            header + "\n2018-01-02,1\n",
            header + "\n2015-01-05,1\n2015-01-02,1\n",
        ):
            with self.subTest(input_text=input_text[:30]):
                with self.assertRaises(ValueError):
                    replay.parse_masks(input_text)

    def test_zip_member_crc_mismatch_rejected_without_market_data(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("Stocks/aapl.us.txt",
                             "Date,Open,High,Low,Close,Volume,OpenInt\n")
        buf.seek(0)
        with zipfile.ZipFile(buf) as archive:
            with self.assertRaisesRegex(ValueError, "SOURCE_MEMBER_CRC_OR_SIZE_MISMATCH"):
                replay.input_from_member(archive, "Stocks/aapl.us.txt",
                                         archive.getinfo("Stocks/aapl.us.txt").CRC ^ 1)

    def test_sanitized_aggregate_only_report_is_pinned(self):
        report = json.loads(AUDIT.read_text(encoding="utf-8"))
        self.assertEqual(report["schema"], replay.SCHEMA)
        self.assertEqual(report["archive_sha256"], replay.SOURCE_SHA256)
        self.assertEqual(report["source_limit"], "2017-11-10")
        self.assertEqual(report["status"], "DEVELOPMENT_DIAGNOSTICS_ONLY")
        self.assertEqual(len(report["instruments"]), 3)
        expected_changes = {"AAPL": (567, 1653), "IBM": (608, 1880), "SPY": (561, 1427)}
        expected_keys = {
            "symbol", "member", "crc32", "source_rows", "source_first",
            "source_last", "input_sha256", "replay_rows", "replay_first",
            "replay_last", "signal_changes", "changed_dates_any_rule",
            "unchanged_dates_all_rules", "rules",
        }
        for inst in report["instruments"]:
            with self.subTest(inst=inst["symbol"]):
                sym = inst["symbol"]
                self.assertEqual(set(inst), expected_keys)
                self.assertEqual(inst["source_rows"], 974)
                self.assertEqual(inst["replay_rows"], 722)
                self.assertEqual(
                    (inst["changed_dates_any_rule"], inst["signal_changes"]),
                    expected_changes[sym],
                )
                self.assertEqual(inst["changed_dates_any_rule"] +
                                 inst["unchanged_dates_all_rules"], 722)
                by_rule = {r["rule"]: r for r in inst["rules"]}
                self.assertEqual(set(by_rule), set(replay.RULES))
                self.assertEqual(by_rule["ADX_DI_CROSS_UP"]["changed"], 0)
                self.assertEqual(by_rule["ADX_DI_CROSS_DOWN"]["changed"], 0)
                self.assertEqual(
                    (by_rule["ST_LONG_STATE"]["old_true"],
                     by_rule["ST_LONG_STATE"]["fixed_true"]),
                    replay.EXPECTED_LONG_COUNTS[sym],
                )


if __name__ == "__main__":
    unittest.main()
