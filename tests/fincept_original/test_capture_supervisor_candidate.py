import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts/yahoo_capture_service_v1"))
import unittest,tempfile,json,fcntl,threading,time,sys,os
from pathlib import Path
from capture_supervisor_candidate import Supervisor,run_child,SCOPE
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  for n,v in [("last.json",'{"last_claim_unix":1400}'),("worker.lock","")]:
   p=self.root/n;p.write_text(v);p.chmod(0o600)
  self.m=0;self.w=2000;self.calls=[]
  self.s=Supervisor(self.root,history_worker=lambda x:self.calls.append(("history",x)) or 0,quote_worker=lambda x:self.calls.append(("quote",x)) or 0,mono=lambda:self.m,wall=lambda:self.w)
 def tearDown(self):self.tmp.cleanup()
 def raw(self):return json.dumps(dict(scope=SCOPE,symbol="EURUSD=X",request_id="a"*32,issued_at_unix=self.w)).encode()
 def test_disabled_and_no_early_history(self):
  self.assertEqual(self.s.quote(self.raw()),"DISABLED");self.assertEqual(self.s.history_tick(),"NOT_DUE");self.assertFalse(self.calls)
 def test_quote_and_history_serial(self):
  self.assertEqual(self.s.quote(self.raw(),scope=SCOPE),"CAPTURE_OK")
  self.assertEqual(self.s.quote(self.raw(),scope=SCOPE),"COOLDOWN")
  self.m=300;self.assertEqual(self.s.history_tick(),"HISTORY_OK")
  self.m=600;self.assertEqual(self.s.history_tick(),"HISTORY_OK")
  self.assertEqual(self.calls,[("quote","EURUSD=X"),("history","SPY"),("history","EURUSD=X")])
 def test_near_due(self):
  self.m=245
  self.assertEqual(self.s.quote(self.raw(),scope=SCOPE),"HISTORY_PRIORITY")
  self.m=300;self.assertEqual(self.s.quote(self.raw(),scope=SCOPE),"HISTORY_PRIORITY")
  self.assertEqual(self.s.history_tick(),"HISTORY_OK")
  self.assertEqual(self.calls,[("history","SPY")])
 def test_busy_skips_no_catchup(self):
  self.m=300
  with (self.root/"worker.lock").open("r+") as f:
   fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   self.assertEqual(self.s.history_tick(),"HISTORY_BUSY_SKIPPED")
  self.assertEqual(self.s.history_tick(),"NOT_DUE");self.assertFalse(self.calls)
  self.m=1800;self.assertEqual(self.s.history_tick(),"HISTORY_OK")
  self.assertEqual(self.s.history_tick(),"NOT_DUE");self.assertEqual(len(self.calls),1)
 def test_actual_history_blocks_quote(self):
  self.m=300
  entered=threading.Event();release=threading.Event()
  def h(x):entered.set();release.wait(2);return 0
  self.s.history_worker=h
  t=threading.Thread(target=self.s.history_tick);t.start()
  try:
   self.assertTrue(entered.wait(1));self.assertEqual(self.s.quote(self.raw(),scope=SCOPE),"BUSY")
  finally:release.set();t.join(2)
  self.assertFalse(self.calls)
 def test_actual_quote_blocks_history(self):
  entered=threading.Event();release=threading.Event()
  def q(x):entered.set();release.wait(2);return 0
  self.s.quote_worker=q
  t=threading.Thread(target=lambda:self.s.quote(self.raw(),scope=SCOPE));t.start()
  try:
   self.assertTrue(entered.wait(1));self.m=300;self.assertEqual(self.s.history_tick(),"HISTORY_BUSY_SKIPPED")
  finally:release.set();t.join(2)
  self.assertFalse(self.calls)
 def test_long_slots_replace_not_add_and_keep_symbol_rotation(self):
  self.s.long_history_worker=lambda x:self.calls.append(("long",x)) or 0
  for i in range(288):
   self.m=(i+1)*300
   self.assertEqual(self.s.history_tick(),"LONG_HISTORY_OK" if i%144 in (2,7) else "HISTORY_OK")
   self.assertEqual(self.s.history_tick(),"NOT_DUE")
  self.assertEqual(len(self.calls),288)
  self.assertEqual([(i,x) for i,x in enumerate(self.calls) if x[0]=="long"],[(2,("long","SPY")),(7,("long","EURUSD=X")),(146,("long","SPY")),(151,("long","EURUSD=X"))])
  self.assertTrue(all(x[1]==("SPY","EURUSD=X")[i%2] for i,x in enumerate(self.calls)))
 def test_long_failure_and_busy_never_retry(self):
  self.s.long_history_worker=lambda x:self.calls.append(("long",x)) or 1
  for self.m in (300,600):self.assertEqual(self.s.history_tick(),"HISTORY_OK")
  self.m=900;self.assertEqual(self.s.history_tick(),"LONG_HISTORY_UNAVAILABLE")
  self.assertEqual(self.s.history_tick(),"NOT_DUE")
  self.m=1200;self.assertEqual(self.s.history_tick(),"HISTORY_OK")
  self.assertEqual(self.calls,[("history","SPY"),("history","EURUSD=X"),("long","SPY"),("history","EURUSD=X")])
  self.s.index=7;self.m=1500
  with (self.root/"worker.lock").open("r+") as f:
   fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   self.assertEqual(self.s.history_tick(),"HISTORY_BUSY_SKIPPED")
  self.assertEqual(self.s.history_tick(),"NOT_DUE")
  self.assertEqual(len(self.calls),4)
 def test_child_exit(self):
  self.assertEqual(run_child([sys.executable,"-c","raise SystemExit(0)"],{},stop=threading.Event()),0)
 def test_child_timeout(self):
  start=time.monotonic()
  self.assertEqual(run_child([sys.executable,"-c","import time;time.sleep(30)"],{},stop=threading.Event(),timeout=.2),1)
  self.assertLess(time.monotonic()-start,3)
 def test_child_stop(self):
  stop=threading.Event();stop.set()
  self.assertEqual(run_child(["/nonexistent"],{},stop=stop),1)
  stop.clear();t=threading.Timer(.2,stop.set);t.start()
  try:self.assertEqual(run_child([sys.executable,"-c","import time;time.sleep(30)"],{},stop=stop,timeout=10),1)
  finally:t.cancel();t.join()
if __name__=="__main__":unittest.main(verbosity=2)
