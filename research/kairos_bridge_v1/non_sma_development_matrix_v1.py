"""Fixed non-SMA development compatibility matrix, not a strategy selector.

Same previously observed SPY snapshot, separate frozen manifest. No arbitrary
strategy, asset, data, code, optimization or authority is accepted.
"""
from datetime import datetime, timezone
from fractions import Fraction
import json
from pathlib import Path
import sys

from research.kairos_bridge_v1 import development_backtest_v1 as dev
from tools.fincept_audit import backtest_provider_probe_v1 as probe
from tools.fincept_audit import non_sma_signal_oracle_v1 as oracle
from tools.fincept_audit import backtest_metrics_oracle_v1 as metrics

SCHEMA = "FINCEPT_SPY_NON_SMA_DEVELOPMENT_MATRIX_V1"
MANIFEST_SHA256 = "a2e4a399bc9acb540b4c155e05bb4a0cdc7a2341b4a9ebc70b43d81421d7b127"
MANIFEST = Path(__file__).with_suffix(".json")
MAX_MANIFEST = 4096


def admit_manifest(raw):
    dev.require(type(raw) is bytes and 0 < len(raw) <= MAX_MANIFEST
                and dev.digest(raw) == MANIFEST_SHA256)
    doc = json.loads(raw, object_pairs_hook=dev.unique, parse_constant=dev.constant)
    dev.require(doc["schema"] == SCHEMA and doc["snapshot_sha256"] == dev.SNAPSHOT_SHA256
                and doc["dataset_class"] == "DEVELOPMENT_CONTAMINATED"
                and doc["dataset_already_observed"] is True
                and all(doc[k] is False for k in ("selection_authorized", "scientific_claim",
                                                  "execution_authority", "costs_verified")))
    dev.require(doc["cases"] == [
        {"id":"momentum_20","kind":"momentum","params":{"lookback":20,"threshold":0}},
        {"id":"breakout_20","kind":"breakout","params":{"period":20}},
        {"id":"mean_reversion_20","kind":"mean_reversion","params":{"period":20,"zThreshold":2}}])
    dev.require((doc["initial_capital"],doc["commission"],doc["slippage"],doc["execution"])
                == ("100000","0.001","0.0005","next_open"))
    return doc


def _case(candles, case, plan):
    expected = oracle.simulate_fixed(candles, case["kind"])
    for t in expected["trades"]:
        t["symbol"] = "SPY"
    req = probe.build_request(candles, {"fast":5,"slow":20,
        **{k:plan[k] for k in ("initial_capital","commission","slippage","execution")}})
    req["strategy"] = {"type":case["kind"],"params":case["params"]}
    req["symbols"] = ["SPY"]
    req["brokerCandles"] = {"SPY":req["brokerCandles"].pop(probe.SYMBOL)}
    req["brokerDataSource"] = "YAHOO_ADJUSTED_RETROSPECTIVE_DEVELOPMENT_ONLY"
    req["startDate"] = datetime.fromtimestamp(candles[0]["t"],timezone.utc).date().isoformat()
    req["endDate"] = datetime.fromtimestamp(candles[-1]["t"]+86400,timezone.utc).date().isoformat()
    root = Path(__file__).resolve().parents[2]/probe.BACKTESTING_RELATIVE
    run = probe.run_original_provider(root,req)
    dev.require(type(run["network_attempts"]) is int and run["network_attempts"] == 0)
    labels = probe.compare(run["response"],expected)
    dev.require(labels["provider_data_source"] == req["brokerDataSource"]
                and labels["provider_using_synthetic_data"] is False)
    measured = metrics.metrics(expected["equity"],expected["trades"],Fraction(100000),252,Fraction(0))
    probe.compare_metrics(run["response"],measured)
    return {"case":case["id"],"status":"MATCHED_ORACLE","request_sha256":dev.digest(dev.canonical(req)),
            "trades":len(expected["trades"]),"return":float(expected["total_return"]),
            "final_capital":float(expected["final_capital"]),"commission":float(expected["total_fees"]),
            "drawdown":float(measured["max_drawdown"]),"network_attempts":0}


def run_matrix(raw, *, manifest):
    plan = admit_manifest(manifest)
    candles = dev.admit(raw)
    dev.require(len(candles) == 128)
    results = []
    for case in plan["cases"]:
        try:
            row = _case(candles,case,plan)
            dev.require(row["case"] == case["id"] and row["status"] == "MATCHED_ORACLE")
            dev.canonical(row)
        except Exception:
            row = {"case":case["id"],"status":"REJECTED_OR_UNAVAILABLE"}
        results.append(row)
    matched = sum(r["status"] == "MATCHED_ORACLE" for r in results)
    body = {"schema":SCHEMA,"manifest_sha256":MANIFEST_SHA256,"snapshot_sha256":dev.SNAPSHOT_SHA256,
            "dataset_class":"DEVELOPMENT_CONTAMINATED","attempted":len(results),"matched":matched,
            "rejected":len(results)-matched,"status":"COMPLETE" if matched == len(results) else "COMPLETE_WITH_REJECTIONS",
            "results":results,"selection_authorized":False,"scientific_claim":False,"costs_verified":False,
            "market_as_of_verified":False,"execution_authority":False,"promotion_eligible":False,"broker_calls":0}
    return {**body,"receipt_sha256":dev.digest(dev.canonical(body))}


def main():
    if sys.argv[1:] != ["--fixed-non-sma-matrix"]:
        return 2
    try:
        with MANIFEST.open("rb") as f:
            manifest = f.read(MAX_MANIFEST+1)
        result = run_matrix(sys.stdin.buffer.read(dev.MAX_BYTES+1),manifest=manifest)
        sys.stdout.buffer.write(dev.canonical(result)+b"\n")
        return 3 if result["rejected"] else 0
    except Exception:
        print("NON_SMA_MATRIX_UNAVAILABLE",file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
