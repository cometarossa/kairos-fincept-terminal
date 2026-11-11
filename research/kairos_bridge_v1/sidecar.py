"""Fincept -> KAIROS local RESEARCH-ONLY synthetic bridge (composition V1).

Zero changes to Fincept application/source tree, Qt, daemon, market/broker, MCP,
credentials or KAIROS scientific gates. Standalone opt-in CLI. The caller's
principal is a *toy offline identity*, NOT authenticated. No network service.

Composes existing API-01 server-owned ACL (#16/#17), exact unmerged TOOL-01
fixture runner (#15) and the ORIGINAL, pinned Fincept volatility module.
Never substitutes this bridge for an independently verified KAIROS evaluator.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import site
import subprocess
import sys
import tempfile

from tools.fincept_authority.server_policy import authorize

POLICY_TOOL = "quant.volatility.read"
EVIDENCE_TOOL_ID = "fincept.research.volatility.fixture.v1"
EXPECTED_SOURCE_SHA256 = "76c8a2329c3109d801222ecc987f57005041533e8264c90f1d8b46a4c0109897"
EXPECTED_RUNNER_SHA256 = "35574f23f043811d0524bd17c11dae7a48cc5234e5f0117e0fe60393762879d3"
EXPECTED_INPUT_SHA256 = "db72401cbb2ee11527be55c95949060ccb5841ecba58ba8d2e8dd3e4309c877b"
MAX_SOURCE_BYTES = 16 * 1024
MAX_RUNNER_BYTES = 16 * 1024
MAX_EVIDENCE_BYTES = 16 * 1024
RUN_TIMEOUT_SECONDS = 20
EXPECTED_VALUE = {
    "atr": 2.5,
    "bb_hband": 107.96139351902247,
    "bb_lband": 105.31396828097752,
    "bb_mavg": 106.63768089999999,
    "dc_hband": 108.696762,
    "dc_lband": 104.397904,
    "kc_mavg": 106.60434756666666,
    "ui": 1.1386454094698457,
}
REQUIRED_QUALITY = (
    "SYNTHETIC", "NOT_MARKET_OBSERVED", "NO_PIT_CERTIFICATION",
    "NO_INDEPENDENT_EVALUATOR",
)
EVIDENCE_FIELDS = frozenset({
    "tool_id", "capability", "source_file", "source_sha256", "source_id",
    "dataset_class", "input_sha256", "bar_count", "observed_at", "available_at",
    "received_at", "rights", "cost", "quality_flags", "result",
    "scientific_status", "broker_authority",
})


class BridgeRejected(ValueError):
    """Every failure means no usable evidence and no authority."""


def _read_pinned(path: Path, expected_name: str, sha: str, limit: int) -> bytes:
    """Read the bytes ONCE; execute a private copy of those same verified bytes."""
    if path.name != expected_name or path.is_symlink() or not path.is_file():
        raise BridgeRejected("INVALID_PINNED_SOURCE_PATH")
    data = path.read_bytes()
    if not data or len(data) > limit:
        raise BridgeRejected("INVALID_PINNED_SOURCE_SIZE")
    if sha256(data).hexdigest() != sha:
        raise BridgeRejected("PINNED_SOURCE_SHA_MISMATCH")
    return data


def _validate_fixture(evidence: object) -> dict:
    if type(evidence) is not dict or set(evidence) != EVIDENCE_FIELDS:
        raise BridgeRejected("INVALID_EVIDENCE_SCHEMA")
    expected = {
        "tool_id": EVIDENCE_TOOL_ID,
        "capability": "research.compute",
        "source_file": "fincept-qt/scripts/technicals/volatility_indicators.py",
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "source_id": "TOOL01_DETERMINISTIC_SYNTHETIC_V1",
        "dataset_class": "SYNTHETIC_FIXTURE",
        "input_sha256": EXPECTED_INPUT_SHA256,
        "bar_count": 120,
        "observed_at": "2024-04-29T00:00:00Z",
        "available_at": "2024-04-29T00:00:00Z",
        "received_at": "NOT_APPLICABLE_OFFLINE_FIXTURE",
        "rights": "FIXTURE_ONLY",
        "scientific_status": "NOT_EVALUATED",
        "broker_authority": False,
    }
    for key, value in expected.items():
        if type(evidence[key]) is not type(value) or evidence[key] != value:
            raise BridgeRejected("INVALID_FIXTURE_FIELD:" + key)
    cost = evidence["cost"]
    if (type(cost) is not dict or set(cost) != {"external_api_calls", "provider_credits"} or
            type(cost["external_api_calls"]) is not int or cost["external_api_calls"] != 0 or
            type(cost["provider_credits"]) is not int or cost["provider_credits"] != 0):
        raise BridgeRejected("NONZERO_OR_INVALID_COST")
    flags = evidence["quality_flags"]
    if type(flags) is not list or flags != list(REQUIRED_QUALITY):
        raise BridgeRejected("INVALID_QUALITY_FLAGS")
    result = evidence["result"]
    if type(result) is not dict or set(result) != set(EXPECTED_VALUE):
        raise BridgeRejected("INVALID_INDICATOR_SCHEMA")
    for k, expected_value in EXPECTED_VALUE.items():
        v = result[k]
        if type(v) not in (int, float) or not math.isfinite(v):
            raise BridgeRejected("NONFINITE_OR_INVALID_INDICATOR:" + k)
        # The input fixture, Fincept source, and executable harness are pinned.
        # A different numerical answer is NOT an accepted research finding.
        if not math.isclose(v, expected_value, rel_tol=1e-8, abs_tol=1e-9):
            raise BridgeRejected("FIXTURE_NUMERICAL_DRIFT:" + k)
    return evidence


def _parse_stdout(stdout: str) -> dict:
    if len(stdout.encode("utf-8")) > MAX_EVIDENCE_BYTES:
        raise BridgeRejected("OVERSIZE_FIXTURE_OUTPUT")
    try:
        data = json.loads(stdout, parse_constant=lambda _: (_ for _ in ()).throw(BridgeRejected("JSON_NAN")))
    except (ValueError, TypeError) as exc:
        raise BridgeRejected("INVALID_FIXTURE_JSON") from exc
    return _validate_fixture(data)


def reject_on_policy(principal: str, requested_tool: str, request: object = None) -> None:
    """Authorize before touching the filesystem or starting the subprocess."""
    if requested_tool != POLICY_TOOL:
        raise BridgeRejected("TOOL_MAPPING_NOT_ALLOWLISTED")
    # This imports the existing policy from draft #16 instead of cloning it.
    verdict = authorize(principal, POLICY_TOOL, request=request)
    if not verdict.allowed:
        raise BridgeRejected("POLICY_DENIED:" + verdict.code)


def run_fixture(principal: str, requested_tool: str, source: Path, harness: Path,
                *, request: object = None) -> dict:
    """An offline toy-identity test, NEVER an agent-facing authenticated API."""
    reject_on_policy(principal, requested_tool, request=request)
    source_bytes = _read_pinned(Path(source), "volatility_indicators.py",
                                EXPECTED_SOURCE_SHA256, MAX_SOURCE_BYTES)
    harness_bytes = _read_pinned(Path(harness), "fincept_volatility_fixture.py",
                                 EXPECTED_RUNNER_SHA256, MAX_RUNNER_BYTES)
    # Staging avoids hash-check / executable-content TOCTOU on the supplied files.
    with tempfile.TemporaryDirectory(prefix="kairos-fincept-readonly-v1-") as tmp:
        scratch = Path(tmp)
        source_copy = scratch / "volatility_indicators.py"
        runner_copy = scratch / "fincept_volatility_fixture.py"
        source_copy.write_bytes(source_bytes)
        runner_copy.write_bytes(harness_bytes)
        source_copy.chmod(0o600)
        runner_copy.chmod(0o600)
        # Keep credentials and Python injection variables OUT of subprocess env.
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": tmp,
            "LANG": "C.UTF-8",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        # Python -I excludes user-site packages. The audited Mac Fincept
        # dependencies live there: opt in to ONLY that locally discovered path
        # without .pth execution or inherited PYTHONPATH. This is NOT a
        # dependency sandbox/attestation and must not serve untrusted agents.
        dependency_site = site.getusersitepackages()
        entrypoint = (
            "import runpy,sys; site_path,runner,*args=sys.argv[1:];"
            "sys.path.append(site_path);sys.argv=[runner,*args];"
            "runpy.run_path(runner,run_name='__main__')"
        )
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", entrypoint, dependency_site,
                 str(runner_copy), "--module-file", str(source_copy)],
                cwd=tmp, env=env, timeout=RUN_TIMEOUT_SECONDS, text=True,
                capture_output=True, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BridgeRejected("PINNED_TOOL_UNAVAILABLE_OR_TIMEOUT") from exc
        if proc.returncode != 0:
            # Do not leak stderr or filesystem details into bridge/LLM output.
            raise BridgeRejected("PINNED_TOOL_FAILED")
        data = _parse_stdout(proc.stdout)

    digest = sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "fincept_kairos_readonly_bridge_v1",
        "kind": "SYNTHETIC_RESEARCH_INPUT_ONLY",
        "transport": "OFFLINE_LOCAL_PROOF",
        "policy": {
            "tool": POLICY_TOOL,
            "policy_verdict": "ALLOW_LOCAL_FIXTURE_ONLY",
            "principal_is_authenticated": False,
        },
        "provenance": {
            "fincept_module_sha256": EXPECTED_SOURCE_SHA256,
            "fixture_runner_sha256": EXPECTED_RUNNER_SHA256,
            "fixture_input_sha256": EXPECTED_INPUT_SHA256,
            "fixture_evidence_sha256": digest,
            "source_id": data["source_id"],
            "rights": "FIXTURE_ONLY",
            "observed_at": data["observed_at"],
            "available_at": data["available_at"],
            "received_at": data["received_at"],
            "bar_count": data["bar_count"],
        },
        "values": dict(data["result"]),
        "quality_flags": list(REQUIRED_QUALITY),
        "safety": {
            "scientific_status": "NOT_EVALUATED",
            "kairos_gate_status": "NOT_RUN",
            "broker_authority": False,
            "trading_authority": False,
            "market_data_entitlement": "FIXTURE_ONLY",
            "external_api_calls": 0,
            "provider_credits": 0,
            "live_data": False,
        },
        "verdict": "RESEARCH_INPUT_ONLY_NOT_SCIENTIFICALLY_ACCEPTED",
    }


def write_optional_report(path: Path, envelope: dict) -> None:
    """Explicit local output only. No Fincept profile, database or service edits."""
    path = Path(path)
    parent = path.parent
    if (not parent.is_dir() or parent.is_symlink() or path.is_symlink() or
            (path.exists() and not path.is_file())):
        raise BridgeRejected("UNSAFE_REPORT_DESTINATION")
    data = (json.dumps(envelope, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    if len(data) > MAX_EVIDENCE_BYTES:
        raise BridgeRejected("OVERSIZE_BRIDGE_REPORT")
    fd, temp_name = tempfile.mkstemp(dir=parent, prefix=".fincept-kairos-v1-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if path.is_symlink():
            raise BridgeRejected("UNSAFE_REPORT_DESTINATION")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="OFFLINE synthetic-only Fincept -> KAIROS bridge")
    parser.add_argument("--principal", default="synthetic-researcher",
                        help="LOCAL TOY TEST principal, NOT an authenticated user")
    parser.add_argument("--tool", default=POLICY_TOOL)
    parser.add_argument("--fincept-module", required=True, type=Path)
    parser.add_argument("--fixture-runner", required=True, type=Path,
                        help="Exact unmerged TOOL-01 PR #15 harness (SHA pinned)")
    parser.add_argument("--out", type=Path, help="Optional local file, existing directory required")
    args = parser.parse_args()
    try:
        result = run_fixture(args.principal, args.tool, args.fincept_module, args.fixture_runner)
        if args.out:
            write_optional_report(args.out, result)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except BridgeRejected as exc:
        print(json.dumps({"schema": "fincept_kairos_readonly_bridge_v1",
                          "status": "REJECTED", "reason": str(exc),
                          "scientific_status": "NOT_EVALUATED",
                          "broker_authority": False, "trading_authority": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
