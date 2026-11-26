import json,os,tempfile,unittest,fcntl
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
import capture_public_yahoo_quote_f2_v1 as m
NOW=1795649670
def quote(symbol="SPY"):
    p=100.123456;prev=99.12;change=p-prev
    return dict(schema="YAHOO_PROVIDER_CLAIMED_QUOTE_V1",provider="Yahoo Finance via original yfinance",symbol=symbol,price=p,previous_close=prev,change=change,change_percent=100*(change/prev),high=101,low=98,volume=1000,provider_claimed_market_time_unix=NOW-10,local_received_at_unix=NOW-1,market_as_of_verified=False,freshness_verified=False,research_only=True,execution_authority=False,scientific_claim=False,broker_calls=0)
class Snapshot(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        (self.root/"SPY").mkdir(mode=0o700)
        self.addCleanup(self.tmp.cleanup)
        e=patch.dict(os.environ,{"FINCEPT_PUBLIC_QUOTE_CAPTURE_ACK":m.ACK,"FINCEPT_PUBLIC_YAHOO_QUOTE_ACK":m.ACK});e.start();self.addCleanup(e.stop)
    def read(self):return (self.root/"SPY"/"snapshot.json").read_bytes()
    def capture(self,q=None,now=NOW):
        return m.capture(self.root,"SPY",clock=lambda:now,adapter=lambda symbol,strict_research:q if q is not None else quote(symbol))
    def test_roundtrip(self):
        q=quote();s=m.build_snapshot(q,"SPY",NOW)
        self.assertEqual(m.decode_snapshot(m.encode(s),"SPY",NOW),q)
    def test_publish_once(self):
        with patch.object(m,"publish",wraps=m.publish) as p:
            self.capture();p.assert_called_once()
        self.assertEqual(m.decode_snapshot(self.read(),"SPY",NOW),quote())
        self.assertEqual((self.root/"SPY"/"snapshot.json").stat().st_mode&0o777,0o600)
    def test_failure_does_not_renew(self):
        self.capture();old=self.read()
        with self.assertRaises(ValueError):self.capture({"error":"unavailable"},NOW+10)
        self.assertEqual(self.read(),old)
        with self.assertRaises(ValueError):m.decode_snapshot(old,"SPY",NOW+61)
    def test_expiry_absolute(self):
        q=quote();q["provider_claimed_market_time_unix"]=NOW-899
        raw=m.encode(m.build_snapshot(q,"SPY",NOW))
        with self.assertRaises(ValueError):m.decode_snapshot(raw,"SPY",NOW+2)
    def test_hash_and_identity(self):
        s=m.build_snapshot(quote(),"SPY",NOW)
        with self.assertRaises(ValueError):m.decode_snapshot(m.encode(s),"EURUSD=X",NOW)
        s["quote_sha256"]="0"*64
        with self.assertRaises(ValueError):m.decode_snapshot(m.encode(s),"SPY",NOW)
    def test_bad_authority(self):
        for k,v in (("broker_calls",False),("market_as_of_verified",True),("execution_authority",True),("research_only",1),("volume",True),("change",0)):
            q=quote();q[k]=v
            with self.assertRaises(ValueError):m.build_snapshot(q,"SPY",NOW)
    def test_opt_in(self):
        with patch.dict(os.environ,{"FINCEPT_PUBLIC_QUOTE_CAPTURE_ACK":""}):
            with self.assertRaises(ValueError):m.capture(self.root,"SPY",adapter=lambda *a,**k:self.fail("called"))
    def test_duplicate_clock(self):
        self.capture();old=self.read()
        with self.assertRaises(ValueError):self.capture()
        self.assertEqual(self.read(),old)
    def test_lock(self):
        fd=os.open(self.root/"SPY"/".capture.lock",os.O_CREAT|os.O_RDWR,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(OSError):m.capture(self.root,"SPY",adapter=lambda *a,**k:self.fail("called"))
        finally:os.close(fd)
    def test_duplicate_json(self):
        raw=m.encode(m.build_snapshot(quote(),"SPY",NOW))
        with self.assertRaises(ValueError):m.decode_snapshot(raw[:-1]+b',"symbol":"SPY"}',"SPY",NOW)
if __name__=="__main__":unittest.main()
