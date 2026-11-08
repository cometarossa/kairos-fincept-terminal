"""Offline synthetic agent -> server-owned ACL -> fixture compute -> mock gate.

No real Fincept provider, KAIROS evaluator, network, or trading authority.
"""
from hashlib import sha256
import json
from tools.fincept_authority.server_policy import authorize, catalog

TOOL = "quant.volatility.read"
FORBIDDEN = {"order", "broker", "live", "risk_override", "approval"}

def run(principal, proposal):
    """Only fixed synthetic inputs; a simulated gate cannot certify strategies."""
    available = catalog(principal)
    auth = authorize(principal, TOOL, request=proposal)
    if not auth.allowed:
        return {"catalog": available, "tool_executed": False,
                "verdict": {"status": "REJECT", "reason": auth.code,
                            "scientific_status": "NOT_EVALUATED", "trading_authority": False}}
    candles = [100 + i % 7 for i in range(20)]
    digest = sha256(json.dumps(candles, separators=(",", ":")).encode()).hexdigest()
    evidence = {"tool": TOOL, "source_kind": "SYNTHETIC_FIXTURE", "sha256": digest,
                "value": max(candles) - min(candles), "cost_usd": 0,
                "scientific_status": "NOT_EVALUATED"}
    if not isinstance(proposal, dict) or FORBIDDEN.intersection(proposal):
        status, reason = "REJECT", "MUTATION_FIELD_OR_INVALID_PROPOSAL"
    elif not isinstance(proposal.get("hypothesis"), str) or not proposal["hypothesis"].strip():
        status, reason = "REJECT", "NO_HYPOTHESIS"
    elif proposal.get("evidence_sha256") != digest:
        status, reason = "REJECT", "EVIDENCE_MISMATCH"
    else:
        status, reason = "ADMIT_TO_RESEARCH_QUEUE_ONLY", "MOCK_FIXTURE_REVIEW"
    return {"catalog": available, "tool_executed": True, "evidence": evidence,
            "verdict": {"status": status, "reason": reason,
                        "scientific_status": "NOT_EVALUATED", "trading_authority": False}}
