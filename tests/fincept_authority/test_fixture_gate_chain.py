import unittest
from tools.fincept_authority.fixture_gate_chain import run

class ChainTests(unittest.TestCase):
    def test_unknown_identity(self):
        self.assertEqual(run("unknown", {})["verdict"]["reason"], "UNAUTHENTICATED")
    def test_reviewer_cannot_compute(self):
        self.assertFalse(run("synthetic-reviewer", {"hypothesis": "x"})["tool_executed"])
    def test_fixture_research_only(self):
        first = run("synthetic-researcher", {"hypothesis": "x"})
        result = run("synthetic-researcher", {"hypothesis": "x", "evidence_sha256": first["evidence"]["sha256"]})
        self.assertEqual(result["verdict"]["status"], "ADMIT_TO_RESEARCH_QUEUE_ONLY")
        self.assertEqual(result["verdict"]["scientific_status"], "NOT_EVALUATED")
        self.assertFalse(result["verdict"]["trading_authority"])
        self.assertEqual(result["evidence"]["cost_usd"], 0)
    def test_tamper(self):
        self.assertEqual(run("synthetic-researcher", {"hypothesis": "x", "evidence_sha256": "bad"})["verdict"]["reason"], "EVIDENCE_MISMATCH")
    def test_no_hypothesis(self):
        self.assertEqual(run("synthetic-researcher", {})["verdict"]["reason"], "NO_HYPOTHESIS")
    def test_mutation_fields(self):
        digest = run("synthetic-researcher", {})["evidence"]["sha256"]
        for key in ("order", "broker", "live", "risk_override", "approval"):
            with self.subTest(key=key):
                result = run("synthetic-researcher", {"hypothesis": "x", "evidence_sha256": digest, key: True})
                self.assertEqual(result["verdict"]["status"], "REJECT")
if __name__ == "__main__":
    unittest.main()
