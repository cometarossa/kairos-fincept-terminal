"""Verify the actual original strategy builders, exact synthetic reference.

No provider access and no backtest performance claims. Verify every prefix
against full-array signal output (causal signals, not causal execution).
"""
import sys
from pathlib import Path
import unittest
from fractions import Fraction
import numpy as np
import pandas as pd

from tools.fincept_audit import backtest_provider_probe_v1 as probe
from tools.fincept_audit import backtest_oracle_v1 as oracle
from tools.fincept_audit.non_sma_signal_oracle_v1 import reference

ROOT=Path(__file__).resolve().parents[2]/probe.BACKTESTING_RELATIVE
probe._verify_sources(ROOT)
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"vectorbt"))
from vectorbt import vbt_strategies as strategies

class NonSmaTests(unittest.TestCase):
    def actual(self, close, kind, period=20):
        s=pd.Series([float(x) for x in close],index=pd.date_range("2024-01-01",periods=len(close),freq="D"))
        params={"lookback":period,"threshold":0} if kind=="momentum" else {"period":period,"zThreshold":2}
        a,b=strategies.build_strategy_signals(None,kind,s,params)
        return a.tolist(),b.tolist()

    def fixtures(self):
        yield [Fraction(x["c"]) for x in oracle.synthetic_candles(bars=160)]
        yield [Fraction(x["c"]) for x in oracle.synthetic_candles(bars=160,shock_bar=90,shock_cents=1800)]
        yield [Fraction(100)]*45+[Fraction(x) for x in (97,90,88,92,99,104,108,109,102,94,96,101)]*5

    def test_exact_signal_parity(self):
        for j,c in enumerate(self.fixtures()):
            for kind in ("momentum","breakout","mean_reversion"):
                with self.subTest(fixture=j,kind=kind):
                    a=self.actual(c,kind)
                    self.assertEqual(a,reference(c,kind))
                    print("SIGNAL_PARITY",j,kind,len(c),sum(a[0]),sum(a[1]),flush=True)

    def test_prefix_causality(self):
        for c in self.fixtures():
            for kind in ("momentum","breakout","mean_reversion"):
                a,b=self.actual(c,kind)
                for n in (21,40,65,90,len(c)-1):
                    with self.subTest(kind=kind,n=n):
                        self.assertEqual(self.actual(c[:n],kind),(a[:n],b[:n]))

    def test_known_prior_channel_and_warmup(self):
        c=list(map(Fraction,[10,11,12,13,9,9,14]))
        a,b=reference(c,"breakout",3)
        self.assertEqual(a,[False,False,False,True,False,False,True])
        self.assertEqual(b,[False,False,False,False,True,False,False])
        self.assertEqual(self.actual(c,"breakout",3),(a,b))


    def test_original_provider_execution(self):
        from tools.fincept_audit import backtest_metrics_oracle_v1 as metrics
        from tools.fincept_audit.non_sma_signal_oracle_v1 import simulate_fixed
        candles=oracle.synthetic_candles(bars=160)
        for kind in ("momentum","breakout","mean_reversion"):
            with self.subTest(kind=kind):
                expected=simulate_fixed(candles,kind)
                self.assertGreater(len(expected["trades"]),0)
                req=probe.build_request(candles,{"fast":5,"slow":20,"commission":"0.001",
                                         "slippage":"0.0005","execution":"next_open"})
                req["strategy"]={"type":kind,"params":{"lookback":20,"threshold":0}
                                 if kind=="momentum" else {"period":20,"zThreshold":2}}
                run=probe.run_original_provider(ROOT,req)
                self.assertEqual(run["network_attempts"],0)
                labels=probe.compare(run["response"],expected)
                self.assertEqual(labels["provider_data_source"],probe.DATA_SOURCE_TAG)
                self.assertIs(labels["provider_using_synthetic_data"],False)
                probe.compare_metrics(run["response"],metrics.metrics(
                    expected["equity"],expected["trades"],Fraction(100000),365,Fraction(0)))
                print("FULL_BACKTEST_PARITY",kind,len(expected["trades"]),
                      "fees",float(expected["total_fees"]),flush=True)

if __name__=="__main__":
    unittest.main()
