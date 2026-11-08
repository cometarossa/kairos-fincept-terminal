"""TOOL-01 V2: fixture-only evidence boundary, not a KAIROS scientific gate.

The local runner may be TOOL-01 run(source_file) in an existing isolated Fincept
environment. No Qt, broker, network, model or credentials are imported here.
This is not production authentication; server-owned ACL PR #16 is separate.
"""
from __future__ import annotations
import re
from typing import Callable

_ALLOWED = frozenset({"synthetic-researcher"})
_TOOL = "fincept.research.volatility.fixture.v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")


def execute(principal: str, local_fixture_runner: Callable[[], dict]) -> dict:
    rejected = {"status": "REJECT", "scientific_status": "NOT_EVALUATED",
                "trading_authority": False}
    if not isinstance(principal, str) or principal not in _ALLOWED:
        return {**rejected, "reason": "CAPABILITY_DENIED"}
    try:
        evidence = local_fixture_runner()
        if not isinstance(evidence, dict):
            raise ValueError("INVALID_EVIDENCE")
        if (evidence.get("tool_id") != _TOOL or
            evidence.get("capability") != "research.compute" or
            evidence.get("dataset_class") != "SYNTHETIC_FIXTURE" or
            evidence.get("scientific_status") != "NOT_EVALUATED" or
            evidence.get("broker_authority") is not False or
            not all(isinstance(evidence.get(k), str) and
                    _SHA.fullmatch(evidence[k]) for k in
                    ("input_sha256", "source_sha256")) or
            not isinstance(evidence.get("result"), dict) or
            not evidence["result"] or
            not isinstance(evidence.get("quality_flags"), list) or
            "SYNTHETIC" not in evidence["quality_flags"] or
            evidence.get("cost") != {"external_api_calls": 0,
                                    "provider_credits": 0}):
            raise ValueError("INVALID_EVIDENCE")
        return {"status": "RESEARCH_ONLY", "scientific_status": "NOT_EVALUATED",
                "trading_authority": False, "evidence": evidence}
    except Exception:
        return {**rejected, "reason": "TOOL_OR_EVIDENCE_REJECTED"}
