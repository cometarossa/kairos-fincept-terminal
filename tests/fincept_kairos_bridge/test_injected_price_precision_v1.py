"""Injected candles must preserve the admitted OHLC price precision."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]/"fincept-qt/scripts/Analytics/backtesting"
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"vectorbt"))
from vectorbt_provider import VectorBTProvider

class InjectedPrecisionTests(unittest.TestCase):
    def test_single_and_multi_preserve_input(self):
        def bars(base):
            return [{"t":1704067200+86400*i,"o":base+i+0.12345678,
                     "h":base+i+0.23456789,"l":base+i+0.01234567,
                     "c":base+i+0.16789123,"v":1000+i} for i in range(6)]
        a,b=bars(10),bars(20)
        for syms,multi in ((["AAPL"],False),(["AAPL","JPM"],True)):
            with self.subTest(multi=multi):
                p=VectorBTProvider()
                p._broker_candles={"AAPL":a,"JPM":b}
                actual=p._load_from_broker_candles(syms,multi)
                for sym,rows in zip(syms,(a,b)):
                    s=actual[sym] if multi else actual
                    self.assertEqual(s.tolist(),[r["c"] for r in rows])
                    frame=p._ohlc[p._canon_symbol(sym)]
                    self.assertEqual(s.tolist(),frame["Close"].tolist())
                    self.assertEqual(frame["Open"].tolist(),[r["o"] for r in rows])

if __name__=="__main__":
    unittest.main()
