import os,sys,copy,datetime,tempfile,time,unittest,io,contextlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
import yfinance as yf
import yfinance.utils as u
from yfinance.scrapers.history import PriceHistory
import yfinance_data as a
import fx_adjustment_observer_v1 as observer
import capture_public_yahoo_history_f2_v1 as prod
from capture_service import child_env,history_diagnostic,HISTORY_EXIT_REASONS

ACK="FINCEPT_FX_ADJUSTMENT_ORIGIN_V1"
class TestIntegration(unittest.TestCase):
 def setUp(self):
  self.assertEqual(yf.__version__,"0.2.66")
  r=np.random.default_rng(42);c=r.uniform(.8,1.3,100000);adj=r.uniform(.8,1.3,100000)
  i=int(np.flatnonzero(c*(adj/c)<adj)[0]);self.c=float(c[i]);self.adj=float(adj[i])
 def fetch(self,kind,diagnostic=True,valid=False,decoded=False,alter=None):
  c=self.c;day=int(time.time())//86400*86400
  ts=[day-86400*n for n in range(175,0,-1) if datetime.datetime.fromtimestamp(day-86400*n,datetime.timezone.utc).weekday()<5] if valid else [day-86400]
  n=len(ts)
  high=c if kind!="pre" else c-.001
  adj=self.adj if kind=="adjust" else c
  payload={'chart':{'error':None,'result':[{'meta':{'currency':'USD','instrumentType':'CURRENCY','exchangeTimezoneName':'UTC','timezone':'UTC','validRanges':['5d','6mo'],'priceHint':5,'dataGranularity':'1d','regularMarketTime':ts[-1],'currentTradingPeriod':{'regular':{'start':ts[-1],'end':ts[-1]+86400,'timezone':'UTC','gmtoffset':0}}},'timestamp':ts,'indicators':{'quote':[{'open':[c]*n,'high':[high]*n,'low':[c-.01]*n,'close':[c]*n,'volume':[0]*n}],'adjclose':[{'adjclose':[adj]*n}]}}]}}
  if decoded:payload['chart']['result'][0]['meta']['symbol']='EURUSD=X'
  if alter:alter(payload['chart']['result'][0])
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
  orig=u.auto_adjust;orig_parse=u.parse_quotes
  with tempfile.TemporaryDirectory() as td:
   target=Path(td)/"long-EURUSD=X";target.mkdir(mode=0o700)
   prior=target/"snapshot.json";previous=('{"captured_at_unix":'+str(day-86400)+'}').encode("ascii");prior.write_bytes(previous);prior.chmod(0o600)
   argv=["capture","--inbox",td,"--symbol","EURUSD=X","--period","6mo"]
   out=io.StringIO()
   with patch.dict(os.environ,env,clear=True),patch.object(a.yf,'Ticker',return_value=Ticker()) as t,patch.object(sys,"argv",argv),contextlib.redirect_stdout(out):
    code=prod.main()
   self.assertEqual((t.call_count,data.calls),(1,1))
   self.assertIs(u.auto_adjust,orig);self.assertIs(u.parse_quotes,orig_parse)
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
 def test_decoded_quote(self):
  code,out=self.fetch("pre",decoded=True)
  self.assertEqual(code,58,out)
  self.assertIn("RAW_INVALID_BAR_DECODED_QUOTE_OHLC_ORDER",out)
  self.assertIn("reason=RAW_INVALID_BAR_DECODED_QUOTE_OHLC_ORDER",history_diagnostic("EURUSD=X","6mo",code))
  self.assertIn("UNCLASSIFIED",history_diagnostic("SPY","6mo",code))
  self.assertIn("UNCLASSIFIED",history_diagnostic("EURUSD=X","5d",code))
 def test_decoded_fallbacks(self):
  for key,value in (("symbol","SPY"),("instrumentType","EQUITY"),("dataGranularity","5m")):
   with self.subTest(key=key):
    self.assertEqual(self.fetch("pre",decoded=True,alter=lambda d:d["meta"].update({key:value}))[0],56)
  self.assertEqual(self.fetch("adjust",decoded=True)[0],57)
  self.assertEqual(self.fetch("pre",decoded=True,diagnostic=False)[0],49)
  self.assertEqual(self.fetch("valid",decoded=True,valid=True)[0],0)
 def test_ambiguous_decoded_date(self):
  def duplicate(d):
   d["timestamp"].append(d["timestamp"][0]+3600)
   for col in d["indicators"]["quote"][0].values():col.append(col[0])
   d["indicators"]["adjclose"][0]["adjclose"].append(d["indicators"]["adjclose"][0]["adjclose"][0])
  self.assertEqual(self.fetch("pre",decoded=True,alter=duplicate)[0],56)
 def test_decoded_tuple_changed_by_parse(self):
  original=u.parse_quotes
  def corrupt(data,*args,**kwargs):
   frame=original(data,*args,**kwargs)
   frame["High"]=frame["Close"]-.001
   return frame
  with patch.object(u,"parse_quotes",corrupt):
   self.assertEqual(self.fetch("valid",decoded=True)[0],56)
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
 def test_optional_observer_errors_keep_original_outcome(self):
  @contextlib.contextmanager
  def broken_entry(_):
   raise RuntimeError("fixture")
   yield
  @contextlib.contextmanager
  def broken_exit(_):
   yield None
   raise RuntimeError("fixture")
  for scope in (broken_entry,broken_exit):
   with self.subTest(scope=scope.__name__),patch.object(observer,"observe_once",scope):
    self.assertEqual(self.fetch("adjust")[0],49)
    self.assertEqual(self.fetch("valid",valid=True)[0],0)
  with patch.object(observer.Observation,"classify",side_effect=RuntimeError("fixture")):
   self.assertEqual(self.fetch("adjust")[0],49)
 def test_forged_origin_cannot_bypass_opt_in(self):
  for diagnostic in (True,False):
   for label in ("PRE_ADJUSTMENT_OHLC_ORDER","ADJUSTMENT_STAGE_OHLC_ORDER","DECODED_QUOTE_OHLC_ORDER"):
    with self.subTest(diagnostic=diagnostic,label=label), tempfile.TemporaryDirectory() as td:
     target=Path(td)/"long-EURUSD=X";target.mkdir(mode=0o700)
     env=child_env(10001,"history",period="6mo")
     if not diagnostic:env.pop("FINCEPT_FX_ADJUSTMENT_DIAGNOSTIC_ACK")
     argv=["capture","--inbox",td,"--symbol","EURUSD=X","--period","6mo"]
     with patch.dict(os.environ,env,clear=True),patch.object(sys,"argv",argv),patch.object(a,"get_historical_period",return_value={"error":"RESEARCH_RAW_INVALID_BAR","raw_bar_failure_class":label,"adjustment_origin":label}) as fetch,contextlib.redirect_stdout(io.StringIO()):
      self.assertEqual(prod.main(),34)
     fetch.assert_called_once()
     self.assertFalse((target/"snapshot.json").exists())
 def test_protocol(self):
  self.assertEqual(set(prod.REASON_EXIT_CODES),prod.REASONS)
  self.assertEqual(HISTORY_EXIT_REASONS,{v:k for k,v in prod.REASON_EXIT_CODES.items()})
if __name__=="__main__":unittest.main()
