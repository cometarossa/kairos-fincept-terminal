"""Offline synthetic contract tests. No Fincept import or broker call."""
import unittest
from research.tool01_v2.fixture_boundary import execute

VALID = {
    "tool_id": "fincept.research.volatility.fixture.v1",
    "capability": "research.compute", "dataset_class": "SYNTHETIC_FIXTURE",
    "input_sha256": "a" * 64, "source_sha256": "b" * 64,
    "scientific_status": "NOT_EVALUATED", "broker_authority": False,
    "cost": {"external_api_calls": 0, "provider_credits": 0},
    "result": {"atr": 1.2}, "quality_flags": ["SYNTHETIC"],
}


class TestFixtureBoundary(unittest.TestCase):
    def test_valid(self):
        result = execute("synthetic-researcher", lambda: VALID.copy())
        self.assertEqual(result["status"], "RESEARCH_ONLY")
        self.assertFalse(result["trading_authority"])

    def test_reviewer_denied(self):
        self.assertEqual(execute("synthetic-reviewer", lambda: VALID)["status"], "REJECT")

    def test_unknown_denied(self):
        self.assertEqual(execute("unknown", lambda: VALID)["status"], "REJECT")

    def test_unhashable_identity_denied(self):
        self.assertEqual(execute([], lambda: VALID)["status"], "REJECT")

    def test_mutation_denied(self):
        self.assertEqual(execute("synthetic-researcher",
                         lambda: {**VALID, "broker_authority": True})["status"], "REJECT")

    def test_market_claim_denied(self):
        self.assertEqual(execute("synthetic-researcher",
                         lambda: {**VALID, "dataset_class": "MARKET"})["status"], "REJECT")

    def test_missing_digest_denied(self):
        self.assertEqual(execute("synthetic-researcher",
                         lambda: {**VALID, "input_sha256": ""})["status"], "REJECT")

    def test_error_closed(self):
        def broken():
            raise RuntimeError("synthetic error")
        self.assertEqual(execute("synthetic-researcher", broken)["status"], "REJECT")

    def test_science_claim_denied(self):
        self.assertEqual(execute("synthetic-researcher",
                         lambda: {**VALID, "scientific_status": "PASS"})["status"], "REJECT")


if __name__ == "__main__":
    unittest.main()
