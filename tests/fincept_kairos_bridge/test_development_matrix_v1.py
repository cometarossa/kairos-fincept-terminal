import unittest
from unittest.mock import patch
from research.kairos_bridge_v1 import development_matrix_v1 as m

class MatrixTests(unittest.TestCase):
    def test_exact_manifest(self):
        plan = m.admit_manifest(m.MANIFEST.read_bytes())
        self.assertEqual(len(plan["cases"]),3)
        self.assertIs(plan["selection_authorized"],False)

    def test_invalid_input_never_computes(self):
        for manifest,raw in ((b"{}",b"{}"),(m.MANIFEST.read_bytes(),b"{}")):
            with patch.object(m,"_case") as compute:
                with self.assertRaises(m.dev.DevelopmentDenied):
                    m.run_matrix(raw,manifest=manifest)
                compute.assert_not_called()

    def test_all_attempts_including_failure_are_recorded(self):
        def fake(candles,case,plan):
            if case["id"]=="sma_10_30":
                raise ValueError("private diagnostic")
            return {"case":case["id"],"status":"MATCHED_ORACLE"}
        with patch.object(m.dev,"admit",return_value=[{}]*128),patch.object(m,"_case",side_effect=fake) as compute:
            result=m.run_matrix(b"test",manifest=m.MANIFEST.read_bytes())
        self.assertEqual(compute.call_count,3)
        self.assertEqual((result["attempted"],result["matched"],result["rejected"]),(3,2,1))
        self.assertEqual(result["results"][1],{"case":"sma_10_30","status":"REJECTED_OR_UNAVAILABLE"})
        self.assertIs(result["selection_authorized"],False)
        self.assertIs(result["execution_authority"],False)
        self.assertEqual(result["receipt_sha256"],m.dev.digest(m.dev.canonical({k:v for k,v in result.items() if k!="receipt_sha256"})))

if __name__=="__main__":
    unittest.main()
