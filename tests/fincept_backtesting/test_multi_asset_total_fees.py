"""Multi-asset VectorBT backtests must report the commissions they charged.

Runs the Fincept provider through its own CLI contract (`run_backtest --stdin`)
on synthetic candles passed via `brokerCandles`. Offline: no market data, no
network (the child gets no proxy variables and yfinance is never reached when
candles are injected). Needs numpy and pandas, like the provider itself.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROVIDER = ROOT / "fincept-qt/scripts/Analytics/backtesting/vectorbt/vectorbt_provider.py"
HAVE_DEPS = all(importlib.util.find_spec(name) for name in ("numpy", "pandas"))
DAY, START = 86400, 1704067200  # 2024-01-01


def candles(base, drift, wave, period, bars=160):
    rows = []
    for i in range(bars):
        close = round(base + drift * i + wave * math.sin(i / period), 2)
        open_ = round(close - 0.3 + 0.2 * math.sin(i / 5), 2)
        rows.append({"t": START + DAY * i, "o": open_, "h": round(max(open_, close) + 0.8, 2),
                     "l": round(min(open_, close) - 0.9, 2), "c": close, "v": 10000 + i})
    return rows


SERIES = {"SYNA": candles(100.0, 0.05, 6.0, 9.0), "SYNB": candles(50.0, 0.03, 4.0, 7.0)}


def run(symbols, **extra):
    request = {
        "strategy": {"type": "sma_crossover", "params": {"fastPeriod": 5, "slowPeriod": 20}},
        "symbols": symbols, "startDate": "2024-01-01", "endDate": "2030-01-01",
        "initialCapital": 100000, "commission": 0.001, "slippage": 0.0005,
        "brokerCandles": {s: SERIES[s] for s in symbols},
        "brokerDataSource": "synthetic_test_fixture",
    }
    request.update(extra)
    with tempfile.TemporaryDirectory() as scratch:
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": scratch,
               "PYTHONDONTWRITEBYTECODE": "1"}
        done = subprocess.run([sys.executable, "-B", str(PROVIDER), "run_backtest", "--stdin"],
                              input=json.dumps(request), capture_output=True, text=True,
                              env=env, cwd=scratch, timeout=120)
    assert done.returncode == 0, done.stderr[-400:]
    response = json.loads(done.stdout)
    assert response.get("success") is True, response.get("error")
    return response["data"]


@unittest.skipUnless(HAVE_DEPS, "the provider needs numpy and pandas")
class MultiAssetTotalFeesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.single = {s: run([s]) for s in SERIES}
        cls.multi = run(["SYNA", "SYNB"], weights=[0.7, 0.3])
        cls.equal = run(["SYNA", "SYNB"])

    def test_single_asset_total_fees_equal_the_trade_commissions(self):
        # The behaviour multi-asset must match; this already held.
        for symbol, data in self.single.items():
            with self.subTest(symbol=symbol):
                charged = sum(t["commission"] for t in data["trades"])
                self.assertGreater(charged, 0)
                self.assertAlmostEqual(data["statistics"]["totalFees"], charged, places=6)

    def test_multi_asset_total_fees_equal_the_trade_commissions(self):
        for name, data in (("weighted", self.multi), ("equal", self.equal)):
            with self.subTest(allocation=name):
                charged = sum(t["commission"] for t in data["trades"])
                self.assertGreater(len(data["trades"]), 3)
                self.assertGreater(charged, 100.0)
                self.assertAlmostEqual(data["statistics"]["totalFees"], charged, places=6)

    def test_multi_asset_fees_scale_with_the_capital_given_to_each_symbol(self):
        # Fees are proportional to capital: 70% / 30% of each single-symbol run.
        expected = (0.7 * self.single["SYNA"]["statistics"]["totalFees"] +
                    0.3 * self.single["SYNB"]["statistics"]["totalFees"])
        self.assertAlmostEqual(self.multi["statistics"]["totalFees"], expected, places=5)

    def test_fix_leaves_equity_trades_and_returns_of_the_combined_run_untouched(self):
        # Combined equity is the sum of the two per-symbol runs at their allocation.
        final = (0.7 * self.single["SYNA"]["statistics"]["finalCapital"] +
                 0.3 * self.single["SYNB"]["statistics"]["finalCapital"])
        self.assertAlmostEqual(self.multi["statistics"]["finalCapital"], final, places=5)
        self.assertAlmostEqual(self.multi["performance"]["totalReturn"], final / 100000 - 1, places=10)
        self.assertEqual(self.multi["performance"]["totalTrades"],
                         sum(len(d["trades"]) for d in self.single.values()))
        self.assertEqual([t["symbol"] for t in self.multi["trades"]],
                         ["SYNA"] * len(self.single["SYNA"]["trades"]) +
                         ["SYNB"] * len(self.single["SYNB"]["trades"]))

    def test_zero_commission_multi_asset_run_reports_zero_fees(self):
        data = run(["SYNA", "SYNB"], commission=0.0)
        self.assertEqual(data["statistics"]["totalFees"], 0)
        self.assertEqual(sum(t["commission"] for t in data["trades"]), 0)


if __name__ == "__main__":
    unittest.main()
