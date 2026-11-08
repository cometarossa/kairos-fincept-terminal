"""DATA-01: offline OHLCV envelope preflight, NOT a scientific admission gate.

Caller must supply a source identity and independently justified timestamps.
Never infer that brokerCandles, Yahoo fallback, or usingSyntheticData=False
proves market provenance. No network, broker, LLM or disk I/O.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
import math

class Rejected(ValueError):
    pass

def _utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise Rejected("UTC_Z_REQUIRED")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Rejected("INVALID_TIMESTAMP") from exc
    if dt.utcoffset().total_seconds() != 0:
        raise Rejected("UTC_REQUIRED")
    return dt

def prepare(candles, provenance, *, min_bars=2):
    """Return a fixture-only payload for VectorBT brokerCandles with audited metadata.

    No acceptance of actual broker data here: only SYNTHETIC_FIXTURE.
    Scientific PIT and licensing gates remain separate in API-SCI-00/KAIROS.
    """
    if not isinstance(provenance, dict) or set(provenance) != {
        "source_id", "classification", "retrieved_at", "requested_from",
        "requested_to", "symbol", "interval", "currency", "rights",
    }:
        raise Rejected("PROVENANCE_SCHEMA")
    if provenance["classification"] != "SYNTHETIC_FIXTURE":
        raise Rejected("REAL_DATA_NOT_AUTHORIZED")
    if provenance["rights"] != "FIXTURE_ONLY":
        raise Rejected("RIGHTS_NOT_VERIFIED")
    for key in ("source_id", "symbol", "interval", "currency"):
        v = provenance[key]
        if not isinstance(v, str) or not v or len(v) > 100:
            raise Rejected("INVALID_IDENTITY")
    start = _utc(provenance["requested_from"])
    end = _utc(provenance["requested_to"])
    retrieved = _utc(provenance["retrieved_at"])
    if start >= end or retrieved < end:
        raise Rejected("INVALID_TIME_ORDER")
    if not isinstance(candles, list) or not min_bars <= len(candles) <= 100000:
        raise Rejected("INVALID_BAR_COUNT")
    rows = []
    previous = None
    for item in candles:
        if not isinstance(item, dict) or set(item) != {"t", "o", "h", "l", "c", "v"}:
            raise Rejected("CANDLE_SCHEMA")
        t = item["t"]
        if type(t) is not int or t < 0 or (previous is not None and t <= previous):
            raise Rejected("BAR_ORDER")
        previous = t
        dt = datetime.fromtimestamp(t, tz=timezone.utc)
        if dt < start or dt > end:
            raise Rejected("BAR_OUTSIDE_REQUEST")
        vals = [item[k] for k in ("o", "h", "l", "c", "v")]
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in vals):
            raise Rejected("INVALID_OHLCV")
        o,h,l,c,v = vals
        if min(o,h,l,c) <= 0 or v < 0 or h < max(o,c,l) or l > min(o,c,h):
            raise Rejected("INVALID_OHLCV")
        rows.append(dict(item))
    # Explicitly do not certify full interval coverage: a request may include
    # weekends/holidays, and a trusted exchange calendar is absent.
    digest = sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "brokerCandles": {provenance["symbol"]: rows},
        "brokerDataSource": "synthetic-regression-fixture",
        "allowSyntheticData": False,
        "data_envelope": {
            **provenance,
            "actual_first": datetime.fromtimestamp(rows[0]["t"], timezone.utc).isoformat().replace("+00:00","Z"),
            "actual_last": datetime.fromtimestamp(rows[-1]["t"], timezone.utc).isoformat().replace("+00:00","Z"),
            "bar_count": len(rows), "sha256": digest,
            "coverage": "UNVERIFIED_SESSION_CALENDAR",
            "scientific_status": "NOT_EVALUATED",
            "broker_authority": False,
        },
    }
