import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for p in (ROOT/"scripts/yahoo_capture_service_v1", ROOT/"scripts", ROOT/"fincept-qt/scripts"):
    sys.path.insert(0,str(p))
import os,tempfile,pathlib,time,unittest,copy
from unittest.mock import patch
import screener_data
from capture_public_yahoo_screener_f2_v1 import capture_once,SCOPE
from screener_inbox_publish_candidate import decode
class Reply:
    status_code=200
    def __init__(self,v):self.v=v
    def json(self):return {"finance":{"result":[copy.deepcopy(self.v)],"error":None}}
class Session:
    def __init__(self,now,variant="ok"):self.now=now;self.variant=variant;self.calls=[]
    def get(self,**kw):
        self.calls.append("get")
        if self.variant=="failure":raise OSError("synthetic transport failure")
        rows=[{"symbol":"QA-A","currency":"USD","regularMarketPrice":10.0,"regularMarketTime":self.now-10,"exchangeDataDelayedBy":15},{"symbol":"QA-B","currency":"USD","regularMarketPrice":20.0,"regularMarketTime":self.now-10,"exchangeDataDelayedBy":15}]
        if self.variant=="mixed":rows[1]["regularMarketTime"]-=1
        return Reply({"quotes":rows,"total":2})
    def post(self,url,**kw):
        self.calls.append("post")
        return Reply({"records":[{"ticker":s,"sector":"Technology","percentchange":5.0} for s in ("QA-A","QA-B")]})
class Test(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name).resolve();self.target=self.root/"snapshot.json"
        self.now=int(time.time())
    def invoke(self,variant="ok",scope=SCOPE,clock=None):
        s=Session(self.now,variant)
        with patch.object(screener_data,"_session",return_value=s),patch.object(screener_data.time,"time",return_value=self.now):
            out=capture_once(scope=scope,inbox=self.root,clock=clock or (lambda:self.now))
        return out,s.calls
    def test_exact_capture_publish(self):
        self.assertEqual(self.invoke(),("PUBLISHED",["get","post"]))
        self.assertEqual(decode(self.target.read_bytes())[0],self.now)
    def test_disabled_no_calls(self):
        self.assertEqual(self.invoke(scope=None),("DISABLED",[]))
    def test_failure_no_retry(self):
        self.assertEqual(self.invoke("failure"),("CAPTURE_UNAVAILABLE",["get"]))
        self.assertFalse(self.target.exists())
    def test_mixed_preserves_distinct_times(self):
        self.assertEqual(self.invoke()[0],"PUBLISHED")
        self.now+=1
        self.assertEqual(self.invoke("mixed")[0],"PUBLISHED")
        import json,base64
        raw=json.loads(base64.b64decode(json.loads(self.target.read_bytes())["payload_base64"]))
        self.assertEqual([x["market_time"] for x in raw["rows"]],[self.now-10,self.now-11])
        self.assertIs(raw["market_as_of_verified"],False)
        self.assertNotIn("as_of",raw)
        self.assertIs(raw["execution_authority"],False)
    def test_clock_regression(self):
        stamps=iter((self.now,self.now-1))
        self.assertEqual(self.invoke(clock=lambda:next(stamps))[0],"CLOCK_DENIED")
        self.assertFalse(self.target.exists())
    def test_timeout_receipt_not_published(self):
        stamps=iter((self.now,self.now+46))
        self.assertEqual(self.invoke(clock=lambda:next(stamps))[0],"CLOCK_DENIED")
    def test_capture_before_start(self):
        self.assertEqual(self.invoke(clock=lambda:self.now+1)[0],"CAPTURE_DENIED")
    def test_broker_env_denied(self):
        with patch.dict(os.environ,{"BROKER_QA":"synthetic"}):
            self.assertEqual(self.invoke(),("ISOLATION_DENIED",[]))
    def test_bad_directory_no_calls(self):
        self.root.chmod(0o755)
        self.assertEqual(self.invoke(),("INBOX_DENIED",[]))
    def test_symlink_directory_no_calls(self):
        alias=self.root/"alias";alias.symlink_to(self.root,target_is_directory=True)
        s=Session(self.now)
        with patch.object(screener_data,"_session",return_value=s):
            self.assertEqual(capture_once(scope=SCOPE,inbox=alias),"INBOX_DENIED")
        self.assertEqual(s.calls,[])
    def test_monotonic_timeout(self):
        stamps=iter((0.,46.))
        s=Session(self.now)
        with patch.object(screener_data,"_session",return_value=s),patch.object(screener_data.time,"time",return_value=self.now):
            self.assertEqual(capture_once(scope=SCOPE,inbox=self.root,clock=lambda:self.now,mono=lambda:next(stamps)),"CLOCK_DENIED")
        self.assertFalse(self.target.exists())
if __name__=="__main__":unittest.main(verbosity=2)
