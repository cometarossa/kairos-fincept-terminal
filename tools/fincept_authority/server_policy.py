"""Offline, server-owned capability policy prototype; not authentication or production ACL."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

_POLICY: Mapping[str, frozenset[str]] = MappingProxyType({
    "synthetic-researcher": frozenset({"quant.volatility.read", "market.fixture.read"}),
    "synthetic-reviewer": frozenset({"market.fixture.read"}),
})
_FORBIDDEN = ("broker.", "security.", "order.", "risk.", "deployment.", "account.")
@dataclass(frozen=True)
class Verdict:
    allowed: bool
    code: str
    tool: str

def authorize(principal: str, tool: str, *, request: object = None) -> Verdict:
    """No caller-supplied scopes, approvals or role flags are consulted."""
    if not isinstance(principal, str) or principal not in _POLICY:
        return Verdict(False, "UNAUTHENTICATED", str(tool))
    if not isinstance(tool, str) or not tool or tool.startswith(_FORBIDDEN):
        return Verdict(False, "FORBIDDEN", str(tool))
    if tool not in _POLICY[principal]:
        return Verdict(False, "FORBIDDEN", tool)
    return Verdict(True, "ALLOW_READ_COMPUTE_ONLY", tool)

def catalog(principal: str) -> tuple[str, ...]:
    if principal not in _POLICY:
        return ()
    return tuple(sorted(x for x in _POLICY[principal] if not x.startswith(_FORBIDDEN)))
