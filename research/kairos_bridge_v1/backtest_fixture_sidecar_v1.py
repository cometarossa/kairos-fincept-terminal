"""Offline fixed synthetic Fincept backtest capability; not an authenticated API."""
from pathlib import Path
import json
import sys
from tools.fincept_authority.server_policy import authorize

TOOL = "quant.backtest.read"
SCENARIO = "multi_asset_75_25"
SCOPE = "FINCEPT_SYNTHETIC_BACKTEST_FIXTURE_V1"

class BacktestDenied(ValueError):
    pass

def run_fixture(principal, tool, request):
    # No caller-supplied paths, strategy code, prices, parameters or authority.
    if (type(principal) is not str or type(tool) is not str or tool != TOOL
            or type(request) is not dict or set(request) != {"scope"}
            or type(request["scope"]) is not str or request["scope"] != SCOPE):
        raise BacktestDenied("BACKTEST_REQUEST_DENIED")
    if not authorize(principal, TOOL, request=request).allowed:
        raise BacktestDenied("BACKTEST_POLICY_DENIED")
    from tools.fincept_audit import backtest_provider_probe_v1 as probe
    from tools.fincept_audit import backtest_evidence_v1 as evidence
    root = Path(__file__).resolve().parents[2]
    selected = [s for s in probe.multi_asset_scenarios() if s["name"] == SCENARIO]
    if len(selected) != 1:
        raise BacktestDenied("BACKTEST_SCENARIO_DENIED")
    result = probe.run_multi_asset_scenario(root / probe.BACKTESTING_RELATIVE, selected[0])
    if result["scenario"] != SCENARIO or result["network_attempts_denied"] != 0:
        raise BacktestDenied("BACKTEST_RESULT_DENIED")
    envelope = evidence.build({"schema": probe.SCHEMA, "scenarios": [result]})
    return evidence.loads(evidence.canonical(envelope).decode("utf-8"))

def main():
    # Fixed local laboratory call. The principal is NOT an authenticated identity.
    if sys.argv[1:] != ["--fixed-fixture"]:
        print("BACKTEST_REQUEST_DENIED", file=sys.stderr)
        return 2
    try:
        result = run_fixture("synthetic-researcher", TOOL, {"scope": SCOPE})
        print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return 0
    except Exception:
        print("BACKTEST_UNAVAILABLE", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
