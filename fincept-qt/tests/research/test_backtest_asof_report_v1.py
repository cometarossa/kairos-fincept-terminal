"""Pure research metadata audit; no execution or evidence certification."""

from test_backtest_asof_boundary_v1 import validate_backtest_window

__all__ = ["audit_backtest_evidence"]


def audit_backtest_evidence(payload: object) -> dict:
    """Validate a window and return a research-only metadata report.

    Validation rejects missing or extra keys, including claimed proof fields.
    Timestamp ordering, provider labels and digest syntax do not establish
    data provenance, out-of-sample performance or scientific strategy fitness.
    Validation errors propagate to the caller without issuing a report.
    """
    window = validate_backtest_window(payload)
    return {
        "window": window,
        "evidence_kind": "RESEARCH_METADATA_ONLY",
        "scientific_fitness_certified": False,
        "real_market_data_certified": False,
        "out_of_sample_certified": False,
        "execution_authority": False,
    }
