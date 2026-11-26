"""Exact oracle against the installed VectorBT library (skipped when absent).

Fincept pins vectorbt==0.28.2 (with plotly<6). This is the only test here that
exercises the real library; the Fincept provider itself simulates in numpy.
"""
from __future__ import annotations

import importlib.util
import math
import unittest

from tools.fincept_audit import backtest_oracle_v1 as oracle

HAVE_VECTORBT = importlib.util.find_spec("vectorbt") is not None
SCENARIOS = [
    {"fast": 5, "slow": 20},
    {"fast": 5, "slow": 20, "commission": "0.001", "slippage": "0.0005"},
    {"fast": 3, "slow": 12, "commission": "0.0025"},
    {"fast": 5, "slow": 20, "commission": "0.001", "slippage": "0.0005", "execution": "same_close"},
]


@unittest.skipUnless(HAVE_VECTORBT, "vectorbt is not installed in this interpreter")
class VectorBTReferenceTests(unittest.TestCase):
    def test_vectorbt_equity_curve_matches_the_exact_oracle(self):
        from tools.fincept_audit.backtest_vectorbt_reference_v1 import vectorbt_equity
        candles = oracle.synthetic_candles(160)
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                expected = oracle.simulate(candles, **scenario)
                equity, closed, version = vectorbt_equity(candles, **scenario)
                self.assertTrue(version)
                self.assertEqual(closed, len(expected["trades"]))
                self.assertGreaterEqual(closed, 3)
                self.assertEqual(len(equity), expected["bars"])
                for i, (got, want) in enumerate(zip(equity, expected["equity"])):
                    self.assertTrue(math.isclose(got, float(want), rel_tol=1e-9, abs_tol=1e-6),
                                    (i, got, float(want)))

    def test_open_final_position_is_refused_not_compared(self):
        from tools.fincept_audit.backtest_vectorbt_reference_v1 import (
            ReferenceRefused, vectorbt_equity)
        with self.assertRaises(ReferenceRefused) as raised:
            vectorbt_equity(oracle.synthetic_candles(130), fast=5, slow=20)
        self.assertEqual(str(raised.exception), "OPEN_FINAL_POSITION_NOT_COMPARABLE")


if __name__ == "__main__":
    unittest.main()
