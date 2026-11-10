"""Build a read-only Fincept-KAIROS dashboard report from an actual OFFLINE
Fincept synthetic volatility fixture envelope, e.g. draft TOOL-01 PR #15.

No broker, HTTP, secrets, trading, host monitoring or paid model calls.
The output is LOCAL/UNATTESTED: it is not KAIROS scientific admission.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import tempfile

SOURCE_SHA = re.compile(r"^[0-9a-f]{64}$")
TOOL_ID = "fincept.research.volatility.fixture.v1"
EXPECTED_FIELDS = {
    "atr", "bb_mavg", "bb_hband", "bb_lband",
    "kc_mavg", "dc_hband", "dc_lband", "ui",
}


class EvidenceRejected(ValueError):
    pass


def report_from_evidence(evidence: dict, *, clock=None) -> dict:
    """Fail closed on any claim of live data, cost, or trading authority."""
    if not isinstance(evidence, dict):
        raise EvidenceRejected("evidence must be an object")
    if evidence.get("tool_id") != TOOL_ID:
        raise EvidenceRejected("unknown tool")
    if evidence.get("capability") != "research.compute":
        raise EvidenceRejected("wrong capability")
    if evidence.get("dataset_class") != "SYNTHETIC_FIXTURE":
        raise EvidenceRejected("live or unknown data forbidden")
    if evidence.get("scientific_status") != "NOT_EVALUATED":
        raise EvidenceRejected("cannot assert scientific admission")
    if evidence.get("broker_authority") is not False:
        raise EvidenceRejected("broker authority forbidden")
    if type(evidence.get("bar_count")) is not int or evidence["bar_count"] != 120:
        raise EvidenceRejected("expected 120 synthetic bars")
    for key in ("source_sha256", "input_sha256"):
        if not isinstance(evidence.get(key), str) or not SOURCE_SHA.fullmatch(evidence[key]):
            raise EvidenceRejected("missing valid hash: " + key)
    cost = evidence.get("cost")
    if not isinstance(cost, dict) or type(cost.get("external_api_calls")) is not int or cost["external_api_calls"] != 0:
        raise EvidenceRejected("external calls must be zero")
    if type(cost.get("provider_credits")) is not int or cost["provider_credits"] != 0:
        raise EvidenceRejected("provider credits must be zero")
    if evidence.get("rights") != "FIXTURE_ONLY" or evidence.get("source_id") != "TOOL01_DETERMINISTIC_SYNTHETIC_V1":
        raise EvidenceRejected("unexpected provenance or rights")
    required_flags = {"SYNTHETIC", "NOT_MARKET_OBSERVED", "NO_PIT_CERTIFICATION", "NO_INDEPENDENT_EVALUATOR"}
    flags = evidence.get("quality_flags")
    if not isinstance(flags, list) or not required_flags.issubset(set(x for x in flags if isinstance(x, str))):
        raise EvidenceRejected("missing negative provenance flags")
    result = evidence.get("result")
    if not isinstance(result, dict) or set(result) != EXPECTED_FIELDS:
        raise EvidenceRejected("indicator schema mismatch")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in result.values()):
        raise EvidenceRejected("invalid or nonfinite indicator")
    for key in ("observed_at", "available_at"):
        if evidence.get(key) != "2024-04-29T00:00:00Z":
            raise EvidenceRejected("unexpected synthetic clock")
    if evidence.get("received_at") != "NOT_APPLICABLE_OFFLINE_FIXTURE":
        raise EvidenceRejected("unexpected receipt clock")

    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise EvidenceRejected("clock must be timezone-aware")
    return {
        "schema": "fincept_kairos_research_status_v1",
        "mode": "SYNTHETIC_FIXTURE",
        "scientific_status": "NOT_EVALUATED",
        "broker_authority": False,
        "external_api_calls": 0,
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_sha256": evidence["source_sha256"],
        "stages": {
            "fincept_tool": "MOCK_PASS",
            "tool_gateway": "BLOCKED",
            "kairos_science": "NOT_VERIFIED",
            "theoretical_portfolio": "BLOCKED",
        },
    }


def save_local_report(path: Path, report: dict) -> None:
    """Atomic local file update; never follow a pre-existing symlink target."""
    path = path.expanduser()
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise EvidenceRejected("report destination must be a regular non-symlink file")
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise EvidenceRejected("report directory must already exist and not be a symlink")
    payload = (json.dumps(report, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")
    if len(payload) > 16384:
        raise EvidenceRejected("report too large")
    handle = tempfile.NamedTemporaryFile(dir=parent, prefix=".kairos-report-", delete=False)
    try:
        os.fchmod(handle.fileno(), 0o600)
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink():
            raise EvidenceRejected("destination changed into symlink")
        os.replace(handle.name, path)
    finally:
        if os.path.exists(handle.name):
            os.unlink(handle.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic-only KAIROS dashboard status exporter")
    parser.add_argument("--evidence", required=True, type=Path, help="TOOL-01 V1 synthetic evidence JSON")
    parser.add_argument("--out", required=True, type=Path, help="Qt AppDataLocation/kairos/research_status_v1.json")
    args = parser.parse_args()
    raw = args.evidence.read_bytes()
    if not raw or len(raw) > 16384:
        raise EvidenceRejected("evidence file empty or too large")
    evidence = json.loads(raw)
    report = report_from_evidence(evidence)
    save_local_report(args.out, report)
    print("SYNTHETIC_LOCAL_REPORT_WRITTEN (not scientific proof; no broker authority)")


if __name__ == "__main__":
    main()
