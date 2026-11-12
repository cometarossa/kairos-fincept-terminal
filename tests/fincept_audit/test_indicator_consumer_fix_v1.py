"""Source identity and integration assertions for the original ConditionEvaluator.

Not a trading, deployment, broker or independent runtime verification.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONSUMER = ROOT / "fincept-qt/src/algo_engine/ConditionEvaluator.cpp"
TEST = ROOT / "tools/fincept_audit/qt_unit_harness/tst_indicator_consumer_fix.cpp"
CMAKE = ROOT / "tools/fincept_audit/qt_unit_harness/CMakeLists.txt"
EXPECTED_CONSUMER_BLOB = "1ae2adbd70fa143f528928338184da336ca0bc6d"


def git_blob(path: Path) -> str:
    b = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(b)).encode("ascii") + b"\x00" + b).hexdigest()


class ConsumerIntegrationSourceTest(unittest.TestCase):
    def test_consumer_source_is_original_and_does_not_use_previous_map(self):
        self.assertEqual(git_blob(CONSUMER), EXPECTED_CONSUMER_BLOB)
        source = CONSUMER.read_text(encoding="utf-8")
        self.assertIn("window = candles.mid(0, candles.size() - offset)", source)
        self.assertIn("r.current.value(field, kNaN)", source)
        self.assertNotIn("r.previous.value(", source)

    def test_native_consumer_harness_compiles_real_engine_and_evaluator(self):
        cmake = CMAKE.read_text(encoding="utf-8")
        for fragment in (
            "fincept_add_test(tst_indicator_consumer_fix",
            'src/algo_engine/ConditionEvaluator.cpp"',
            'src/algo_engine/IndicatorEngine.cpp"',
            "Qt6::Gui",
            "set_tests_properties(tst_indicator_consumer_fix PROPERTIES TIMEOUT 30)",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, cmake)

    def test_covered_crossings_and_false_falling_signal(self):
        source = TEST.read_text(encoding="utf-8")
        for fragment in (
            'above.op = "crosses_above"',
            'below.op = "crosses_below"',
            'condition.op = "falling"',
            "ConditionEvaluator::evaluate_single(above, prefix)",
            "ConditionEvaluator::evaluate_single(below, prefix)",
            "ConditionEvaluator::evaluate_single(condition, prefix)",
            "QCOMPARE(up_crossings + down_crossings, 20)",
            "QCOMPARE(forbidden_triggers, 0)",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, source)
        for forbidden in (
            "BrokerRegistry", "ExecuteMarketOrder", "QNetworkAccessManager",
            "IG_DEMO", "IG_LIVE", "QWebEngine", "QEXPECT_FAIL(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
