"""Assert independently generated Fraction reversal rows match the native Qt test."""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import unittest

from tools.fincept_audit import supertrend_reversal_reference_v1 as ref

ROOT = Path(__file__).resolve().parents[2]
CPP = ROOT / "tools/fincept_audit/qt_unit_harness/tst_indicator_temporal_contracts.cpp"


class ReversalReferenceSourceTests(unittest.TestCase):
    def test_generated_rows_are_identical_to_cpp(self):
        text = CPP.read_text(encoding="utf-8")
        self.assertEqual(text.count(ref.START), 1)
        self.assertEqual(text.count(ref.END), 1)
        start, end = text.index(ref.START), text.index(ref.END) + len(ref.END) + 1
        self.assertEqual(text[start:end], ref.cpp_rows())

    def test_reversal_fixture_four_transitions_and_both_directions(self):
        rows = ref.reference()
        self.assertEqual(len(rows), 200)
        self.assertTrue(all(isinstance(x, Fraction) for x, _ in rows[9:]))
        self.assertTrue(all(d in (-1, 1) for _, d in rows[9:]))
        flips = [(i, rows[i][1]) for i in range(10, len(rows))
                 if rows[i][1] != rows[i - 1][1]]
        self.assertEqual(flips, [(43, -1), (82, 1), (123, -1), (165, 1)])

    def test_native_contract_tests_all_prefixes_and_four_transitions(self):
        code = CPP.read_text(encoding="utf-8")
        for marker in (
            "QCOMPARE(reversals, 4)",
            "for (int bars = 12; bars <= candles.size(); ++bars)",
            "QCOMPARE(static_cast<int>(actual.current.value(\"direction\")), want.direction)",
            "QCOMPARE(static_cast<int>(current.previous.value(\"direction\")), prior_direction)",
            "reversal reference current line differs",
            "reversal reference previous line differs",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, code)
        self.assertNotIn("QEXPECT_FAIL(", code)


if __name__ == "__main__":
    unittest.main()
