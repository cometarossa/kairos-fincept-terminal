"""Actual pinned yfinance dependency, mocked HTTP session only."""
import os,sys,json,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"fincept-qt"/"scripts"))
import fincept_raw_public_quote_v1 as m
from curl_cffi.requests import Session
class Raw(unittest.TestCase):
 def setUp(self):
    env=patch.dict(os.environ,{"FINCEPT_PUBLIC_YAHOO_QUOTE_ACK":m.ACK});env.start();self.addCleanup(env.stop)
 def record(self,symbol="SPY"):
    return {"quoteResponse":{"result":[{"symbol":symbol,"regularMarketTime":1795650000,"regularMarketPrice":100.123456}],"error":None}}
 def fixture(self,record=None,fail=None):
    calls=[]
    def request(session,method,url,**kw):
        calls.append((method,url,kw))
        i=len(calls)-1
        assert kw["allow_redirects"] is False and kw["timeout"]==8
        payload=[b"",b"synthetic-crumb",json.dumps(record if record is not None else self.record()).encode()][i]
        status=404 if i==0 else 200
        if i==fail:status=429
        return types.SimpleNamespace(url=url,status_code=status,content=payload,text=payload.decode())
    return calls,request
 def test_exact_three_requests(self):
    calls,f=self.fixture()
    with patch.object(Session,"request",f):
        q=m.fetch_raw_quote("SPY")
    self.assertEqual(q["symbol"],"SPY");self.assertEqual(q["regularMarketTime"],1795650000)
    self.assertEqual([c[1] for c in calls],list(m.URLS))
 def test_wrong_symbol_before_normalization(self):
    calls,f=self.fixture(self.record("AAPL"))
    with patch.object(Session,"request",f),self.assertRaises(m.QuoteDenied):m.fetch_raw_quote("SPY")
    self.assertEqual(len(calls),3)
 def test_no_retry_on_http_error(self):
    for i in (0,1,2):
        calls,f=self.fixture(fail=i)
        with patch.object(Session,"request",f),self.assertRaises(m.QuoteDenied):m.fetch_raw_quote("SPY")
        self.assertEqual(len(calls),i+1)
 def test_raw_duplicate(self):
    with self.assertRaises(m.QuoteDenied):m.raw_record(b'{"quoteResponse":{"result":[{"symbol":"AAPL","symbol":"SPY"}],"error":null}}',"SPY")
 def test_raw_ambiguous(self):
    r=self.record();r["quoteResponse"]["result"]*=2
    with self.assertRaises(m.QuoteDenied):m.raw_record(json.dumps(r).encode(),"SPY")
 def test_raw_timestamp_preserved(self):
    r=self.record();r["quoteResponse"]["result"][0]["regularMarketTime"]={"raw":1795650000,"fmt":"some text"}
    q=m.raw_record(json.dumps(r).encode(),"SPY")
    self.assertIsInstance(q["regularMarketTime"],dict)
 def test_no_ack(self):
    with patch.dict(os.environ,{"FINCEPT_PUBLIC_YAHOO_QUOTE_ACK":""}),patch.object(Session,"request") as f,self.assertRaises(m.QuoteDenied):m.fetch_raw_quote("SPY")
    f.assert_not_called()
 def test_unreviewed_version(self):
    with patch.object(m.importlib.metadata,"version",return_value="99"),patch.object(Session,"request") as f,self.assertRaises(m.QuoteDenied):m.fetch_raw_quote("SPY")
    f.assert_not_called()
if __name__=="__main__":unittest.main()
