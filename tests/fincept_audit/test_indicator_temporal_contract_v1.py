"""Exact-head source contracts for the strict C++ fix candidate.

These are structural checks only, not a release or trading permission.
"""
from pathlib import Path
import hashlib
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "tools/fincept_audit/qt_unit_harness/tst_indicator_temporal_contracts.cpp"
CMAKE = ROOT / "tools/fincept_audit/qt_unit_harness/CMakeLists.txt"
ENGINE = ROOT / "fincept-qt/src/algo_engine/IndicatorEngine.cpp"
EXPECTED_ENGINE_BLOB = "e33cf1a6151012adb126ab05846b035d8efa16b0"


def git_blob(path: Path) -> str:
    b = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\x00" + b).hexdigest()


class TemporalContractsSourceTests(unittest.TestCase):
    def test_engine_fix_candidate_blob_is_pinned(self):
        self.assertEqual(git_blob(ENGINE), EXPECTED_ENGINE_BLOB)

    def test_real_engine_is_linked_into_registered_ctest(self):
        cmake = CMAKE.read_text(encoding="utf-8")
        self.assertIn("fincept_add_test(tst_indicator_temporal_contracts", cmake)
        self.assertIn("IndicatorEngine.cpp", cmake)
        self.assertIn("set_tests_properties(tst_indicator_temporal_contracts", cmake)
        self.assertIn("TIMEOUT 30", cmake)

    def test_fixture_matches_reference_generator_formula(self):
        cpp = PROBE.read_text(encoding="utf-8")
        for fragment in (
            "10000 + 9 * i + (((i * 37) % 23) - 11) * 15 + (((i * i) % 7) - 3) * 8",
            "close - 25 + (i % 6) * 10",
            "std::max(open, close) + 20 + (i % 4) * 10",
            "std::min(open, close) - 15 - (i % 3) * 10",
            "1000 + ((i * 53) % 200) + (i % 5) * 40",
            "out.reserve(120)",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, cpp)

    def test_asof_prefix_invariants_are_strict_and_broker_free(self):
        cpp = PROBE.read_text(encoding="utf-8")
        for fragment in (
            "candles.mid(0, n)",
            "candles.mid(0, n - 1)",
            'IndicatorEngine::compute("ADX"',
            'IndicatorEngine::compute("SUPERTREND"',
            'prior.current.value("plus_di")',
            "masked_crossovers",
            "long_line_falls",
            "QCOMPARE(broken_previous, 0)",
            "QCOMPARE(masked_crossovers, 0)",
            "QCOMPARE(long_line_falls, 0)",
            "QTEST_GUILESS_MAIN",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, cpp)
        self.assertNotIn("QEXPECT_FAIL(", cpp)
        for forbidden in (
            "ExecuteMarketOrder", "QNetworkAccessManager", "QWebEngine",
            "IG_DEMO", "IG_LIVE", "OrderValidator", "QApplication",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, cpp)


if __name__ == "__main__":
    unittest.main()
