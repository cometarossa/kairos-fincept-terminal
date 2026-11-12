"""Original Fincept technicals: independent synthetic numeric and as-of-T contracts.

The two production modules are imported from unchanged Git blobs.  Only
deterministic synthetic OHLCV candles are used; no broker, network, account,
backtesting performance or forecasting claim is involved.
"""
from __future__ import annotations

import hashlib
import importlib.util
import math
from pathlib import Path
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
VOL_PATH = ROOT / "fincept-qt/scripts/technicals/volatility_indicators.py"
MOM_PATH = ROOT / "fincept-qt/scripts/technicals/momentum_indicators.py"
PINNED_BLOBS = {
    VOL_PATH: "d991f5448be1e16675f511993896b3f8edea1059",
    MOM_PATH: "6af1b869f7b7f1f94fca829d8ce704a78a81bef6",
}


def blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def load_source(path: Path):
    spec = importlib.util.spec_from_file_location("original_" + path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture():
    rows = []
    for i in range(83):
        close = 102 + 0.23 * i + 2.1 * math.sin(i * .33) + .7 * math.cos(i * .17)
        rows.append({
            "high": close + 1.05 + .1 * (i % 3),
            "low": close - 1.15 - .08 * (i % 4),
            "close": close,
            "volume": 2000 + 7 * i,
        })
    return pd.DataFrame(rows, index=pd.date_range("2026-01-01", periods=len(rows), freq="D", tz="UTC"))


def atr_wilder(df, window):
    highs, lows, closes = df.high.to_list(), df.low.to_list(), df.close.to_list()
    tr = []
    for i in range(len(df)):
        if i == 0:
            tr.append(highs[i] - lows[i])
        else:
            tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                          abs(lows[i] - closes[i - 1])))
    output = [0.] * len(df)
    output[window - 1] = sum(tr[:window]) / window
    for i in range(window, len(df)):
        output[i] = (output[i - 1] * (window - 1) + tr[i]) / window
    return output


def bollinger_band(closes, i, window=20, dev=2):
    vals = closes[i - window + 1:i + 1]
    avg = sum(vals) / window
    std = math.sqrt(sum((x - avg) ** 2 for x in vals) / window)
    return avg, avg + dev * std, avg - dev * std


def stoch_at(df, i, period=14):
    highs, lows = df.high.to_list(), df.low.to_list()
    upper, lower = max(highs[i-period+1:i+1]), min(lows[i-period+1:i+1])
    return 100 * (df.close.iloc[i] - lower) / (upper - lower)


def rsi_ewm_asof(closes, window=14):
    # Independent scalar recurrence equivalent to Wilder alpha=1/window:
    # the original ta library seeds the first diff with zero and uses adjust=False.
    alpha = 1. / window
    upavg = downavg = 0.
    out = [float("nan")] * len(closes)
    for i in range(len(closes)):
        delta = 0. if i == 0 else closes[i] - closes[i-1]
        upavg = (1-alpha) * upavg + alpha * max(delta, 0)
        downavg = (1-alpha) * downavg + alpha * max(-delta, 0)
        if i >= window - 1:
            out[i] = 100 if downavg == 0 else 100 - 100 / (1 + upavg / downavg)
    return out


class OriginalTechnicalIndicatorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vol = load_source(VOL_PATH)
        cls.mom = load_source(MOM_PATH)
        cls.df = fixture()

    def assert_value(self, actual, expected, places=8):
        self.assertTrue(math.isfinite(float(actual)), f"not finite: {actual}")
        self.assertAlmostEqual(float(actual), float(expected), places=places)

    def test_unchanged_source_blobs(self):
        for path, expected in PINNED_BLOBS.items():
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())
                self.assertEqual(blob_sha(path.read_bytes()), expected)

    def test_atr_independent_wilder_reference_and_warmup(self):
        values = self.vol.calculate_atr(self.df, window=14, fillna=False)
        ref = atr_wilder(self.df, window=14)
        self.assertEqual(len(values), len(self.df))
        self.assertEqual(values.iloc[:13].tolist(), [0.] * 13)
        for i in (13, 14, 25, 49, 82):
            with self.subTest(bar=i):
                self.assert_value(values.iloc[i], ref[i])

    def test_bollinger_independent_population_reference(self):
        bands = self.vol.calculate_bollinger_bands(self.df, window=20, window_dev=2)
        self.assertEqual(len(bands), 7)
        for name in ("bb_mavg", "bb_hband", "bb_lband"):
            self.assertTrue(math.isnan(bands[name].iloc[18]))
        closes = self.df.close.to_list()
        for i in (19, 35, 49, 82):
            avg, upper, lower = bollinger_band(closes, i)
            for name, expected in (("bb_mavg", avg), ("bb_hband", upper),
                                   ("bb_lband", lower)):
                with self.subTest(bar=i, band=name):
                    self.assert_value(bands[name].iloc[i], expected, places=7)

    def test_stochastic_independent_trailing_ranges(self):
        values = self.mom.calculate_stochastic(self.df, window=14, smooth_window=3)
        self.assertEqual(set(values), {"stoch_k", "stoch_d"})
        self.assertTrue(math.isnan(values["stoch_k"].iloc[12]))
        self.assertTrue(math.isnan(values["stoch_d"].iloc[14]))
        for i in (15, 35, 49, 82):
            with self.subTest(bar=i):
                self.assert_value(values["stoch_k"].iloc[i], stoch_at(self.df, i))
                self.assert_value(values["stoch_d"].iloc[i],
                                  sum(stoch_at(self.df, j) for j in range(i-2, i+1)) / 3)

    def test_rsi_independent_scalar_wilder_reference(self):
        values = self.mom.calculate_rsi(self.df, window=14)
        self.assertTrue(math.isnan(values.iloc[12]))
        ref = rsi_ewm_asof(self.df.close.to_list())
        for i in (13, 14, 35, 49, 82):
            with self.subTest(bar=i):
                self.assert_value(values.iloc[i], ref[i], places=7)

    def test_point_in_time_prefix_is_invariant_to_future_candles(self):
        # No output at as-of-T (bar 49) can depend on bars 50..82.
        old = self.df
        new = old.copy(deep=True)
        new.iloc[50:, new.columns.get_loc("close")] *= 1.47
        new.iloc[50:, new.columns.get_loc("high")] *= 1.49
        new.iloc[50:, new.columns.get_loc("low")] *= 1.35
        tests = (
            ("ATR", lambda d: self.vol.calculate_atr(d).iloc[49]),
            ("BB-upper", lambda d: self.vol.calculate_bollinger_bands(d)["bb_hband"].iloc[49]),
            ("RSI", lambda d: self.mom.calculate_rsi(d).iloc[49]),
            ("stochK", lambda d: self.mom.calculate_stochastic(d)["stoch_k"].iloc[49]),
        )
        for label, fn in tests:
            with self.subTest(indicator=label):
                self.assert_value(fn(old), fn(new), places=10)
                self.assert_value(fn(old), fn(old.iloc[:50]), places=10)

    def test_reference_detects_swapped_bollinger_bands(self):
        # Negative probe: intentionally wrong result must not satisfy oracle.
        result = self.vol.calculate_bollinger_bands(self.df)
        _, upper, _ = bollinger_band(self.df.close.to_list(), 49)
        corrupted = result["bb_lband"].iloc[49]
        self.assertGreater(abs(float(corrupted) - upper), 0.1)
        with self.assertRaises(AssertionError):
            self.assert_value(corrupted, upper)


if __name__ == "__main__":
    unittest.main()
