"""Versioned, allowlisted evidence envelope for the synthetic backtest probe.

The probe result is free-form JSON. Anything that later crosses the read-only
Fincept -> KAIROS boundary must instead be an envelope with an exact field set,
fixed labels and bounded numbers, so a consumer can refuse everything else.

Field names follow the evidence contract of the unmerged bridge sidecar
(PR #25, `research/kairos_bridge_v1/sidecar.py`) where the meaning is the
same, so this envelope can be listed there under a server-owned capability
(suggested name: `quant.backtest.read`) without renaming. This module does not
edit that policy, makes no network connection and writes no file.

Deny by default: unknown or missing keys at any level, wrong types (bool is
not a number), non-finite numbers, any label other than the fixed synthetic
ones, unpinned sources or fixtures, a wrong self-hash, or an oversize payload
all raise `EvidenceRejected`. An accepted envelope is still only a statement
that pinned code reproduced an oracle on a synthetic fixture: it carries
`scientific_status=NOT_EVALUATED`, `broker_authority=false` and
`promotion_eligible=false`, and validation never changes that.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math

try:
    from tools.fincept_audit import backtest_provider_probe_v1 as probe
except ImportError:  # pragma: no cover - direct execution
    import backtest_provider_probe_v1 as probe

SCHEMA_VERSION = "kairos_fincept_backtest_evidence_v1"
TOOL_ID = "fincept.research.backtest.sma_crossover.fixture.v1"
SUGGESTED_CAPABILITY = "quant.backtest.read"
MAX_ENVELOPE_BYTES = 32 * 1024
MAX_SCENARIOS = 64
QUALITY_FLAGS = ("SYNTHETIC", "NOT_MARKET_OBSERVED", "NO_PIT_CERTIFICATION",
                 "NO_INDEPENDENT_EVALUATOR")
ENVELOPE_FIELDS = frozenset({
    "schema_version", "tool_id", "capability", "source_id", "dataset_class",
    "sources", "fixtures", "observed_at", "available_at", "received_at",
    "rights", "cost", "quality_flags", "result", "scientific_status",
    "broker_authority", "promotion_eligible", "evidence_sha256",
})
FIXED = {
    "schema_version": SCHEMA_VERSION,
    "tool_id": TOOL_ID,
    "capability": "research.compute",
    "source_id": "TOOL01_BACKTEST_DETERMINISTIC_SYNTHETIC_V1",
    "dataset_class": "SYNTHETIC_FIXTURE",
    "observed_at": "NOT_APPLICABLE_SYNTHETIC_FIXTURE",
    "available_at": "NOT_APPLICABLE_SYNTHETIC_FIXTURE",
    "received_at": "NOT_APPLICABLE_OFFLINE_FIXTURE",
    "rights": "FIXTURE_ONLY",
    "scientific_status": "NOT_EVALUATED",
    "broker_authority": False,
    "promotion_eligible": False,
}
RESULT_FIELDS = frozenset({"comparison", "relative_tolerance", "scenario_count", "scenarios",
                           "provider_flags_fixture_as_market_data"})
SCENARIO_NUMBERS = {
    # field: (lower bound, upper bound) - generous sanity limits, not expectations
    "total_return": (-1.0, 100.0),
    "total_fees": (0.0, 1e9),
    "max_drawdown": (0.0, 1.0),
    "sharpe_cagr_based": (-1e3, 1e3),
}
SCENARIO_INTEGERS = {"bars": (30, 2000), "trades": (1, 10000), "periods_per_year": (1, 100000)}
SCENARIO_FIELDS = frozenset({"name", "exit_reasons"}) | set(SCENARIO_NUMBERS) | set(SCENARIO_INTEGERS)
EXIT_REASONS = frozenset({"signal", "stop_loss", "take_profit", "trailing_stop", "end_of_data"})
_NAME_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")


class EvidenceRejected(ValueError):
    """No usable evidence and no authority."""


def canonical(document: dict) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _self_hash(envelope: dict) -> str:
    return sha256(canonical({k: v for k, v in envelope.items() if k != "evidence_sha256"})).hexdigest()


def build(probe_result: dict) -> dict:
    """Project a probe result onto the envelope. Only allowlisted values are copied."""
    if not isinstance(probe_result, dict) or probe_result.get("schema") != probe.SCHEMA:
        raise EvidenceRejected("NOT_A_PROBE_RESULT")
    scenarios = probe_result.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise EvidenceRejected("PROBE_RESULT_HAS_NO_SCENARIOS")
    projected = []
    for item in scenarios:
        if not isinstance(item, dict) or item.get("status") != "ORIGINAL_PROVIDER_MATCHES_EXACT_ORACLE":
            raise EvidenceRejected("SCENARIO_NOT_VERIFIED")
        if item.get("network_attempts_denied") != 0:
            raise EvidenceRejected("SCENARIO_ATTEMPTED_NETWORK")
        projected.append({
            "name": item.get("scenario"),
            "bars": item.get("bars"),
            "trades": item.get("trades"),
            "exit_reasons": item.get("exit_reasons"),
            "periods_per_year": item.get("periods_per_year"),
            "total_return": item.get("oracle_total_return"),
            "total_fees": item.get("oracle_total_fees"),
            "max_drawdown": item.get("oracle_max_drawdown"),
            "sharpe_cagr_based": item.get("oracle_sharpe_as_stated_by_provider"),
        })
    envelope = dict(FIXED)
    envelope.update({
        "sources": dict(probe.PINNED_SOURCES),
        "fixtures": dict(probe.FIXTURE_SHA256),
        "cost": {"external_api_calls": 0, "provider_credits": 0},
        "quality_flags": list(QUALITY_FLAGS),
        "result": {
            "comparison": "ORIGINAL_PROVIDER_MATCHES_EXACT_ORACLE",
            "relative_tolerance": probe.REL_TOL,
            "scenario_count": len(projected),
            "scenarios": projected,
            # The provider itself reported every fixture as broker data.
            "provider_flags_fixture_as_market_data": all(
                item.get("provider_using_synthetic_data") is False for item in scenarios),
        },
    })
    try:
        envelope["evidence_sha256"] = _self_hash(envelope)
    except ValueError as exc:  # NaN or infinity in a projected number
        raise EvidenceRejected("NON_FINITE_NUMBER") from exc
    return validate(envelope)


def _exact(value, expected, code: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise EvidenceRejected(code)


def _number(value, low: float, high: float, code: str) -> None:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise EvidenceRejected(code)


def validate(envelope: object) -> dict:
    """Return the envelope unchanged if every rule holds; raise otherwise."""
    if type(envelope) is not dict or set(envelope) != ENVELOPE_FIELDS:
        raise EvidenceRejected("INVALID_ENVELOPE_FIELDS")
    for key, expected in FIXED.items():
        _exact(envelope[key], expected, "INVALID_FIXED_FIELD:" + key)
    _exact(envelope["sources"], dict(probe.PINNED_SOURCES), "UNPINNED_OR_CHANGED_SOURCES")
    _exact(envelope["fixtures"], dict(probe.FIXTURE_SHA256), "UNPINNED_OR_CHANGED_FIXTURES")
    _exact(envelope["cost"], {"external_api_calls": 0, "provider_credits": 0}, "NONZERO_OR_INVALID_COST")
    for value in envelope["cost"].values():
        if type(value) is not int:
            raise EvidenceRejected("NONZERO_OR_INVALID_COST")
    _exact(envelope["quality_flags"], list(QUALITY_FLAGS), "INVALID_QUALITY_FLAGS")

    result = envelope["result"]
    if type(result) is not dict or set(result) != RESULT_FIELDS:
        raise EvidenceRejected("INVALID_RESULT_FIELDS")
    _exact(result["comparison"], "ORIGINAL_PROVIDER_MATCHES_EXACT_ORACLE", "INVALID_COMPARISON")
    _exact(result["relative_tolerance"], probe.REL_TOL, "INVALID_TOLERANCE")
    if type(result["provider_flags_fixture_as_market_data"]) is not bool:
        raise EvidenceRejected("INVALID_PROVIDER_FLAG")
    scenarios = result["scenarios"]
    if type(scenarios) is not list or not 1 <= len(scenarios) <= MAX_SCENARIOS:
        raise EvidenceRejected("INVALID_SCENARIO_LIST")
    _exact(result["scenario_count"], len(scenarios), "SCENARIO_COUNT_MISMATCH")
    seen = set()
    for item in scenarios:
        if type(item) is not dict or set(item) != SCENARIO_FIELDS:
            raise EvidenceRejected("INVALID_SCENARIO_FIELDS")
        name = item["name"]
        if type(name) is not str or not 1 <= len(name) <= 64 or not set(name) <= _NAME_CHARS \
                or name in seen:
            raise EvidenceRejected("INVALID_SCENARIO_NAME")
        seen.add(name)
        for key, (low, high) in SCENARIO_INTEGERS.items():
            if type(item[key]) is not int or not low <= item[key] <= high:
                raise EvidenceRejected("INVALID_SCENARIO_INTEGER:" + key)
        for key, (low, high) in SCENARIO_NUMBERS.items():
            _number(item[key], low, high, "INVALID_SCENARIO_NUMBER:" + key)
        reasons = item["exit_reasons"]
        if type(reasons) is not list or not reasons or reasons != sorted(set(reasons)) \
                or not all(type(r) is str for r in reasons) or not set(reasons) <= EXIT_REASONS:
            raise EvidenceRejected("INVALID_EXIT_REASONS")

    digest = envelope["evidence_sha256"]
    if type(digest) is not str or len(digest) != 64:
        raise EvidenceRejected("INVALID_EVIDENCE_HASH")
    try:
        recomputed = _self_hash(envelope)
        size = len(canonical(envelope))
    except ValueError as exc:
        raise EvidenceRejected("NON_FINITE_NUMBER") from exc
    if digest != recomputed:
        raise EvidenceRejected("EVIDENCE_HASH_MISMATCH")
    if size > MAX_ENVELOPE_BYTES:
        raise EvidenceRejected("OVERSIZE_ENVELOPE")
    return envelope


def loads(text: str) -> dict:
    """Parse and validate an envelope received as text (duplicate keys refused)."""
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_ENVELOPE_BYTES:
        raise EvidenceRejected("OVERSIZE_ENVELOPE")

    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        if len(set(keys)) != len(keys):
            raise EvidenceRejected("DUPLICATE_JSON_KEY")
        return dict(pairs)

    def no_constants(name):
        raise EvidenceRejected("NON_FINITE_NUMBER")

    try:
        document = json.loads(text, object_pairs_hook=no_duplicates, parse_constant=no_constants)
    except ValueError as exc:
        if isinstance(exc, EvidenceRejected):
            raise
        raise EvidenceRejected("INVALID_JSON") from exc
    return validate(document)


def main() -> int:
    import argparse
    from pathlib import Path
    import sys

    parser = argparse.ArgumentParser(description="Run the probe and print its evidence envelope")
    parser.add_argument("--backtesting-dir", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    try:
        envelope = build(probe.run_all(args.backtesting_dir, args.python))
    except (EvidenceRejected, probe.ProbeError, probe.oracle.OracleRefused, OSError) as exc:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "status": "REJECTED",
                          "reason": str(exc)[:200], "broker_authority": False,
                          "promotion_eligible": False}))
        return 2
    print(canonical(envelope).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
