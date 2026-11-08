"""Offline tests against separately supplied PR #16 and PR #18 Python sources.

Set FINCEPT_POLICY_PY and FINCEPT_BOUNDARY_PY to exact checked-out files.
No vendored Fincept code, GUI, network, or broker.
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research" / "tool01_v4"))
from composition import execute


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load("pinned_policy", os.environ["FINCEPT_POLICY_PY"])
        cls.boundary = load("pinned_boundary", os.environ["FINCEPT_BOUNDARY_PY"])

    def setUp(self):
        self.calls = 0

    def runner(self, **changes):
        self.calls += 1
        evidence = {"tool_id": "fincept.research.volatility.fixture.v1", "capability": "research.compute",
                    "dataset_class": "SYNTHETIC_FIXTURE", "scientific_status": "NOT_EVALUATED",
                    "broker_authority": False, "input_sha256": "a"*64, "source_sha256": "b"*64,
                    "result": {"atr": 1.2}, "quality_flags": ["SYNTHETIC"],
                    "cost": {"external_api_calls": 0, "provider_credits": 0}}
        return {**evidence, **changes}

    def test_valid_research_only(self):
        r = execute("synthetic-researcher", "quant.volatility.read", self.runner, policy=self.policy, boundary=self.boundary)
        self.assertEqual(r["status"], "RESEARCH_ONLY")
        self.assertFalse(r["trading_authority"])
        self.assertEqual(self.calls, 1)

    def test_reviewer_denied_before_runner(self):
        r = execute("synthetic-reviewer", "quant.volatility.read", self.runner, policy=self.policy, boundary=self.boundary)
        self.assertEqual(r["reason"], "ACL_DENIED")
        self.assertEqual(self.calls, 0)

    def test_unknown_principal_denied(self):
        r = execute("unknown", "quant.volatility.read", self.runner, policy=self.policy, boundary=self.boundary)
        self.assertEqual(r["reason"], "ACL_DENIED")
        self.assertEqual(self.calls, 0)

    def test_forged_scopes_denied(self):
        r = execute("synthetic-reviewer", "quant.volatility.read", self.runner, policy=self.policy, boundary=self.boundary, request={"scopes": ["quant.volatility.read"], "approved": True})
        self.assertEqual(r["reason"], "ACL_DENIED")
        self.assertEqual(self.calls, 0)

    def test_direct_evidence_identifier_denied(self):
        r = execute("synthetic-researcher", "fincept.research.volatility.fixture.v1", self.runner, policy=self.policy, boundary=self.boundary)
        self.assertEqual(r["reason"], "UNREGISTERED_TOOL")
        self.assertEqual(self.calls, 0)

    def test_mutations_not_exposed(self):
        for tool in ("broker.order", "security.mutate", "risk.reset", "deployment.start"):
            r = execute("synthetic-researcher", tool, self.runner, policy=self.policy, boundary=self.boundary)
            self.assertEqual(r["status"], "REJECT")
        self.assertEqual(self.calls, 0)

    def test_evidence_mapping_mismatch(self):
        r = execute("synthetic-researcher", "quant.volatility.read", lambda: self.runner(tool_id="wrong"), policy=self.policy, boundary=self.boundary)
        self.assertEqual(r["reason"], "BOUNDARY_DENIED")

    def test_evidence_broker_authority_rejected(self):
        r = execute("synthetic-researcher", "quant.volatility.read", lambda: self.runner(broker_authority=True), policy=self.policy, boundary=self.boundary)
        self.assertEqual(r["status"], "REJECT")

    def test_evidence_cost_rejected(self):
        r = execute("synthetic-researcher", "quant.volatility.read", lambda: self.runner(cost={"external_api_calls": 1, "provider_credits": 0}), policy=self.policy, boundary=self.boundary)
        self.assertEqual(r["status"], "REJECT")


if __name__ == "__main__":
    unittest.main()
