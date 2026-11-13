"""Guard identity / source-boundary contracts for experimental Supertrend validation.

This is NOT a replacement for native Qt tests or permission to merge.
"""
from pathlib import Path
import hashlib
import unittest

ROOT = Path(__file__).resolve().parents[2]
CPP = ROOT / "fincept-qt/src/algo_engine/IndicatorEngine.cpp"
NATIVE_TEST = ROOT / "tools/fincept_audit/qt_unit_harness/tst_supertrend_input_guard.cpp"
CMAKE = ROOT / "tools/fincept_audit/qt_unit_harness/CMakeLists.txt"

BASE_BLOB = "7d3c32ca4d9f4a265a77dbbe56d59b52129ecfb5"
GUARD_BLOB = "e33cf1a6151012adb126ab05846b035d8efa16b0"


def git_blob(path):
    b = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()


class SupertrendInputGuardSource(unittest.TestCase):
    def test_guard_candidate_blob_is_pinned_and_distinct_from_old(self):
        self.assertEqual(git_blob(CPP), GUARD_BLOB)
        self.assertNotEqual(GUARD_BLOB, BASE_BLOB)

    def test_guard_scoped_to_supertrend_branch(self):
        s = CPP.read_text()
        start = s.index('    if (name == "SUPERTREND") {')
        end = s.index('    if (name == "AROON")', start)
        guard = s[start:end]
        self.assertIn("Supertrend: non-finite OHLC", guard)
        self.assertIn("Supertrend: inconsistent OHLC", guard)
        self.assertIn("Supertrend: invalid period", guard)
        self.assertIn("Supertrend: invalid multiplier type", guard)
        self.assertIn("multiplier must be finite and positive", guard)
        self.assertIn("return compute_supertrend(high, low, close, period, mult);", guard)
        self.assertIn("std::isfinite(candle.open)", guard)
        self.assertIn("std::isfinite(candle.high)", guard)
        self.assertIn("std::isfinite(candle.low)", guard)
        self.assertIn("std::isfinite(candle.close)", guard)
        self.assertLess(guard.index("std::isfinite(candle.open)"),
                        guard.index("return compute_supertrend("))

    def test_real_production_engine_is_in_native_target(self):
        c = CMAKE.read_text()
        self.assertIn("fincept_add_test(tst_supertrend_input_guard", c)
        self.assertIn("tst_supertrend_input_guard.cpp", c)
        self.assertIn('src/algo_engine/IndicatorEngine.cpp"', c)
        self.assertIn("set_tests_properties(tst_supertrend_input_guard PROPERTIES TIMEOUT 30)", c)

    def test_native_guards_are_required_without_xfail(self):
        src = NATIVE_TEST.read_text()
        self.assertNotIn("QEXPECT_FAIL(", src)
        for method in (
            "nonfinite_prices_fail_closed",
            "structurally_invalid_candles_fail_closed",
            "malformed_period_and_multiplier_fail_closed",
            "asof_prefix_does_not_inspect_future_corruption",
            "valid_history_and_first_warmup",
            "flat_and_zero_volume_are_not_silently_marked_bad_prices",
        ):
            with self.subTest(method=method):
                self.assertIn(method, src)
        for forbidden in (
            "BrokerRegistry", "ExecuteMarketOrder", "QNetworkAccessManager",
            "QWebEngine", "IG_DEMO", "IG_LIVE", "QApplication",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
