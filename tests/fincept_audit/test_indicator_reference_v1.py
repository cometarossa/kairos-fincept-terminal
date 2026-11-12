"""The reference generator and the table embedded in the native Qt test stay identical."""
from __future__ import annotations

from fractions import Fraction as F
from pathlib import Path
import unittest

from tools.fincept_audit import indicator_reference_v1 as ref

ROOT = Path(__file__).resolve().parents[2]
CPP = ROOT / "tools/fincept_audit/qt_unit_harness/tst_indicator_engine_reference.cpp"


class ReferenceTableTests(unittest.TestCase):
    def test_cpp_table_is_exactly_the_generated_one(self):
        text = CPP.read_text(encoding="utf-8")
        start, end = text.index(ref.BEGIN), text.index(ref.END) + len(ref.END) + 1
        self.assertEqual(text[start:end], ref.cpp_table())
        self.assertEqual(text.count(ref.BEGIN), 1)

    def test_cpp_fixture_formula_is_the_python_one(self):
        text = CPP.read_text(encoding="utf-8")
        for fragment in ("10000 + 9 * i + (((i * 37) % 23) - 11) * 15 + (((i * i) % 7) - 3) * 8",
                         "close - 25 + (i % 6) * 10", "+ 20 + (i % 4) * 10", "- 15 - (i % 3) * 10",
                         "1000 + ((i * 53) % 200) + (i % 5) * 40", "kBars = 120"):
            self.assertIn(fragment, text)

    def test_fixture_spot_values_worked_by_hand(self):
        rows = ref.fixture()
        self.assertEqual(len(rows), 120)
        self.assertEqual(rows[0], (9786, 9831, 9771, 9811, 1000))   # i = 0
        self.assertEqual(rows[1][3], 10038)                          # 10009 + 45 - 16
        self.assertEqual(rows[119][4], 1267)
        for o, h, l, c, v in rows:
            self.assertTrue(l < min(o, c) and h > max(o, c) and v > 0)

    def test_simple_indicators_agree_with_a_direct_recomputation(self):
        rows = ref.fixture()
        close = [F(r[3], 100) for r in rows]
        high = [F(r[1], 100) for r in rows]
        low = [F(r[2], 100) for r in rows]
        table = {(name, key): (cur, prev) for name, _, key, cur, prev in ref.reference()}
        self.assertEqual(table[("SMA", "value")], (sum(close[-14:]) / 14, sum(close[-15:-1]) / 14))
        self.assertEqual(table[("DONCHIAN", "upper")], (max(high[-20:]), max(high[-21:-1])))
        self.assertEqual(table[("DONCHIAN", "lower")], (min(low[-20:]), min(low[-21:-1])))
        self.assertEqual(table[("ROC", "value")][0], (close[-1] / close[-11] - 1) * 100)
        macd = {key: table[("MACD", key)][0] for key in ("line", "signal_line", "histogram")}
        self.assertEqual(macd["histogram"], macd["line"] - macd["signal_line"])
        upper, middle, lower = (table[("BOLLINGER", k)][0] for k in ("upper", "middle", "lower"))
        self.assertEqual(middle, sum(close[-20:]) / 20)
        self.assertEqual(upper - middle, middle - lower)
        self.assertEqual(table[("ICHIMOKU", "senkou_a")][0],
                         (table[("ICHIMOKU", "tenkan_sen")][0] + table[("ICHIMOKU", "kijun_sen")][0]) / 2)

    def test_reference_covers_24_indicators_and_40_values_within_bounds(self):
        rows = ref.reference()
        self.assertEqual(len(rows), 40)
        self.assertEqual(len({r[0] for r in rows}), 24)
        self.assertEqual(len({(r[0], r[2]) for r in rows}), 40)
        bounded = {("RSI", "value"): (0, 100), ("STOCHASTIC", "k"): (0, 100), ("STOCHASTIC", "d"): (0, 100),
                   ("MFI", "value"): (0, 100), ("WILLIAMS_R", "value"): (-100, 0),
                   ("AROON", "up"): (0, 100), ("AROON", "down"): (0, 100), ("CMF", "value"): (-1, 1),
                   ("ADX", "value"): (0, 100), ("ADX", "plus_di"): (0, 100), ("ADX", "minus_di"): (0, 100)}
        for name, _, key, current, previous in rows:
            self.assertIsInstance(current, F)
            if (name, key) in bounded:
                low, high = bounded[(name, key)]
                self.assertTrue(low <= current <= high and low <= previous <= high, (name, key))

    def test_all_40_reference_rows_require_both_bars_to_match(self):
        self.assertEqual(ref.CHECKS, {})
        table = ref.cpp_table()
        self.assertEqual(table.count('"match"},'), 40)
        self.assertNotIn('"current_only"},', table)
        self.assertNotIn('"diverges"},', table)

    def test_textbook_supertrend_lower_band_never_falls_while_long(self):
        # The defining property the engine violates: in an uptrend the line is the
        # final lower band, which may only rise. Recompute on the fixture.
        rows = ref.fixture()
        high = [F(r[1], 100) for r in rows]
        low = [F(r[2], 100) for r in rows]
        close = [F(r[3], 100) for r in rows]
        atr = ref._ema(ref._true_range(high, low, close), 10)
        final_low = None
        lows = []
        for i in range(9, len(close)):
            basic = (high[i] + low[i]) / 2 - 3 * atr[i]
            final_low = basic if final_low is None or close[i - 1] <= final_low else max(basic, final_low)
            lows.append(final_low)
        self.assertTrue(all(b >= a for a, b in zip(lows, lows[1:])))
        line = {(r[0], r[2]): r[3] for r in ref.reference()}[("SUPERTREND", "value")]
        self.assertEqual(line, lows[-1])

    def test_ema_seed_and_wilder_average_on_a_tiny_hand_case(self):
        # EMA(3) of 1,2,3,4,5: seed (1+2+3)/3 = 2, k = 1/2 -> 3, then 4.
        self.assertEqual(ref._ema([F(x) for x in (1, 2, 3, 4, 5)], 3), [None, None, F(2), F(3), F(4)])
        # SMA(2) skips a leading gap, as an average of an average must.
        self.assertEqual(ref._sma([None, F(2), F(4), F(8)], 2), [None, None, F(3), F(6)])
        # True range uses the previous close: bar 1 gaps up from 10 to a 14-15 range.
        self.assertEqual(ref._true_range([F(11), F(15)], [F(9), F(14)], [F(10), F(14)]), [F(2), F(5)])


if __name__ == "__main__":
    unittest.main()
