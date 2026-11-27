import os,sys,copy,datetime,tempfile,time,unittest,io,contextlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
import yfinance as yf
import yfinance.utils as u
from yfinance.scrapers.history import PriceHistory
import yfinance_data as a
import capture_public_yahoo_history_f2_v1 as prod
from capture_service import child_env,history_diagnostic,HISTORY_EXIT_REASONS

ACK="FINCEPT_FX_ADJUSTMENT_ORIGIN_V1"
class TestIntegration(unittest.TestCase):
 def setUp(self):
  self.assertEqual(yf.__version__,"0.2.66")
  r=np.random.default_rng(42);c=r.uniform(.8,1.3,100000);adj=r.uniform(.8,1.3,100000)
  i=int(np.flatnonzero(c*(adj/c)<adj)[0]);self.c=float(c[i]);self.adj=float(adj[i])
 def fetch(self,kind,diagnostic=True,valid=False):
  c=self.c;day=int(time.time())//86400*86400
  ts=[day-86400*n for n in range(175,0,-1) if datetime.datetime.fromtimestamp(day-86400*n,datetime.timezone.utc).weekday()<5] if valid else [day-86400]
  n=len(ts)
  high=c if kind!="pre" else c-.001
  adj=self.adj if kind=="adjust" else c
  payload={'chart':{'error':None,'result':[{'meta':{'currency':'USD','instrumentType':'CURRENCY','exchangeTimezoneName':'UTC','timezone':'UTC','validRanges':['5d','6mo'],'priceHint':5,'dataGranularity':'1d','regularMarketTime':ts[-1],'currentTradingPeriod':{'regular':{'start':ts[-1],'end':ts[-1]+86400,'timezone':'UTC','gmtoffset':0}}},'timestamp':ts,'indicators':{'quote':[{'open':[c]*n,'high':[high]*n,'low':[c-.01]*n,'close':[c]*n,'volume':[0]*n}],'adjclose':[{'adjclose':[adj]*n}]}}]}}
  class Response:
   text='fixture'
   def json(self):return copy.deepcopy(payload)
  class Data:
   def __init__(self):self.calls=0
   def get(self,*x,**k):self.calls+=1;return Response()
   cache_get=get
  data=Data();p=PriceHistory(data,'EURUSD=X','UTC')
  class Ticker:
   def history(self,**kwargs):return p.history(**kwargs,raise_errors=True)
  env=child_env(10001,"history",period="6mo")
  if not diagnostic:env.pop("FINCEPT_FX_ADJUSTMENT_DIAGNOSTIC_ACK")
  orig=u.auto_adjust
  with tempfile.TemporaryDirectory() as td:
   target=Path(td)/"long-EURUSD=X";target.mkdir(mode=0o700)
   prior=target/"snapshot.json";previous=('{"captured_at_unix":'+str(day-86400)+'}').encode("ascii");prior.write_bytes(previous);prior.chmod(0o600)
   argv=["capture","--inbox",td,"--symbol","EURUSD=X","--period","6mo"]
   out=io.StringIO()
   with patch.dict(os.environ,env,clear=True),patch.object(a.yf,'Ticker',return_value=Ticker()) as t,patch.object(sys,"argv",argv),contextlib.redirect_stdout(out):
    code=prod.main()
   self.assertEqual((t.call_count,data.calls),(1,1))
   self.assertIs(u.auto_adjust,orig)
   if code: self.assertEqual(prior.read_bytes(),previous)
   else: self.assertNotEqual(prior.read_bytes(),previous)
   return code,out.getvalue()
 def test_adjustment(self):
  code,out=self.fetch("adjust");self.assertEqual(code,57)
  self.assertIn("RAW_INVALID_BAR_ADJUSTMENT_STAGE_OHLC_ORDER",out)
  self.assertEqual(history_diagnostic("EURUSD=X","6mo",code),"HISTORY_CAPTURE_DIAGNOSTIC symbol=EURUSD=X period=6mo reason=RAW_INVALID_BAR_ADJUSTMENT_STAGE_OHLC_ORDER")
 def test_preexisting(self):
  code,out=self.fetch("pre");self.assertEqual(code,56)
  self.assertIn("RAW_INVALID_BAR_PRE_ADJUSTMENT_OHLC_ORDER",out)
 def test_legacy_rejection(self):
  code,out=self.fetch("adjust",diagnostic=False);self.assertEqual(code,49)
  self.assertIn("reason=RAW_INVALID_BAR_OHLC_ORDER",out)
 def test_valid_publication(self):
  code,out=self.fetch("valid",valid=True);self.assertEqual(code,0,out)
  self.assertIn("FINCEPT_F2_HISTORY_CAPTURE_OK",out)
 def test_ack_and_scope(self):
  self.assertEqual(child_env(10001,"history",period="6mo")["FINCEPT_FX_ADJUSTMENT_DIAGNOSTIC_ACK"],ACK)
  for lane in ("history","quote","screener"):
   self.assertNotIn("FINCEPT_FX_ADJUSTMENT_DIAGNOSTIC_ACK",child_env(10001,lane))
  with patch.dict(os.environ,{},clear=True),patch.object(a.yf,"Ticker") as t:
   out=a.get_historical_period("EURUSD=X","6mo","1d",strict_research=True,diagnose_research_raw_bar=True,diagnose_adjustment_origin=True)
   self.assertEqual(out,{"error":"RESEARCH_ADJUSTMENT_DIAGNOSTICS_DENIED"});t.assert_not_called()
  with patch.dict(os.environ,{"FINCEPT_FX_ADJUSTMENT_DIAGNOSTIC_ACK":ACK},clear=True),patch.object(a.yf,"Ticker") as t:
   out=a.get_historical_period("SPY","6mo","1d",strict_research=True,diagnose_research_raw_bar=True,diagnose_adjustment_origin=True)
   self.assertEqual(out,{"error":"RESEARCH_ADJUSTMENT_DIAGNOSTICS_DENIED"});t.assert_not_called()
 def test_protocol(self):
  self.assertEqual(set(prod.REASON_EXIT_CODES),prod.REASONS)
  self.assertEqual(HISTORY_EXIT_REASONS,{v:k for k,v in prod.REASON_EXIT_CODES.items()})
if __name__=="__main__":unittest.main()
