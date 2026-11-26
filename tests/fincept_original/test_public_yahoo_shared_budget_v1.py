import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts/yahoo_capture_service_v1"))
import unittest,threading
from concurrent.futures import ThreadPoolExecutor
from public_yahoo_shared_budget_v1 import SharedWindow
class Clock:
    now=0
    def __call__(self):return self.now

class TestBudget(unittest.TestCase):
    def setUp(self):
        self.clock=Clock()
        self.gate=SharedWindow(clock=self.clock)
    def ready(self):self.clock.now=600
    def test_restart_does_not_reset_budget(self):
        self.clock.now=599.999
        self.assertFalse(self.gate.admit("history"))
        self.assertFalse(self.gate.admit("quote"))
        self.ready();self.assertTrue(self.gate.admit("history"))
        other=SharedWindow(clock=self.clock)
        self.assertFalse(other.admit("history"))
    def test_history_alone(self):
        self.ready()
        self.assertEqual(sum(self.gate.admit("history") for _ in range(12)),8)
        self.assertFalse(self.gate.admit("quote"))
    def test_quote_budget_and_history_reserve(self):
        self.ready()
        self.assertEqual(sum(self.gate.admit("quote") for _ in range(20)),2)
        self.assertEqual(sum(self.gate.admit("history") for _ in range(20)),6)
    def test_history_priority_under_load(self):
        self.ready()
        self.assertEqual(sum(self.gate.admit("history") for _ in range(7)),7)
        self.assertTrue(self.gate.admit("quote"))
        self.assertFalse(self.gate.admit("quote"))
    def test_sliding_boundary(self):
        self.ready()
        self.assertTrue(self.gate.admit("quote"))
        self.clock.now=650;self.assertTrue(self.gate.admit("quote"))
        self.clock.now=1199.999;self.assertFalse(self.gate.admit("quote"))
        self.clock.now=1200;self.assertTrue(self.gate.admit("quote"))
        self.assertFalse(self.gate.admit("quote"))
        self.clock.now=1250;self.assertTrue(self.gate.admit("quote"))
    def test_unknown_lane(self):
        self.ready()
        for value in (None,True,1,"broker","quote ","QUOTE"):
            self.assertFalse(self.gate.admit(value))
        self.assertEqual(sum(self.gate.admit("history") for _ in range(9)),8)
    def test_clock_regression_latches(self):
        self.ready();self.assertTrue(self.gate.admit("history"))
        self.clock.now=599;self.assertFalse(self.gate.admit("quote"))
        self.clock.now=2400;self.assertFalse(self.gate.admit("history"))
    def test_clock_nan_latches(self):
        self.ready();self.clock.now=float("nan")
        self.assertFalse(self.gate.admit("history"))
        self.clock.now=2400;self.assertFalse(self.gate.admit("history"))
    def test_atomic_admission_across_lanes(self):
        self.ready()
        barrier=threading.Barrier(16)
        lanes=["quote","history"]*8
        def call(lane):
            barrier.wait(timeout=5)
            return lane,self.gate.admit(lane)
        with ThreadPoolExecutor(max_workers=16) as pool:
            results=list(pool.map(call,lanes))
        accepted=[lane for lane,ok in results if ok]
        self.assertEqual(len(accepted),8)
        self.assertLessEqual(accepted.count("quote"),2)
        self.assertGreaterEqual(accepted.count("history"),6)
if __name__=="__main__":unittest.main(verbosity=2)
