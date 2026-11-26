import unittest
from unittest.mock import patch
from research.kairos_bridge_v1 import tiingo_train_multi_asset_v1 as p

class PortfolioTests(unittest.TestCase):
    def test_denial_precedes_compute(self):
        for raw,plan in ((b"{}",p.PLAN.read_bytes()),(None,p.PLAN.read_bytes()),
                         (b"x"*(p.MAX_BYTES+1),p.PLAN.read_bytes()),(b"{}",b"{}")):
            with patch.object(p.probe,"run_original_provider") as run:
                with self.assertRaises(p.dev.DevelopmentDenied):
                    p.run_portfolio(raw,plan=plan)
                run.assert_not_called()

    def test_exact_plan(self):
        self.assertEqual(p.dev.digest(p.PLAN.read_bytes()),p.PLAN_SHA)

    def test_unknown_flag_denied_before_input(self):
        with patch.object(p.sys,"argv",["portfolio","--live"]),patch.object(p.sys,"stdin") as stdin:
            self.assertEqual(p.main(),2)
            stdin.buffer.read.assert_not_called()

if __name__=="__main__":
    unittest.main()
