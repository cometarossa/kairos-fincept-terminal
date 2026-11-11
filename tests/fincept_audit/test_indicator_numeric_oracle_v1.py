"""Independent arithmetic spot-checks of ORIGINAL Fincept indicator outputs.

Tests compare deterministic synthetic OHLCV against stdlib math formulae, not
against ta/Pandas indicator implementations. This is NOT market validation,
GUI coverage, independent library attestation or an execution/trading signal.
No original Fincept application file is modified.
"""
from __future__ import annotations

import math
from pathlib import Path
import unittest

from tools.fincept_audit.technical_family_probe_v1 import (
    PINNED_MODULES,
    SOURCE_RELATIVE,
    _load_pinned_module,
    synthetic_ohlcv,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / SOURCE_RELATIVE
ROWS = (21, 57, 179)


def original_output(name, data):
    """Require the exact pinned original source, not a test replacement."""
    digest, _ = PINNED_MODULES[name]
    mod = _load_pinned_module(SOURCE / (name + "_indicators.py"), name, digest)
    return getattr(mod, "calculate_all_" + name + "_indicators")(data)


class IndependentNumericOracleTests(unittest.TestCase):
    def test_returns_independently_derived_from_closes(self):
        data = synthetic_ohlcv()
        got = original_output("others", data)
        close = data["close"].tolist()

        for i in (1, 21, 57, 179):
            with self.subTest(bar=i):
                self.assertAlmostEqual(
                    float(got["daily_return"].iloc[i]),
                    100.0 * (close[i] / close[i - 1] - 1.0),
                    places=9,
                )
                self.assertAlmostEqual(
                    float(got["daily_log_return"].iloc[i]),
                    100.0 * (math.log(close[i]) - math.log(close[i - 1])),
                    places=9,
                )
                self.assertAlmostEqual(
                    float(got["cumulative_return"].iloc[i]),
                    100.0 * (close[i] / close[0] - 1.0),
                    places=9,
                )

    def test_momentum_and_trend_against_rolling_arithmetic(self):
        data = synthetic_ohlcv()
        close = data["close"].tolist()
        momentum = original_output("momentum", data)
        trend = original_output("trend", data)

        self.assertTrue(math.isnan(float(momentum["roc"].iloc[11])))
        self.assertTrue(math.isnan(float(trend["sma_20"].iloc[18])))

        for i in ROWS:
            with self.subTest(bar=i):
                self.assertAlmostEqual(
                    float(momentum["roc"].iloc[i]),
                    100.0 * (close[i] / close[i - 12] - 1.0),
                    places=9,
                )
                self.assertAlmostEqual(
                    float(trend["sma_20"].iloc[i]),
                    sum(close[i - 19:i + 1]) / 20,
                    places=9,
                )

    def test_volatility_bands_independent_of_indicator_library(self):
        data = synthetic_ohlcv()
        close = data["close"].tolist()
        highs = data["high"].tolist()
        lows = data["low"].tolist()
        got = original_output("volatility", data)

        for i in ROWS:
            with self.subTest(bar=i):
                c = close[i - 19:i + 1]
                avg = sum(c) / 20.0
                population_std = math.sqrt(sum((v - avg) ** 2 for v in c) / 20)
                self.assertAlmostEqual(float(got["bb_mavg"].iloc[i]), avg, places=9)
                self.assertAlmostEqual(float(got["bb_hband"].iloc[i]), avg + 2 * population_std, places=9)
                self.assertAlmostEqual(float(got["bb_lband"].iloc[i]), avg - 2 * population_std, places=9)
                self.assertAlmostEqual(float(got["dc_hband"].iloc[i]), max(highs[i - 19:i + 1]), places=9)
                self.assertAlmostEqual(float(got["dc_lband"].iloc[i]), min(lows[i - 19:i + 1]), places=9)

    def test_volume_vwap_against_direct_weighted_sum(self):
        data = synthetic_ohlcv()
        got = original_output("volume", data)
        high = data["high"].tolist()
        low = data["low"].tolist()
        close = data["close"].tolist()
        volume = data["volume"].tolist()
        self.assertTrue(math.isnan(float(got["vwap"].iloc[12])))

        for i in ROWS:
            with self.subTest(bar=i):
                indexes = range(i - 13, i + 1)
                numerator = sum(((high[j] + low[j] + close[j]) / 3.0) * volume[j] for j in indexes)
                denominator = sum(volume[j] for j in indexes)
                self.assertGreater(denominator, 0)
                self.assertAlmostEqual(float(got["vwap"].iloc[i]), numerator / denominator, places=9)


if __name__ == "__main__":
    unittest.main()
