"""Offline composition contract for pinned PR #16 and #18 modules.

No Fincept asset is bundled; caller supplies separately checked module objects.
This is not authentication, a science gate, or production authorization.
"""
from __future__ import annotations
from collections.abc import Callable

MAP_V1 = {"quant.volatility.read": ("fincept.research.volatility.fixture.v1", "research.compute")}
DENIED = {"status": "REJECT", "scientific_status": "NOT_EVALUATED", "trading_authority": False}


def execute(principal: str, requested_tool: str, runner: Callable[[], dict], *, policy, boundary, request=None) -> dict:
    """Authorize the exact ACL capability before executing the evidence boundary."""
    if not isinstance(requested_tool, str) or requested_tool not in MAP_V1:
        return {**DENIED, "reason": "UNREGISTERED_TOOL"}
    verdict = policy.authorize(principal, requested_tool, request=request)
    if verdict.allowed is not True or verdict.tool != requested_tool:
        return {**DENIED, "reason": "ACL_DENIED"}
    expected_tool, expected_capability = MAP_V1[requested_tool]

    def checked_runner():
        evidence = runner()
        if not isinstance(evidence, dict) or evidence.get("tool_id") != expected_tool or evidence.get("capability") != expected_capability:
            raise ValueError("MAPPING_MISMATCH")
        return evidence

    outcome = boundary.execute(principal, checked_runner)
    if not isinstance(outcome, dict) or outcome.get("status") != "RESEARCH_ONLY" or outcome.get("scientific_status") != "NOT_EVALUATED" or outcome.get("trading_authority") is not False:
        return {**DENIED, "reason": "BOUNDARY_DENIED"}
    return outcome
