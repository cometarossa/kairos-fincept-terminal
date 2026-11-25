import importlib.util,os,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[2]/"fincept-qt"/"scripts"
class StrictQuote(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    stub=types.ModuleType("yfinance")
    stub.Ticker=lambda *_: (_ for _ in ()).throw(AssertionError("unexpected provider"))
    cls.prev=sys.modules.get("yfinance");sys.modules["yfinance"]=stub
    spec=importlib.util.spec_from_file_location("quote_qa",SCRIPTS/"yfinance_data.py")
    cls.m=importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(SCRIPTS))
    try:spec.loader.exec_module(cls.m)
    finally:sys.path.remove(str(SCRIPTS))
 @classmethod
 def tearDownClass(cls):
    if cls.prev is None:del sys.modules["yfinance"]
    else:sys.modules["yfinance"]=cls.prev
 def setUp(self):
    self.now=int(self.m.datetime.now().timestamp())
    self.info=dict(symbol="SPY",regularMarketPrice=100.123456,regularMarketPreviousClose=99.12,regularMarketDayHigh=101,regularMarketDayLow=98,regularMarketVolume=1000,regularMarketTime=self.now-10)
    env=patch.dict(os.environ,{"FINCEPT_PUBLIC_YAHOO_QUOTE_ACK":"PUBLIC_YAHOO_QUOTE_RESEARCH_V1"})
    env.start();self.addCleanup(env.stop)
 def call(self,**kw):
    with patch.object(self.m.yf,"Ticker",return_value=types.SimpleNamespace(info={**self.info,**kw})) as t:
        r=self.m.get_quote("SPY",strict_research=True)
    t.assert_called_once_with("SPY");return r
 def test_valid(self):
    r=self.call();self.assertEqual(r["price"],100.123456);self.assertEqual(r["provider_claimed_market_time_unix"],self.now-10)
    self.assertGreaterEqual(r["local_received_at_unix"],self.now)
    for k in ("market_as_of_verified","freshness_verified","execution_authority","scientific_claim"):self.assertIs(r[k],False)
 def test_bad_time(self):
    for t in (self.now-901,self.now+60,None,True):self.assertIn("error",self.call(regularMarketTime=t))
 def test_identity(self):self.assertIn("error",self.call(symbol="QQQ"))
 def test_missing_previous(self):self.assertIn("error",self.call(regularMarketPreviousClose=None))
 def test_invalid_values(self):
    for k,v in (("regularMarketPrice",float("nan")),("regularMarketDayLow",101),("regularMarketVolume",None),("regularMarketVolume",1.5),("regularMarketVolume",True),("regularMarketPrice",0)):
        self.assertIn("error",self.call(**{k:v}))
 def test_no_opt_in(self):
    with patch.dict(os.environ,{"FINCEPT_PUBLIC_YAHOO_QUOTE_ACK":""}),patch.object(self.m.yf,"Ticker") as t:
        self.assertIn("error",self.m.get_quote("SPY",strict_research=True));t.assert_not_called()
 def test_symbol_denied(self):
    with patch.object(self.m.yf,"Ticker") as t:
        self.assertIn("error",self.m.get_quote("QQQ",strict_research=True));t.assert_not_called()
 def test_no_fallback(self):
    with patch.object(self.m.yf,"Ticker",side_effect=RuntimeError("private provider text")) as t:
        self.assertEqual(self.m.get_quote("SPY",strict_research=True),{"error":"RESEARCH_QUOTE_UNAVAILABLE"});t.assert_called_once()
 def test_fx_zero_volume(self):
    with patch.object(self.m.yf,"Ticker",return_value=types.SimpleNamespace(info={**self.info,"symbol":"EURUSD=X","regularMarketVolume":0})):
        self.assertEqual(self.m.get_quote("EURUSD=X",strict_research=True)["volume"],0)
 def test_legacy_unchanged(self):
    import pandas as pd
    frame=pd.DataFrame({"Close":[100.0],"Open":[99.0],"High":[101.0],"Low":[98.0],"Volume":[1000]})
    with patch.object(self.m.yf,"Ticker",return_value=types.SimpleNamespace(info={"previousClose":99},history=lambda **_:frame)):
        r=self.m.get_quote("SPY")
    self.assertEqual(r["price"],100.0);self.assertNotIn("provider_claimed_market_time_unix",r)
if __name__=="__main__":unittest.main()
