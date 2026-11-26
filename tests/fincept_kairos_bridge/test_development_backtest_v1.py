"""No market data shipped with tests; strict admission and deny-first behavior."""
import unittest
from unittest.mock import patch
from research.kairos_bridge_v1 import development_backtest_v1 as d

class DevelopmentTests(unittest.TestCase):
    def test_denial_before_provider(self):
        for raw, scope in ((b"{}", d.SCOPE), (None, d.SCOPE), (b"x"*100001,d.SCOPE),
                           (b"{}", "quant.backtest.read"), (b"{}", None)):
            with self.subTest(scope=scope), patch.object(d.probe,"run_original_provider") as run:
                with self.assertRaises(d.DevelopmentDenied):
                    d.run_development(raw,scope=scope)
                run.assert_not_called()

    def test_wrong_snapshot_bytes_are_not_relabelled(self):
        for raw in (b'{"symbol":"SPY"}', b'{"symbol":"EURUSD=X"}', b'{"broker_authority":true}'):
            with self.assertRaises(d.DevelopmentDenied):
                d.admit(raw)

    def test_exact_json_helpers(self):
        with self.assertRaises(d.DevelopmentDenied):
            d.unique([("x",1),("x",2)])
        with self.assertRaises(d.DevelopmentDenied):
            d.constant("NaN")

    def test_cli_denies_unknown_flag_without_reading_stdin(self):
        with patch.object(d.sys,"argv",["replay","--live"]), patch.object(d.sys,"stdin") as stdin:
            self.assertEqual(d.main(),2)
            stdin.buffer.read.assert_not_called()

if __name__ == "__main__":
    unittest.main()
