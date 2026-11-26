import json,os,socket,tempfile,threading,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts/yahoo_capture_service_v1"))
from capture_service import child_env,serve_request,Supervisor,SCOPE,history_diagnostic,HISTORY_EXIT_REASONS
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
import capture_public_yahoo_history_f2_v1 as producer
class Tests(unittest.TestCase):
 def test_separate_envs(self):
  h=child_env(10001,"history");q=child_env(10002,"quote")
  self.assertNotIn("FINCEPT_PUBLIC_QUOTE_CAPTURE_ACK",h)
  self.assertNotIn("FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK",q)
  self.assertEqual(h["HTTPS_PROXY"],"http://127.0.0.1:10001")
  self.assertEqual(q["HTTPS_PROXY"],"http://127.0.0.1:10002")
  self.assertFalse(any(k.startswith(("IG_","BROKER_")) for k in h|q))
 def test_long_environment_exact_and_quote_denied(self):
  h=child_env(10001,"history",period="6mo")
  self.assertEqual(h["FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK"],"DUAL_WINDOW_YAHOO_HISTORY_SNAPSHOT_V1")
  self.assertEqual(h["HTTPS_PROXY"],"http://127.0.0.1:10001")
  self.assertNotIn("FINCEPT_PUBLIC_QUOTE_CAPTURE_ACK",h)
  self.assertEqual(child_env(10001,"history")["FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK"],"MULTI_YAHOO_HISTORY_SNAPSHOT_V1")
  for lane,period in (("quote","6mo"),("history","2y"),("history","1y")):
   with self.assertRaises(ValueError):child_env(10001,lane,period=period)
 def test_fixed_history_reason_protocol(self):
  self.assertEqual(set(producer.REASON_EXIT_CODES),producer.REASONS)
  self.assertEqual(HISTORY_EXIT_REASONS,{v:k for k,v in producer.REASON_EXIT_CODES.items()})
  self.assertEqual(len(set(producer.REASON_EXIT_CODES.values())),len(producer.REASONS))
  self.assertTrue(all(20<=x<=100 for x in HISTORY_EXIT_REASONS))
  with patch.dict(os.environ,{},clear=True):
   self.assertEqual(producer.diagnostic_exit("RAW_INVALID_BAR_MISSING_CLOSE"),1)
  with patch.dict(os.environ,{"FINCEPT_HISTORY_REASON_EXIT_ACK":producer.DIAGNOSTIC_ACK},clear=True):
   for reason,code in producer.REASON_EXIT_CODES.items():
    self.assertEqual(producer.diagnostic_exit(reason),code)
    self.assertEqual(history_diagnostic("EURUSD=X","6mo",code),"HISTORY_CAPTURE_DIAGNOSTIC symbol=EURUSD=X period=6mo reason="+reason)
   self.assertEqual(producer.diagnostic_exit("arbitrary provider text"),producer.REASON_EXIT_CODES["INTERNAL_FAILURE"])
  self.assertIsNone(history_diagnostic("SPY","5d",0))
  self.assertIsNone(history_diagnostic("untrusted","6mo",20))
  self.assertIsNone(history_diagnostic("SPY","other",20))
  self.assertIsNone(history_diagnostic("SPY","5d",True))
  self.assertEqual(history_diagnostic("SPY","5d",1),"HISTORY_CAPTURE_DIAGNOSTIC symbol=SPY period=5d reason=CHILD_UNAVAILABLE_UNCLASSIFIED")
  self.assertEqual(child_env(10001,"history")["FINCEPT_HISTORY_REASON_EXIT_ACK"],producer.DIAGNOSTIC_ACK)
  self.assertNotIn("FINCEPT_HISTORY_REASON_EXIT_ACK",child_env(10002,"quote"))
 def test_adapter_error_envelope_is_not_invalid_count(self):
  import types
  from contextlib import redirect_stdout
  from io import StringIO
  for envelope in ({"error":"private test message","symbol":"EURUSD=X"}, {"error":""}):
   with self.subTest(envelope=envelope), tempfile.TemporaryDirectory() as td:
    root=Path(td);target=root/"long-EURUSD=X";target.mkdir(mode=0o700)
    prior=target/"snapshot.json";prior.write_bytes(b"prior");prior.chmod(0o600)
    calls=[]
    def fetch(*args,**kwargs):
     calls.append((args,kwargs));return envelope
    output=StringIO()
    argv=["capture","--inbox",td,"--symbol","EURUSD=X","--period","6mo"]
    with patch.dict(sys.modules,{"yfinance_data":types.SimpleNamespace(get_historical_period=fetch)}), patch.dict(os.environ,{"FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK":producer.DUAL_ACK,"FINCEPT_HISTORY_REASON_EXIT_ACK":producer.DIAGNOSTIC_ACK}), patch.object(sys,"argv",argv), redirect_stdout(output):
     self.assertEqual(producer.main(),20)
    self.assertEqual(output.getvalue().strip(),"FINCEPT_F2_HISTORY_CAPTURE_UNAVAILABLE reason=ADAPTER_UNAVAILABLE")
    self.assertEqual(prior.read_bytes(),b"prior")
    self.assertEqual(len(calls),1)
    self.assertEqual(calls[0][0],("EURUSD=X","6mo","1d"))
 def test_real_socket_request_claim(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   for n,v in [("last.json",'{"last_claim_unix":1400}'),("worker.lock","")]:
    p=root/n;p.write_text(v);p.chmod(0o600)
   calls=[]
   s=Supervisor(root,history_worker=lambda x:1,quote_worker=lambda x:calls.append(x) or 0,mono=lambda:0,wall=lambda:2000)
   raw=json.dumps(dict(scope=SCOPE,symbol="SPY",request_id="a"*32,issued_at_unix=2000)).encode()
   def send(payload,enabled):
    a,b=socket.socketpair()
    with a,b:
     t=threading.Thread(target=serve_request,args=(a,s),kwargs={"enabled":enabled});t.start()
     b.sendall(payload);b.shutdown(socket.SHUT_WR);b.settimeout(2)
     result=b.recv(128);t.join(2)
     return result
   self.assertEqual(send(raw,False),b"DISABLED\n")
   self.assertEqual(send(raw,True),b"CAPTURE_OK\n")
   self.assertEqual(send(raw,True),b"COOLDOWN\n")
   self.assertEqual(calls,["SPY"])
   self.assertEqual(send(b"x"*513,True),b"DENIED\n")
if __name__=="__main__":unittest.main()
