"""API-SCI-00: strictly offline, research-only temporal evidence preflight.

Not an evaluator, not a KAIROS gate, not an execution authorization.
No broker, filesystem, clock, network or provider access.
"""
from __future__ import annotations
from datetime import datetime, timezone

REQUIRED = frozenset({
    "schema_version", "attempt_id", "source_id", "content_digest",
    "observed_at", "available_at", "received_at", "decision_as_of",
    "research_clock", "dataset_class", "entitlement_status",
})
CLOCKS = frozenset({"HISTORICAL_AS_OF_DISCOVERY", "PROSPECTIVE_PRE_EVENT"})
DATASETS = frozenset({"SYNTHETIC_FIXTURE", "MARKET_OBSERVED"})
PROHIBITED = frozenset({
    "broker_order", "execution_authority", "risk_override",
    "protected_outcome", "holdout_payload", "credentials", "api_key",
})


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp_must_be_utc_z")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_timestamp") from exc
    if dt.tzinfo != timezone.utc:
        raise ValueError("timestamp_must_be_utc")
    return dt


def preflight(evidence: object) -> dict[str, object]:
    """Fail closed on unknown schema, missing provenance, or temporal leakage.

    A PASS only means *eligible for independent scientific evaluation*.
    """
    reasons: list[str] = []
    if not isinstance(evidence, dict):
        return {"status": "REJECT", "reasons": ["invalid_payload"], "authority": False}
    if PROHIBITED.intersection(evidence):
        reasons.append("prohibited_fields")
    missing = sorted(REQUIRED - evidence.keys())
    if missing:
        reasons.append("missing_required:" + ",".join(missing))
    if evidence.get("schema_version") != "fincept-kairos-science-v1":
        reasons.append("unknown_schema")
    if evidence.get("research_clock") not in CLOCKS:
        reasons.append("unknown_clock")
    if evidence.get("dataset_class") not in DATASETS:
        reasons.append("unknown_dataset_class")
    if evidence.get("entitlement_status") != "ALLOWED":
        reasons.append("entitlement_not_allowed")
    for field in ("attempt_id", "source_id", "content_digest"):
        value = evidence.get(field)
        if not isinstance(value, str) or not value.strip():
            reasons.append("missing_identity:" + field)
    timestamps: dict[str, datetime] = {}
    for field in ("observed_at", "available_at", "received_at", "decision_as_of"):
        try:
            timestamps[field] = _parse_utc(evidence.get(field))
        except ValueError:
            reasons.append("invalid_time:" + field)
    if len(timestamps) == 4:
        if timestamps["observed_at"] > timestamps["available_at"]:
            reasons.append("observed_after_available")
        if timestamps["available_at"] > timestamps["decision_as_of"]:
            reasons.append("future_data_leakage")
        if timestamps["received_at"] > timestamps["decision_as_of"]:
            reasons.append("received_after_decision")
    if evidence.get("research_clock") == "PROSPECTIVE_PRE_EVENT":
        try:
            frozen = _parse_utc(evidence.get("frozen_at"))
            if "decision_as_of" in timestamps and frozen < timestamps["decision_as_of"]:
                reasons.append("freeze_before_decision")
        except ValueError:
            reasons.append("missing_or_invalid_freeze")
        # Prospective evaluation cannot be certified from the proposer payload.
        reasons.append("prospective_requires_independent_freeze_ledger")
    if evidence.get("dataset_class") == "SYNTHETIC_FIXTURE":
        # A fixture may exercise the pipeline, never certify real-world alpha.
        return {"status": "FIXTURE_ONLY" if not reasons else "REJECT",
                "reasons": reasons, "authority": False}
    return {"status": "ELIGIBLE_FOR_INDEPENDENT_REVIEW" if not reasons else "REJECT",
            "reasons": reasons, "authority": False}
