"""Hand-checked cases for the metric oracle. Standard library only."""
from __future__ import annotations

from fractions import Fraction as F
import math
import unittest

from tools.fincept_audit.backtest_metrics_oracle_v1 import MetricsRefused, metrics

# Four bars, four bars per year -> exactly one year.
#   equity   100, 110, 99, 121      returns  +1/10, -1/10, +2/9
#   peak     100, 110, 110, 121     drawdown 0, 0, 1/10, 0
#   trades   +10, -11, +22          (they need not add up to the equity change here)
EQUITY = [F(100), F(110), F(99), F(121)]
TRADES = [{"pnl": F(10)}, {"pnl": F(-11)}, {"pnl": F(22)}]


class HandCheckedMetricsTests(unittest.TestCase):
    def setUp(self):
        self.m = metrics(EQUITY, TRADES, F(100), 4)

    def test_exact_ratios(self):
        m = self.m
        self.assertEqual(m["total_return"], F(21, 100))
        self.assertEqual(m["max_drawdown"], F(1, 10))
        self.assertEqual((m["total_trades"], m["winning_trades"], m["losing_trades"]), (3, 2, 1))
        self.assertEqual(m["win_rate"], F(2, 3))
        self.assertEqual(m["profit_factor"], F(32, 11))
        self.assertEqual(m["average_win"], F(16, 100))       # (10 + 22) / 2 / 100
        self.assertEqual(m["average_loss"], F(-11, 100))
        self.assertEqual(m["largest_win"], F(22, 100))
        self.assertEqual(m["largest_loss"], F(-11, 100))
        self.assertEqual(m["expectancy"], F(7, 100))         # 21 / 3 / 100
        self.assertEqual((m["winning_bars"], m["losing_bars"]), (2, 1))
        self.assertEqual(m["average_bar_return"], F(2, 27))  # (1/10 - 1/10 + 2/9) / 3
        self.assertEqual((m["best_bar"], m["worst_bar"]), (F(2, 9), F(-1, 10)))

    def test_annualised_figures(self):
        m = self.m
        # One year exactly, so CAGR is the total return.
        self.assertAlmostEqual(float(m["annualized_return"]), 0.21, places=15)
        # Deviations from 2/27 are 7/270, -47/270, 40/270: squares sum to 3858/72900.
        # Sample variance = 1929/72900; times 4 bars/year, square root.
        volatility = math.sqrt(1929 / 72900 * 4)
        self.assertAlmostEqual(float(m["volatility"]), volatility, places=14)
        self.assertAlmostEqual(float(m["sharpe"]), 0.21 / volatility, places=13)
        # Only -1/10 is negative: mean(min(r,0)^2) = 0.01/3; times 4, square root.
        downside = math.sqrt(0.01 / 3 * 4)
        self.assertAlmostEqual(float(m["sortino"]), 0.21 / downside, places=13)
        self.assertAlmostEqual(float(m["calmar"]), 2.1, places=13)
        # Arithmetic-mean convention: mean * 4 / volatility = (8/27) / volatility.
        self.assertAlmostEqual(float(m["conventional_sharpe"]), (8 / 27) / volatility, places=13)

    def test_years_use_the_bar_count_not_the_interval_count(self):
        # 4 bars at 2 bars/year are 2 years: CAGR = sqrt(1.21) - 1 = 0.1 exactly.
        self.assertAlmostEqual(float(metrics(EQUITY, TRADES, F(100), 2)["annualized_return"]),
                               0.1, places=15)

    def test_risk_free_rate_lowers_sharpe_and_moves_the_sortino_target(self):
        m = metrics(EQUITY, TRADES, F(100), 4, F(4, 100))
        volatility = math.sqrt(1929 / 72900 * 4)
        self.assertAlmostEqual(float(m["sharpe"]), 0.17 / volatility, places=13)
        # Per-bar target 0.01: excess returns 0.09, -0.11, 2/9 - 0.01.
        downside = math.sqrt(0.11 ** 2 / 3 * 4)
        self.assertAlmostEqual(float(m["sortino"]), 0.17 / downside, places=13)

    def test_drawdown_peak_is_the_equity_itself_not_the_initial_capital(self):
        # Starts under water relative to 100 but never falls from its own peak.
        m = metrics([F(90), F(95), F(99)], [], F(100), 4)
        self.assertEqual(m["max_drawdown"], 0)
        self.assertEqual(m["total_return"], F(-1, 100))
        self.assertEqual(float(m["calmar"]), 0.0)

    def test_break_even_trade_counts_as_losing_and_all_winners_give_no_finite_factor(self):
        m = metrics(EQUITY, [{"pnl": F(5)}, {"pnl": F(0)}], F(100), 4)
        self.assertEqual((m["winning_trades"], m["losing_trades"]), (1, 1))
        self.assertIsNone(m["profit_factor"])          # winners, zero gross loss -> infinite
        self.assertEqual(m["average_loss"], 0)
        none = metrics(EQUITY, [], F(100), 4)
        self.assertEqual((none["win_rate"], none["profit_factor"], none["expectancy"]), (0, 0, 0))

    def test_flat_equity_has_zero_ratios_not_a_division_error(self):
        m = metrics([F(100)] * 5, [], F(100), 252)
        self.assertEqual((float(m["volatility"]), float(m["sharpe"]), float(m["sortino"])), (0, 0, 0))

    def test_invalid_inputs_are_refused(self):
        for args in ((EQUITY[:2], TRADES, F(100), 4), (EQUITY, TRADES, F(0), 4),
                     (EQUITY, TRADES, F(100), 0), (EQUITY, TRADES, F(100), True),
                     (EQUITY, TRADES, F(100), 252.0), ([100.0, 110.0, 99.0], TRADES, F(100), 4),
                     ([F(100), F(0), F(5)], TRADES, F(100), 4), (EQUITY, TRADES, F(100), 4, F(1))):
            with self.subTest(args=args[2:]):
                with self.assertRaises(MetricsRefused):
                    metrics(*args)


if __name__ == "__main__":
    unittest.main()
