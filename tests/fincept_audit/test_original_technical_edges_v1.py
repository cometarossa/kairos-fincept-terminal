"""Research-only edge-case characterization of UNMODIFIED Fincept Python modules.

A PASS here means that the observations and a separate, opt-in laboratory
input guard behave as explicitly tested; it DOES NOT mean these edge cases
are safe inside Fincept or KAIROS execution.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def load(relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location("edge_" + path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GUARD = load("tools/fincept_audit/technical_preflight_lab_v1.py")
VOL = load("fincept-qt/scripts/technicals/volatility_indicators.py")
MOM = load("fincept-qt/scripts/technicals/momentum_indicators.py")


def trend(n=61):
    return pd.DataFrame(
        {
            "high": [101.0 + i * 0.17 for i in range(n)],
            "low": [99.0 + i * 0.17 for i in range(n)],
            "close": [100.0 + i * 0.17 for i in range(n)],
            "volume": [100.0 + i for i in range(n)],
        },
        index=pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC"),
    )


class OriginalTechnicalEdgeCharacterization(unittest.TestCase):
    def test_short_atr_raises_but_research_preflight_rejects(self):
        for n in (5, 13):
            with self.subTest(bars=n):
                df = trend(n)
                with self.assertRaises(IndexError):
                    VOL.calculate_atr(df, window=14)
                self.assertEqual(
                    GUARD.evaluate_window(df, asof_bar=n - 1, lookback=14)["reason"],
                    "INSUFFICIENT_HISTORY",
                )
                self.assertTrue(MOM.calculate_rsi(df).isna().all())

    def test_flat_prices_expose_extreme_rsi_and_undefined_stochastic(self):
        df = trend(50)
        for field in ("high", "low", "close"):
            df[field] = 100.0
        df["volume"] = 0.0
        self.assertEqual(VOL.calculate_atr(df).iloc[-1], 0.0)
        self.assertEqual(VOL.calculate_bollinger_bands(df)["bb_hband"].iloc[-1], 100.0)
        self.assertEqual(MOM.calculate_rsi(df).iloc[-1], 100.0)
        self.assertTrue(math.isnan(MOM.calculate_stochastic(df)["stoch_k"].iloc[-1]))
        self.assertEqual(
            GUARD.evaluate_window(df, asof_bar=49, lookback=20)["reason"],
            "DEGENERATE_RANGE",
        )
        # Even with nonzero intrabar range, flat close should NOT be treated
        # as an actionable overbought RSI=100 in research.
        df["high"], df["low"] = 101.0, 99.0
        self.assertEqual(MOM.calculate_rsi(df).iloc[-1], 100.0)
        self.assertEqual(
            GUARD.evaluate_window(df, asof_bar=49, lookback=20)["reason"],
            "NO_PRICE_MOVEMENT",
        )

    def test_zero_volume_undefined_pvo_requires_volume_preflight(self):
        df = trend(50)
        df["volume"] = 0.0
        self.assertTrue(math.isnan(MOM.calculate_pvo(df)["pvo"].iloc[-1]))
        self.assertEqual(
            GUARD.evaluate_window(df, asof_bar=49, lookback=26, volume_required=True)["reason"],
            "NO_VOLUME",
        )
        self.assertEqual(
            GUARD.evaluate_window(df, asof_bar=49, lookback=26, volume_required=False)["reason"],
            "OK",
        )

    def test_missing_close_can_leave_rsi_finite_while_bollinger_invalid(self):
        df = trend(61)
        df.iloc[30, df.columns.get_loc("close")] = float("nan")
        bb = VOL.calculate_bollinger_bands(df)["bb_hband"]
        rsi = MOM.calculate_rsi(df)
        self.assertTrue(math.isnan(bb.iloc[49]))
        self.assertTrue(math.isfinite(float(bb.iloc[50])))
        self.assertTrue(math.isfinite(float(rsi.iloc[31])))
        self.assertEqual(
            GUARD.evaluate_window(df, asof_bar=31, lookback=20)["reason"],
            "NON_FINITE_PRICE",
        )
        self.assertEqual(
            GUARD.evaluate_window(df, asof_bar=50, lookback=20)["reason"],
            "OK",
        )

    def test_research_preflight_is_asof_and_ignores_future_rows(self):
        df = trend(61)
        self.assertEqual(
            GUARD.evaluate_window(df, asof_bar=40, lookback=26, volume_required=True),
            {"admissible": True, "reason": "OK"},
        )
        changed = df.copy(deep=True)
        changed.loc[changed.index[41]:, ["high", "low", "close", "volume"]] = float("nan")
        self.assertEqual(
            GUARD.evaluate_window(changed, asof_bar=40, lookback=26, volume_required=True),
            {"admissible": True, "reason": "OK"},
        )
        self.assertEqual(
            GUARD.evaluate_window(changed, asof_bar=50, lookback=26)["reason"],
            "NON_FINITE_PRICE",
        )

    def test_research_preflight_rejects_invalid_candles_and_history_index(self):
        df = trend(51)
        bad_candle = df.copy()
        bad_candle.iloc[50, bad_candle.columns.get_loc("close")] = 999.0
        self.assertEqual(
            GUARD.evaluate_window(bad_candle, asof_bar=50, lookback=20)["reason"],
            "INVALID_CANDLE",
        )
        bad_index = df.copy()
        ix = list(bad_index.index)
        ix[50] = ix[49]
        bad_index.index = ix
        self.assertEqual(
            GUARD.evaluate_window(bad_index, asof_bar=50, lookback=20)["reason"],
            "NON_MONOTONIC_INDEX",
        )
        self.assertEqual(
            GUARD.evaluate_window(df.drop(columns=["close"]), asof_bar=50, lookback=20)["reason"],
            "MISSING_COLUMN",
        )

    def test_research_preflight_rejects_malformed_requests_fail_closed(self):
        df = trend(51)
        self.assertEqual(
            GUARD.evaluate_window(None, asof_bar=50, lookback=20)["reason"],
            "INVALID_INPUT",
        )
        self.assertEqual(
            GUARD.evaluate_window([], asof_bar=5, lookback=2)["reason"],
            "INVALID_INPUT",
        )
        for bad_asof, bad_lookback in ((True, 20), (50, True), (50, 1)):
            with self.subTest(asof=bad_asof, lookback=bad_lookback):
                self.assertEqual(
                    GUARD.evaluate_window(df, asof_bar=bad_asof, lookback=bad_lookback)["reason"],
                    "INVALID_REQUEST",
                )
        self.assertEqual(
            GUARD.evaluate_window(df, asof_bar=51, lookback=20)["reason"],
            "INSUFFICIENT_HISTORY",
        )

    def test_research_preflight_rejects_nonfinite_or_negative_volume(self):
        df = trend(51)
        nonfinite = df.copy()
        nonfinite.iloc[50, nonfinite.columns.get_loc("high")] = float("inf")
        self.assertEqual(
            GUARD.evaluate_window(nonfinite, asof_bar=50, lookback=20)["reason"],
            "NON_FINITE_PRICE",
        )
        neg_vol = df.copy()
        neg_vol.iloc[50, neg_vol.columns.get_loc("volume")] = -1.0
        self.assertEqual(
            GUARD.evaluate_window(neg_vol, asof_bar=50, lookback=20, volume_required=True)["reason"],
            "INVALID_VOLUME",
        )


if __name__ == "__main__":
    unittest.main()
