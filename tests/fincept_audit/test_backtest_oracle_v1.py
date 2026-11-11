"""Hand-checked cases for the exact backtest oracle. Standard library only.

The expected numbers below are worked out by hand in the comments; they do not
come from running the oracle or the Fincept provider.
"""
from __future__ import annotations

from fractions import Fraction as F
import unittest

from tools.fincept_audit.backtest_oracle_v1 import (
    DAY, EPOCH_2024, OracleRefused, simulate, sma_cross_signals, synthetic_candles)


def candles_from(closes, open_offset="0"):
    """Candles from decimal strings; open = close + open_offset."""
    rows = []
    for i, close in enumerate(closes):
        c = F(close)
        o = c + F(open_offset)
        rows.append({"t": EPOCH_2024 + DAY * i, "o": str(o), "c": str(c),
                     "h": str(max(o, c) + 1), "l": str(min(o, c) - 1), "v": 1})
    return rows


# 31 closes, SMA(2) against SMA(4).
#   bars 0-9 : 100.00, 99.99, ... 99.91   slowly falling -> SMA2 < SMA4
#   bars 10-12: 110, 111, 112             rising         -> SMA2 > SMA4
#   bars 13-30: 105, 104, ... 88          falling        -> SMA2 < SMA4
# bar  9: SMA2 = (99.92+99.91)/2 = 99.915   SMA4 = (99.94+99.93+99.92+99.91)/4 = 99.925
# bar 10: SMA2 = (99.91+110)/2 = 104.955    SMA4 = (99.93+99.92+99.91+110)/4 = 102.44  ENTRY
# bar 12: SMA2 = 111.5                      SMA4 = (99.91+110+111+112)/4 = 108.2275
# bar 13: SMA2 = (112+105)/2 = 108.5        SMA4 = (110+111+112+105)/4 = 109.5         EXIT
# Smallest gap anywhere is 0.01 (the falling prefix), far above the tie margin.
ROUND_TRIP = ([str(F(10000 - i, 100)) for i in range(10)] + ["110", "111", "112"] +
              [str(105 - i) for i in range(18)])
# Opens are one above the close, so a next-open fill differs from a same-close fill:
#   next_open : buy at open of bar 11 = 112, sell at open of bar 14 = 105
#   same_close: buy at close of bar 10 = 110, sell at close of bar 13 = 105


class SignalTests(unittest.TestCase):
    def test_edges_and_margin_on_hand_checked_series(self):
        entries, exits, margin = sma_cross_signals([F(c) for c in ROUND_TRIP], 2, 4)
        self.assertEqual(len(ROUND_TRIP), 31)
        self.assertEqual([i for i, x in enumerate(entries) if x], [10])
        self.assertEqual([i for i, x in enumerate(exits) if x], [13])
        self.assertEqual(margin, F(1, 100))

    def test_exact_tie_between_averages_is_refused(self):
        # A flat series makes both averages equal: floats could go either way.
        flat = [F(100)] * 31
        with self.assertRaises(OracleRefused) as raised:
            sma_cross_signals(flat, 2, 4)
        self.assertEqual(str(raised.exception), "AMBIGUOUS_CROSSOVER_MARGIN")


class SimulationTests(unittest.TestCase):
    """One round trip on ROUND_TRIP, every expected number worked out by hand."""

    def candles(self):
        return candles_from(ROUND_TRIP, open_offset="1")

    def test_next_open_round_trip_without_costs(self):
        result = simulate(self.candles(), fast=2, slow=4, initial_capital="1000")
        shares = F(1000, 112)                    # all cash at the open of bar 11
        self.assertEqual(len(result["trades"]), 1)
        trade = result["trades"][0]
        self.assertEqual((trade["entry_bar"], trade["exit_bar"]), (11, 14))
        self.assertEqual(trade["entry_price"], 112)
        self.assertEqual(trade["exit_price"], 105)
        self.assertEqual(trade["size"], shares)
        self.assertEqual(trade["pnl"], F(-7000, 112))          # (105-112) * 1000/112
        self.assertEqual(trade["exit_reason"], "signal")
        self.assertEqual(result["final_capital"], F(105000, 112))   # 937.5
        self.assertEqual(result["total_return"], F(-1, 16))
        self.assertEqual(result["total_fees"], 0)
        # Flat until the fill, then marked at each close while invested.
        self.assertEqual(result["equity"][10], 1000)
        self.assertEqual(result["equity"][11], shares * 111)
        self.assertEqual(result["equity"][12], shares * 112)
        self.assertEqual(result["equity"][13], shares * 105)
        self.assertEqual(result["equity"][14], F(105000, 112))
        self.assertEqual(result["equity"][-1], F(105000, 112))

    def test_costs_are_charged_on_both_legs_exactly(self):
        result = simulate(self.candles(), fast=2, slow=4, initial_capital="1000",
                          commission="0.01", slippage="0.02")
        buy = F(112) * F("1.02")                 # 114.24
        sell = F(105) * F("0.98")                # 102.9
        shares = F(1000) / (buy * F("1.01"))     # cash covers notional plus the 1% fee
        entry_fee = shares * buy * F("0.01")
        exit_fee = shares * sell * F("0.01")
        trade = result["trades"][0]
        self.assertEqual(trade["entry_price"], F("114.24"))
        self.assertEqual(trade["exit_price"], F("102.9"))
        self.assertEqual(trade["size"], shares)
        self.assertEqual(trade["fees"], entry_fee + exit_fee)
        self.assertEqual(trade["pnl"], (sell - buy) * shares - entry_fee - exit_fee)
        self.assertEqual(result["total_fees"], entry_fee + exit_fee)
        self.assertEqual(result["final_capital"], shares * sell * F("0.99"))
        self.assertEqual(result["total_return"], result["final_capital"] / 1000 - 1)

    def test_same_close_fills_on_the_signal_bar(self):
        result = simulate(self.candles(), fast=2, slow=4, initial_capital="1000",
                          execution="same_close")
        trade = result["trades"][0]
        self.assertEqual((trade["entry_bar"], trade["exit_bar"]), (10, 13))
        self.assertEqual(trade["entry_price"], 110)
        self.assertEqual(trade["exit_price"], 105)
        self.assertEqual(result["final_capital"], F(105000, 110))

    def test_percent_and_fixed_sizing(self):
        half = simulate(self.candles(), fast=2, slow=4, initial_capital="1000",
                        sizing_value="50")
        self.assertEqual(half["trades"][0]["size"], F(500, 112))
        self.assertEqual(half["final_capital"], 500 + F(500, 112) * 105)
        fixed = simulate(self.candles(), fast=2, slow=4, initial_capital="1000",
                         sizing_mode="fixed", sizing_value="250")
        self.assertEqual(fixed["trades"][0]["size"], F(250, 112))
        capped = simulate(self.candles(), fast=2, slow=4, initial_capital="1000",
                          sizing_mode="fixed", sizing_value="5000")
        self.assertEqual(capped["trades"][0]["size"], F(1000, 112))

    def test_open_position_is_closed_at_last_close_with_costs(self):
        # bars 0-4 fall by 0.01, bars 5-34 rise by 1: one entry, never an exit signal.
        # bar 4: SMA2 = 99.965 < SMA4 = 99.975.  bar 5 (101): SMA2 = 100.48 > SMA4 = 100.2275.
        closes = [str(F(10000 - i, 100)) for i in range(5)] + [str(100 + i) for i in range(1, 31)]
        result = simulate(candles_from(closes), fast=2, slow=4, initial_capital="1000",
                          commission="0.01")
        self.assertEqual(len(result["trades"]), 1)
        trade = result["trades"][0]
        shares = F(1000) / (102 * F("1.01"))     # filled at the open of bar 6 = 102
        self.assertEqual((trade["entry_bar"], trade["exit_bar"]), (6, 34))
        self.assertEqual(trade["size"], shares)
        self.assertEqual(trade["exit_reason"], "end_of_data")
        self.assertEqual(trade["exit_price"], 130)
        self.assertEqual(result["equity"][-1], result["final_capital"])
        self.assertEqual(result["final_capital"], shares * 130 * F("0.99"))


class StopTests(unittest.TestCase):
    """Stops on ROUND_TRIP. next_open buys at 112 (open of bar 11); closes then run
    111, 112, 105, 104, ... same_close buys at 110 (close of bar 10)."""

    def run_stops(self, **kwargs):
        result = simulate(candles_from(ROUND_TRIP, open_offset="1"), fast=2, slow=4,
                          initial_capital="1000", **kwargs)
        self.assertEqual(len(result["trades"]), 1)
        return result, result["trades"][0]

    def test_stop_loss_is_judged_on_the_close_and_fills_at_the_next_open(self):
        # 112 * 0.95 = 106.4. Closes 111 and 112 hold; close 105 on bar 13 breaks it.
        result, trade = self.run_stops(stop_loss="0.05")
        self.assertEqual((trade["exit_bar"], trade["exit_reason"]), (14, "stop_loss"))
        self.assertEqual(trade["exit_price"], 105)
        self.assertEqual(result["final_capital"], F(105000, 112))

    def test_stop_can_fire_on_the_fill_bar_itself(self):
        # 112 * 0.995 = 111.44 and the fill bar closes at 111: stopped at once,
        # sold at the open of bar 12 = 113, above the entry.
        result, trade = self.run_stops(stop_loss="0.005")
        self.assertEqual((trade["entry_bar"], trade["exit_bar"]), (11, 12))
        self.assertEqual(trade["exit_reason"], "stop_loss")
        self.assertEqual(trade["exit_price"], 113)
        self.assertEqual(trade["pnl"], F(1000, 112))

    def test_take_profit_same_close(self):
        # Bought at 110; 110 * 1.01 = 111.1. Close 111 holds, close 112 takes profit.
        result, trade = self.run_stops(take_profit="0.01", execution="same_close")
        self.assertEqual((trade["entry_bar"], trade["exit_bar"]), (10, 12))
        self.assertEqual(trade["exit_reason"], "take_profit")
        self.assertEqual(trade["exit_price"], 112)
        self.assertEqual(result["final_capital"], F(112000, 110))

    def test_trailing_stop_starts_at_the_entry_fill(self):
        # Peak starts at the 112 fill and never rises: 112 * 0.95 = 106.4, hit by 105.
        _, trade = self.run_stops(trailing_stop="0.05")
        self.assertEqual((trade["exit_bar"], trade["exit_reason"]), (14, "trailing_stop"))

    def test_trailing_stop_follows_the_highest_close(self):
        # same_close buys at 110; peak climbs to 112, so the 5% trail sits at 106.4
        # while a 5% stop-loss from 110 sits at 104.5. Close 105 trips only the trail.
        result, trade = self.run_stops(trailing_stop="0.05", stop_loss="0.05",
                                       execution="same_close")
        self.assertEqual((trade["exit_bar"], trade["exit_reason"]), (13, "trailing_stop"))
        self.assertEqual(trade["exit_price"], 105)

    def test_stop_loss_outranks_trailing_and_a_stop_outranks_the_signal(self):
        # Bar 13 is also the crossover exit bar; both stops hold there too.
        _, trade = self.run_stops(stop_loss="0.05", trailing_stop="0.05")
        self.assertEqual(trade["exit_reason"], "stop_loss")
        _, plain = self.run_stops()
        self.assertEqual((plain["exit_bar"], plain["exit_reason"]), (14, "signal"))

    def test_stop_uses_the_fill_price_including_slippage(self):
        # Entry 112 * 1.02 = 114.24. A 2.9% stop sits at 110.927, below the 111
        # close, so it holds until bar 13; a 2.8% stop sits at 111.041 and the 111
        # close of the fill bar trips it. Against the raw 112 neither would fire.
        _, held = self.run_stops(stop_loss="0.029", slippage="0.02")
        self.assertEqual(held["exit_bar"], 14)
        _, hit = self.run_stops(stop_loss="0.028", slippage="0.02")
        self.assertEqual((hit["exit_bar"], hit["exit_reason"]), (12, "stop_loss"))

    def test_invalid_stops_are_refused(self):
        for name in ("stop_loss", "take_profit", "trailing_stop"):
            for value in ("0", "1", "-0.1", 0.05, True):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(OracleRefused):
                        self.run_stops(**{name: value})


class RefusalTests(unittest.TestCase):
    def test_floats_and_malformed_inputs_are_refused(self):
        good = synthetic_candles(60)
        cases = [
            (dict(candles=[dict(good[0], c=101.5)] + good[1:]), "NON_DECIMAL_INPUT:c"),
            (dict(candles=good[:10]), "TOO_FEW_BARS"),
            (dict(candles=good[:1] + good), "NON_INCREASING_TIMESTAMPS"),
            (dict(candles=[dict(good[0], h="1")] + good[1:]), "INCONSISTENT_OHLC"),
            (dict(candles=good, fast=20, slow=5), "INVALID_SMA_PERIODS"),
            (dict(candles=good, slow=60), "SLOW_PERIOD_EXCEEDS_HISTORY"),
            (dict(candles=good, commission="0.5"), "INVALID_CAPITAL_OR_COSTS"),
            (dict(candles=good, initial_capital="0"), "INVALID_CAPITAL_OR_COSTS"),
            (dict(candles=good, execution="next_close"), "UNSUPPORTED_EXECUTION"),
            (dict(candles=good, sizing_mode="kelly"), "UNSUPPORTED_SIZING_MODE"),
            (dict(candles=good, sizing_value="0"), "INVALID_PERCENT_SIZING"),
            (dict(candles=good, sizing_mode="fixed", sizing_value="-1"), "INVALID_FIXED_SIZING"),
        ]
        for kwargs, reason in cases:
            with self.subTest(reason=reason):
                params = {"fast": 5, "slow": 20}
                params.update(kwargs)
                candles = params.pop("candles")
                with self.assertRaises(OracleRefused) as raised:
                    simulate(candles, **params)
                self.assertEqual(str(raised.exception), reason)

    def test_synthetic_fixture_is_deterministic_and_bounded(self):
        self.assertEqual(synthetic_candles(160), synthetic_candles(160))
        self.assertEqual(len(synthetic_candles(130)), 130)
        for count in (29, 2001):
            with self.assertRaises(OracleRefused):
                synthetic_candles(count)

    def test_result_is_labelled_synthetic(self):
        result = simulate(synthetic_candles(160), fast=5, slow=20)
        self.assertEqual(result["source_kind"], "SYNTHETIC_FIXTURE_NOT_MARKET_DATA")
        self.assertEqual(result["bars"], 160)
        self.assertTrue(all(isinstance(x, F) for x in result["equity"]))


if __name__ == "__main__":
    unittest.main()
