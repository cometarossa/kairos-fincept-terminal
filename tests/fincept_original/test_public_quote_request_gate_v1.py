import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts/yahoo_capture_service_v1"))
import unittest,tempfile,json,os,fcntl
from pathlib import Path
from public_quote_request_gate_v1 import dispatch,SCOPE
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.root.chmod(0o700)
  self.now=2000;self.calls=[]
  for n,v in [("last.json",'{"last_claim_unix":1400}'),("worker.lock","")]:
   p=self.root/n;p.write_text(v);p.chmod(0o600)
 def tearDown(self):self.tmp.cleanup()
 def raw(self,**kw):return json.dumps(dict(scope=SCOPE,symbol="EURUSD=X",request_id="a"*32,issued_at_unix=self.now,**{} )|kw).encode()
 def worker(self,symbol):self.calls.append(symbol);return 0
 def go(self,raw=None,worker=None):return dispatch(self.raw() if raw is None else raw,self.root,scope=SCOPE,worker=worker or self.worker,clock=lambda:self.now)
 def test_single_claim_and_restart(self):
  self.assertEqual(self.go(),"CAPTURE_OK");self.assertEqual(self.go(),"COOLDOWN");self.assertEqual(self.calls,["EURUSD=X"])
  self.now+=600;self.assertEqual(self.go(),"CAPTURE_OK")
 def test_failed_worker_consumes_slot(self):
  def fail(s):self.calls.append(s);raise RuntimeError("private")
  self.assertEqual(self.go(worker=fail),"CAPTURE_UNAVAILABLE");self.assertEqual(self.go(),"COOLDOWN");self.assertEqual(len(self.calls),1)
 def test_disabled(self):self.assertEqual(dispatch(self.raw(),self.root,worker=self.worker),"DISABLED");self.assertFalse(self.calls)
 def test_invalid(self):
  for raw in (self.raw(symbol="IG"),self.raw(issued_at_unix=self.now+1),self.raw(issued_at_unix=self.now-31),self.raw(request_id="../bad"),self.raw(extra=True),b'{"symbol":"SPY","symbol":"SPY"}',b'x'*513):
   self.assertEqual(self.go(raw),"DENIED")
  self.assertFalse(self.calls)
 def test_busy(self):
  with (self.root/"worker.lock").open("r+") as f:
   fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);self.assertEqual(self.go(),"BUSY")
  self.assertFalse(self.calls);self.assertEqual(self.go(),"CAPTURE_OK")
 def test_missing_state(self):
  (self.root/"last.json").unlink();self.assertEqual(self.go(),"DENIED");self.assertFalse(self.calls)
 def test_future_state(self):
  (self.root/"last.json").write_text('{"last_claim_unix":2001}');self.assertEqual(self.go(),"COOLDOWN");self.assertFalse(self.calls)
 def test_symlink(self):
  (self.root/"last.json").rename(self.root/"other");(self.root/"last.json").symlink_to("other");self.assertEqual(self.go(),"DENIED");self.assertFalse(self.calls)
 def test_unsafe_mode(self):
  (self.root/"last.json").chmod(0o644);self.assertEqual(self.go(),"DENIED");self.assertFalse(self.calls)
if __name__=="__main__":unittest.main(verbosity=2)
