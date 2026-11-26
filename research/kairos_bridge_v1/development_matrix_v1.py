"""Bounded public-SPY development compatibility matrix; not a strategy selector.

The manifest was frozen on GitHub before these three executions. This is a
previously observed development dataset, not an independent preregistration.
Do not pass these results to E0 as generated hypotheses or scientific trials.
"""
from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

from research.kairos_bridge_v1 import development_backtest_v1 as dev
from tools.fincept_audit import backtest_provider_probe_v1 as probe
from tools.fincept_audit import backtest_oracle_v1 as oracle
from tools.fincept_audit import backtest_metrics_oracle_v1 as metrics

SCHEMA = "FINCEPT_SPY_DEVELOPMENT_MATRIX_V1"
MANIFEST_SHA256 = "030ef8061f6af5aa3692845ed4dd008224fd3293ead7469cfccbb3ffe92b5d15"
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
        {"id": "sma_5_20", "fast": 5, "slow": 20},
        {"id": "sma_10_30", "fast": 10, "slow": 30},
        {"id": "sma_20_50", "fast": 20, "slow": 50}])
    return doc


def _case(candles, case, plan):
    params = {"fast": case["fast"], "slow": case["slow"],
              **{k: plan[k] for k in ("initial_capital", "commission", "slippage", "execution")}}
    scenario = {"name": case["id"], **params}
    expected = oracle.simulate(candles, **params)
    for t in expected["trades"]:
        t["symbol"] = "SPY"
    req = probe.build_request(candles, scenario)
    req["symbols"] = ["SPY"]
    req["brokerCandles"] = {"SPY": req["brokerCandles"].pop(probe.SYMBOL)}
    req["brokerDataSource"] = "YAHOO_ADJUSTED_RETROSPECTIVE_DEVELOPMENT_ONLY"
    req["startDate"] = datetime.fromtimestamp(candles[0]["t"], timezone.utc).date().isoformat()
    req["endDate"] = datetime.fromtimestamp(candles[-1]["t"] + 86400, timezone.utc).date().isoformat()
    root = Path(__file__).resolve().parents[2] / probe.BACKTESTING_RELATIVE
    run = probe.run_original_provider(root, req)
    dev.require(type(run["network_attempts"]) is int and run["network_attempts"] == 0)
    labels = probe.compare(run["response"], expected)
    dev.require(labels["provider_data_source"] == req["brokerDataSource"]
                and labels["provider_using_synthetic_data"] is False)
    measured = metrics.metrics(expected["equity"], expected["trades"],
                               Fraction(plan["initial_capital"]), 252, Fraction(0))
    probe.compare_metrics(run["response"], measured)
    return {"case": case["id"], "status": "MATCHED_ORACLE", "request_sha256": dev.digest(dev.canonical(req)),
            "trades": len(expected["trades"]), "return": float(expected["total_return"]),
            "final_capital": float(expected["final_capital"]), "commission": float(expected["total_fees"]),
            "drawdown": float(measured["max_drawdown"]), "network_attempts": 0}


def run_matrix(raw, *, manifest):
    # Both immutable input commitments must match before invoking anything.
    plan = admit_manifest(manifest)
    candles = dev.admit(raw)
    dev.require(len(candles) == 128)
    results = []
    for case in plan["cases"]:
        try:
            result = _case(candles, case, plan)
            dev.require(result["case"] == case["id"] and result["status"] == "MATCHED_ORACLE")
            dev.canonical(result)  # refuses nonfinite results
        except Exception:
            # All planned attempts are represented, including rejected ones;
            # never emit exception text, synthetic replacement metrics or rank.
            result = {"case": case["id"], "status": "REJECTED_OR_UNAVAILABLE"}
        results.append(result)
    matched = sum(r["status"] == "MATCHED_ORACLE" for r in results)
    body = {"schema": SCHEMA, "manifest_sha256": MANIFEST_SHA256,
            "snapshot_sha256": dev.SNAPSHOT_SHA256, "dataset_class": "DEVELOPMENT_CONTAMINATED",
            "attempted": len(results), "matched": matched, "rejected": len(results)-matched,
            "status": "COMPLETE" if matched == len(results) else "COMPLETE_WITH_REJECTIONS",
            "results": results, "selection_authorized": False, "scientific_claim": False,
            "costs_verified": False, "market_as_of_verified": False,
            "execution_authority": False, "promotion_eligible": False, "broker_calls": 0}
    return {**body, "receipt_sha256": dev.digest(dev.canonical(body))}


def main():
    if sys.argv[1:] != ["--fixed-matrix"]:
        return 2
    try:
        with MANIFEST.open("rb") as f:
            manifest = f.read(MAX_MANIFEST + 1)
        result = run_matrix(sys.stdin.buffer.read(dev.MAX_BYTES + 1), manifest=manifest)
        sys.stdout.buffer.write(dev.canonical(result) + b"\n")
        return 0 if result["rejected"] == 0 else 3
    except Exception:
        print("DEVELOPMENT_MATRIX_UNAVAILABLE", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
