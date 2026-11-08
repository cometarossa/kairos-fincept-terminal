"""TOOL-01 V6: fixture evidence verifier. Offline, no execution or authority.

The service, NOT the LLM, must supply trusted fixture bytes, trusted installed
source bytes and authenticated principal. This function does not authenticate.
"""
import hashlib
import math

TOOL_ID = "fincept.research.volatility.fixture.v1"
EXPECTED = frozenset({
    "atr", "bb_upper", "bb_middle", "bb_lower",
    "keltner_upper", "keltner_lower", "donchian_upper", "ulcer_index",
})

class EvidenceDenied(ValueError):
    pass

def verify_fixture(envelope, *, fixture_bytes, installed_source_bytes,
                   trusted_principal, permitted_principals=frozenset({"synthetic-researcher"})):
    """Fail closed; returns research-only verdict, never scientific approval."""
    if not isinstance(trusted_principal, str) or trusted_principal not in permitted_principals:
        raise EvidenceDenied("untrusted principal")
    if not isinstance(envelope, dict) or not isinstance(fixture_bytes, bytes) or not isinstance(installed_source_bytes, bytes):
        raise EvidenceDenied("invalid evidence or trusted bytes")
    if not fixture_bytes or not installed_source_bytes:
        raise EvidenceDenied("empty trusted evidence")
    if envelope.get("tool_id") != TOOL_ID or envelope.get("operation") != "research.compute":
        raise EvidenceDenied("tool mismatch")
    if envelope.get("data_classification") != "SYNTHETIC_FIXTURE":
        raise EvidenceDenied("non-fixture data")
    if envelope.get("bar_count") != 120 or type(envelope.get("bar_count")) is not int:
        raise EvidenceDenied("bar count mismatch")
    if envelope.get("broker_authority") is not False or envelope.get("scientific_status") != "NOT_EVALUATED":
        raise EvidenceDenied("authority mismatch")
    cost = envelope.get("external_api_calls")
    if type(cost) is not int or cost != 0:
        raise EvidenceDenied("external cost not zero")
    for key, payload in (("input_sha256", fixture_bytes), ("source_sha256", installed_source_bytes)):
        if envelope.get(key) != hashlib.sha256(payload).hexdigest():
            raise EvidenceDenied("digest mismatch: " + key)
    result = envelope.get("result")
    if not isinstance(result, dict) or set(result) != EXPECTED:
        raise EvidenceDenied("indicator schema mismatch")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in result.values()):
        raise EvidenceDenied("non-finite or invalid indicator")
    return {"status": "RESEARCH_ONLY", "scientific_status": "NOT_EVALUATED",
            "broker_authority": False, "tool_id": TOOL_ID}

if __name__ == "__main__":
    import unittest
    class FixtureTests(unittest.TestCase):
        def setUp(self):
            self.env = dict(tool_id=TOOL_ID, operation="research.compute",
                data_classification="SYNTHETIC_FIXTURE", bar_count=120,
                broker_authority=False, scientific_status="NOT_EVALUATED",
                external_api_calls=0, input_sha256=hashlib.sha256(b"fixture").hexdigest(),
                source_sha256=hashlib.sha256(b"source").hexdigest(),
                result={key: 1.0 for key in EXPECTED})
        def check(self, env=None, **kw):
            args=dict(fixture_bytes=b"fixture", installed_source_bytes=b"source",
                      trusted_principal="synthetic-researcher")
            args.update(kw)
            return verify_fixture(self.env if env is None else env, **args)
        def test_allow(self):
            self.assertEqual(self.check()["status"], "RESEARCH_ONLY")
        def test_spoof(self):
            with self.assertRaises(EvidenceDenied): self.check(trusted_principal="unknown")
        def test_forged_fixture_hash(self):
            with self.assertRaises(EvidenceDenied): self.check(dict(self.env, input_sha256="0"*64))
        def test_forged_source_hash(self):
            with self.assertRaises(EvidenceDenied): self.check(dict(self.env, source_sha256="0"*64))
        def test_nan(self):
            env=dict(self.env, result=dict(self.env["result"]))
            env["result"]["atr"]=float("nan")
            with self.assertRaises(EvidenceDenied): self.check(env)
        def test_inf(self):
            env=dict(self.env, result=dict(self.env["result"]))
            env["result"]["atr"]=float("inf")
            with self.assertRaises(EvidenceDenied): self.check(env)
        def test_missing_indicator(self):
            env=dict(self.env, result={})
            with self.assertRaises(EvidenceDenied): self.check(env)
        def test_wrong_bar_count(self):
            with self.assertRaises(EvidenceDenied): self.check(dict(self.env, bar_count=119))
        def test_mutation(self):
            with self.assertRaises(EvidenceDenied): self.check(dict(self.env, broker_authority=True))
        def test_cost(self):
            with self.assertRaises(EvidenceDenied): self.check(dict(self.env, external_api_calls=1))
    unittest.main()
