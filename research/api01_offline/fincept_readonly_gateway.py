"""API-01 isolated proof: deny-by-default, offline, read-only Fincept tool catalog.

No network listener, broker connection, environment/credential access or Fincept
imports. This is a synthetic contract test, NOT a deployed KAIROS gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


class ToolDenied(PermissionError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    capability: str
    version: str
    schema: Mapping[str, type]
    source_id: str


class OfflineToolGateway:
    """A local reference interface. Never accepts agent-supplied capabilities."""

    _ALLOWED = frozenset({"market.read", "research.compute"})

    def __init__(self) -> None:
        self._registry: dict[str, tuple[ToolSpec, Callable[..., Any]]] = {}

    def register(self, spec: ToolSpec, handler: Callable[..., Any]) -> None:
        if spec.capability not in self._ALLOWED:
            raise ToolDenied("capability is not available in research gateway")
        if not spec.tool_id or not spec.source_id or not spec.version:
            raise ValueError("tool identity, version and source are mandatory")
        if spec.tool_id in self._registry:
            raise ValueError("duplicate tool identity")
        if not callable(handler):
            raise TypeError("handler must be callable")
        if any(not isinstance(k, str) or not isinstance(v, type)
               for k, v in spec.schema.items()):
            raise ValueError("invalid input schema")
        self._registry[spec.tool_id] = (spec, handler)

    def catalog(self) -> tuple[dict[str, str], ...]:
        return tuple({
            "tool_id": spec.tool_id, "capability": spec.capability,
            "version": spec.version, "source_id": spec.source_id,
        } for spec, _ in self._registry.values())

    def call(self, tool_id: str, args: Mapping[str, Any],
             granted_capabilities: frozenset[str]) -> dict[str, Any]:
        if tool_id not in self._registry:
            raise ToolDenied("unknown tool")
        spec, handler = self._registry[tool_id]
        if spec.capability not in self._ALLOWED or spec.capability not in granted_capabilities:
            raise ToolDenied("capability not granted")
        if not isinstance(args, Mapping) or set(args) != set(spec.schema):
            raise ToolDenied("input schema mismatch")
        for key, expected in spec.schema.items():
            if type(args[key]) is not expected:
                raise ToolDenied("input type mismatch")
        output = handler(**dict(args))
        if not isinstance(output, dict) or not isinstance(output.get("value"), (int, float)):
            raise ValueError("invalid result envelope")
        if type(output["value"]) is bool:
            raise ValueError("invalid numeric result")
        import math
        if not math.isfinite(float(output["value"])):
            raise ValueError("non-finite result")
        return {
            "tool_id": spec.tool_id,
            "tool_version": spec.version,
            "source_id": spec.source_id,
            "data_mode": "SYNTHETIC_FIXTURE",
            "authorization": "READ_ONLY",
            "result": output,
            "gate_status": "NOT_EVALUATED",
            "broker_authority": False,
        }

[executed on device: iMac-3.local (7ee641a1-2c6a-4142-9db0-28fef901d728)]