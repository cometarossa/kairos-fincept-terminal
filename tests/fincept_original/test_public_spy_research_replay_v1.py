import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[2] / "scripts/replay_public_spy_research_v1.py"
spec = importlib.util.spec_from_file_location("archived_replay", P)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class ReplayTests(unittest.TestCase):
    def fixture(self):
        end=1795557808
        rows=[]
        for i in range(128):
            v=100.0 + (i%24 if (i//24)%2==0 else 24-i%24)
            rows.append(dict(timestamp=end-(128-i)*120000,open=v,high=v+1,low=v-1,close=v,volume=1000))
        raw=json.dumps(rows,separators=(",",":")).encode()
        return dict(schema="YAHOO_HISTORY_SNAPSHOT_V1",provider="Yahoo Finance via original yfinance",
                    symbol="SPY",period="6mo",interval="1d",adjustment="AUTO_ADJUST_TRUE_BACK_ADJUST_FALSE",
                    captured_at_unix=end,bars_base64=base64.b64encode(raw).decode(),bars_sha256=r.digest(raw))

    def test_decode(self):
        s=self.fixture()
        self.assertEqual(len(r.decode(json.dumps(s).encode(),s["bars_sha256"])[0]),128)
        for key,value in (("symbol","EURUSD=X"),("period","5d"),("captured_at_unix",True),("bars_sha256","0"*64)):
            bad=dict(s,**{key:value})
            with self.assertRaises(ValueError):
                r.decode(json.dumps(bad).encode(),s["bars_sha256"])

    def test_invalid_bar_with_valid_hash_denied(self):
        s=self.fixture()
        rows=json.loads(base64.b64decode(s["bars_base64"]))
        rows[0]["low"]=rows[0]["high"]+1
        payload=json.dumps(rows).encode()
        s.update(bars_base64=base64.b64encode(payload).decode(),bars_sha256=r.digest(payload))
        with self.assertRaisesRegex(ValueError,"OHLC"):
            r.decode(json.dumps(s).encode(),s["bars_sha256"])

    def test_original_engine_nontrivial_fixed_economic_case(self):
        import pandas as pd
        build,_=r.load_original()
        d=pd.DataFrame({"open":[100.,110.,120.,90.],"close":[100.,115.,115.,95.]})
        e=pd.Series([True,False,False,False])
        x=pd.Series([False,False,True,False])
        for bps in (0,10,25):
            v=r.evaluate(build,d,e,x,bps)
            c=bps/20000
            expected=10000/(110*(1+c)*(1+c))*90*(1-c)*(1-c)
            self.assertAlmostEqual(v["final_capital"],expected,places=7)
            self.assertEqual(v["legs"],2)
        self.assertLess(r.evaluate(build,d,e,x,25)["final_capital"],r.evaluate(build,d,e,x,0)["final_capital"])

    def test_receipt_and_reproducibility(self):
        s=self.fixture()
        raw=json.dumps(s).encode()
        a=r.replay(raw,s["bars_sha256"])
        b=r.replay(raw,s["bars_sha256"])
        self.assertEqual(a,b)
        self.assertEqual(len(a["results"]),9)
        self.assertEqual(sum(x["equity_checks"] for x in a["results"]),468)
        self.assertFalse(a["scientific_claim"])
        self.assertFalse(a["execution_authority"])
        sha=a.pop("receipt_sha256")
        self.assertEqual(sha,hashlib.sha256(json.dumps(a,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest())


if __name__ == "__main__":
    unittest.main()
