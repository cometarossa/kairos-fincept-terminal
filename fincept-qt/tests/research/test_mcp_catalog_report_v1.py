"""Audit an MCP catalogue as inventory without granting authority."""

from test_mcp_catalog_boundary_v1 import catalogue_names


_SENSITIVE_SUBSTRINGS = (
    "live", "broker", "credential", "secret", "execute", "order", "trade"
)


def audit_catalog(payload: object) -> dict:
    """Preserve all validated names and flag potentially sensitive names."""
    names = catalogue_names(payload)
    return {
        "total": len(names),
        "all_names": names,
        "suspected_sensitive": [
            name for name in names
            if any(part in name.lower() for part in _SENSITIVE_SUBSTRINGS)
        ],
        "tool_calls_authorized": False,
        "execution_authority": False,
        "market_data_certified": False,
        "complete_runtime_catalog": False,
    }
