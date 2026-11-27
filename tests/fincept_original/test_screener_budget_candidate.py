import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for p in (ROOT/"scripts/yahoo_capture_service_v1", ROOT/"scripts", ROOT/"fincept-qt/scripts"):
    sys.path.insert(0,str(p))
"""Offline candidate tests; no socket, provider, or production admission."""
import itertools
import unittest
from concurrent.futures import ThreadPoolExecutor
from public_yahoo_shared_budget_v1 import SharedWindow

class Clock:
    def __init__(self):
        self.now=0
    def __call__(self):
        return self.now

class BudgetTest(unittest.TestCase):
    def ready(self, enabled=True):
        clock=Clock();gate=SharedWindow(clock=clock,screener_enabled=enabled)
        clock.now=600
        return clock,gate
    def test_default_matches_original(self):
        for lanes in itertools.product(("history","quote","screener"),repeat=7):
            a=Clock();new=SharedWindow(clock=a);a.now=600
            expected=[];total=quotes=0
            for lane in lanes:
                ok=lane in ("history","quote") and total<8 and (lane!="quote" or quotes<2)
                expected.append(ok)
                if ok:
                    total+=1;quotes+=lane=="quote"
            self.assertEqual(expected,[new.admit(l) for l in lanes])
    def test_no_implicit_opt_in(self):
        _,gate=self.ready(False)
        self.assertFalse(gate.admit("screener"))
        self.assertEqual(sum(gate.admit("history") for _ in range(10)),8)
        with self.assertRaises(ValueError):SharedWindow(screener_enabled=1)
    def test_cold_restart(self):
        c=Clock();gate=SharedWindow(clock=c,screener_enabled=True)
        for t in (0,599.999):
            c.now=t
            self.assertTrue(all(not gate.admit(l) for l in ("history","quote","screener")))
        c.now=600;self.assertTrue(gate.admit("screener"))
        other=SharedWindow(clock=c,screener_enabled=True)
        self.assertFalse(other.admit("screener"))
    def test_screener_first(self):
        _,g=self.ready()
        self.assertEqual(sum(g.admit("screener") for _ in range(6)),2)
        self.assertEqual(sum(g.admit("history") for _ in range(8)),4)
        self.assertEqual(sum(g.admit("quote") for _ in range(5)),2)
        self.assertFalse(g.admit("history"))
    def test_history_can_use_all_if_no_screener(self):
        _,g=self.ready()
        self.assertEqual(sum(g.admit("history") for _ in range(12)),8)
        self.assertFalse(g.admit("screener"))
    def test_busy_history_denies_screener_to_preserve_quotes(self):
        _,g=self.ready()
        self.assertEqual(sum(g.admit("history") for _ in range(6)),6)
        self.assertFalse(g.admit("screener"))
        self.assertEqual(sum(g.admit("quote") for _ in range(5)),2)
    def test_expiry_restores_legacy_capacity(self):
        c,g=self.ready()
        self.assertTrue(g.admit("screener"));self.assertTrue(g.admit("screener"))
        c.now=1199.999;self.assertFalse(g.admit("screener"))
        c.now=1200
        self.assertEqual(sum(g.admit("history") for _ in range(10)),8)
    def test_invalid_clock_latches_all(self):
        c,g=self.ready()
        self.assertTrue(g.admit("screener"))
        c.now=599;self.assertFalse(g.admit("history"))
        c.now=2400
        self.assertTrue(all(not g.admit(l) for l in ("history","quote","screener")))
    def test_invalid_lanes(self):
        _,g=self.ready()
        self.assertTrue(all(not g.admit(l) for l in (None,True,1,"broker","Screener","screener ")))
    def test_atomic_concurrent_limit(self):
        _,g=self.ready()
        with ThreadPoolExecutor(max_workers=12) as pool:
            lanes=["history","quote","screener"]*20
            results=list(pool.map(g.admit,lanes))
        accepted=[lane for lane,ok in zip(lanes,results) if ok]
        self.assertLessEqual(len(accepted),8)
        self.assertLessEqual(accepted.count("quote"),2)
        self.assertLessEqual(accepted.count("screener"),2)
    def test_exhaustive_single_window_reservations(self):
        for lanes in itertools.product(("history","quote","screener"),repeat=9):
            _,g=self.ready()
            counts={k:0 for k in ("history","quote","screener")}
            for l in lanes:
                if g.admit(l):counts[l]+=1
                total=sum(counts.values())
                self.assertLessEqual(total,8)
                self.assertLessEqual(counts["quote"],2)
                self.assertLessEqual(counts["screener"],2)
                if counts["screener"]:
                    self.assertLessEqual(total+max(0,4-counts["history"])+max(0,2-counts["quote"]),8)
    def test_real_tradeoff_not_disguised(self):
        _,g=self.ready()
        self.assertTrue(g.admit("screener"));self.assertTrue(g.admit("screener"))
        self.assertEqual(sum(g.admit("history") for _ in range(8)),4)
        # Existing history-only policy would allow eight. Must not claim
        # unchanged future history capacity for the opt-in policy.
if __name__=="__main__":unittest.main(verbosity=2)
