import unittest
from unittest.mock import patch
from research.kairos_bridge_v1 import non_sma_development_matrix_v1 as m

class NonSmaMatrixTests(unittest.TestCase):
    def test_exact_frozen_manifest(self):
        plan=m.admit_manifest(m.MANIFEST.read_bytes())
        self.assertEqual([x["kind"] for x in plan["cases"]],["momentum","breakout","mean_reversion"])
        self.assertIs(plan["selection_authorized"],False)

    def test_bad_input_before_compute(self):
        for manifest,raw in ((b"{}",b"{}"),(m.MANIFEST.read_bytes(),b"{}")):
            with patch.object(m,"_case") as compute:
                with self.assertRaises(m.dev.DevelopmentDenied):
                    m.run_matrix(raw,manifest=manifest)
                compute.assert_not_called()

    def test_rejected_case_not_suppressed(self):
        def fake(candles,case,plan):
            if case["kind"]=="breakout":
                raise ValueError("private error")
            return {"case":case["id"],"status":"MATCHED_ORACLE"}
        with patch.object(m.dev,"admit",return_value=[{}]*128),patch.object(m,"_case",side_effect=fake) as compute:
            out=m.run_matrix(b"test",manifest=m.MANIFEST.read_bytes())
        self.assertEqual(compute.call_count,3)
        self.assertEqual((out["attempted"],out["matched"],out["rejected"]),(3,2,1))
        self.assertEqual(out["results"][1],{"case":"breakout_20","status":"REJECTED_OR_UNAVAILABLE"})
        self.assertIs(out["execution_authority"],False)
        self.assertEqual(out["receipt_sha256"],m.dev.digest(m.dev.canonical({k:v for k,v in out.items() if k!="receipt_sha256"})))

if __name__=="__main__":
    unittest.main()
