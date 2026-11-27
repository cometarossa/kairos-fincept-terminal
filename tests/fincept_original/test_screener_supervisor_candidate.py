import os,sys,pathlib,tempfile,unittest,json,fcntl
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/"scripts/yahoo_capture_service_v1"))
from capture_supervisor_candidate import Supervisor,SCREENER_SCOPE,SCOPE
from public_quote_request_gate_v1 import load_state
class Test(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name)
        for n,b in (("worker.lock",b""),("last.json",b'{"last_claim_unix":1000}')):
            p=self.root/n;p.write_bytes(b);p.chmod(0o600)
        self.now=2000;self.mono=100;self.calls=[];self.code=0
        self.s=Supervisor(self.root,history_worker=lambda x:self.record("history",x),quote_worker=lambda x:self.record("quote",x),screener_worker=lambda x:self.record("screen",x),mono=lambda:self.mono,wall=lambda:self.now)
    def record(self,lane,x):
        self.calls.append((lane,x));return self.code
    def raw(self,scope=SCREENER_SCOPE,**extra):
        r={"scope":scope,"request_id":"a"*32,"issued_at_unix":self.now}
        r.update({"screen_id":"day_gainers"} if scope==SCREENER_SCOPE else {"symbol":"SPY"});r.update(extra);return json.dumps(r).encode()
    def screen(self,raw=None):
        return self.s.screener(self.raw() if raw is None else raw,scope=SCREENER_SCOPE)
    def test_disabled(self):
        self.assertEqual(self.s.screener(self.raw()),"DISABLED");self.assertEqual(self.calls,[])
    def test_quote_then_screen(self):
        self.assertEqual(self.s.quote(self.raw(SCOPE),scope=SCOPE),"CAPTURE_OK")
        self.assertEqual(self.screen(),"COOLDOWN")
        self.assertEqual(self.calls,[("quote","SPY")])
    def test_screen_then_quote(self):
        self.assertEqual(self.screen(),"CAPTURE_OK")
        self.assertEqual(self.s.quote(self.raw(SCOPE),scope=SCOPE),"COOLDOWN")
        self.assertEqual(self.calls,[("screen","day_gainers")]);self.assertEqual(load_state(self.root),self.now)
    def test_no_retry_failure(self):
        self.code=1;self.assertEqual(self.screen(),"CAPTURE_UNAVAILABLE")
        self.assertEqual(self.screen(),"COOLDOWN");self.assertEqual(len(self.calls),1)
    def test_history_priority(self):
        self.mono=self.s.next_history-55
        self.assertEqual(self.screen(),"HISTORY_PRIORITY");self.assertEqual(load_state(self.root),1000)
        self.mono=self.s.next_history
        self.assertEqual(self.s.history_tick(),"HISTORY_OK");self.assertEqual(self.calls,[("history","SPY")])
    def test_common_lock(self):
        with (self.root/"worker.lock").open("rb") as f:
            fcntl.flock(f,fcntl.LOCK_EX);self.assertEqual(self.screen(),"BUSY")
        self.assertEqual(self.calls,[]);self.assertEqual(load_state(self.root),1000)
    def test_request_denial(self):
        for r in (self.raw(screen_id="other"),self.raw(force=True),self.raw(issued_at_unix=self.now-31),self.raw(issued_at_unix=True),b'{}',self.raw(SCOPE)):
            self.assertEqual(self.screen(r),"DENIED")
        self.assertEqual(self.calls,[]);self.assertEqual(load_state(self.root),1000)
    def test_restart_preserves_claim(self):
        self.assertEqual(self.screen(),"CAPTURE_OK")
        other=Supervisor(self.root,history_worker=lambda x:0,quote_worker=lambda x:0,screener_worker=lambda x:self.record("screen",x),mono=lambda:self.mono,wall=lambda:self.now)
        self.assertEqual(other.screener(self.raw(),scope=SCREENER_SCOPE),"COOLDOWN")
    def test_wall_regression(self):
        self.now=999;self.assertEqual(self.screen(),"COOLDOWN");self.assertEqual(self.calls,[])
    def test_missing_claim_fail_closed(self):
        (self.root/"last.json").unlink();self.assertEqual(self.screen(),"DENIED");self.assertEqual(self.calls,[])
if __name__=="__main__":unittest.main()
