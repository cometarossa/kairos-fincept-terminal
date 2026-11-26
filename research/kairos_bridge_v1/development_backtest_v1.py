"""One pinned public retrospective SPY development diagnostic, NOT trading.

Caller supplies the exact cached envelope bytes, never a path, prices, strategy
parameters or credentials. The caller must admit the dataset as DEVELOPMENT
ONLY and run in an isolated offline laboratory. No PIT or scientific claim.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys

from tools.fincept_audit import backtest_provider_probe_v1 as probe
from tools.fincept_audit import backtest_oracle_v1 as oracle
from tools.fincept_audit import backtest_metrics_oracle_v1 as metrics

SCOPE = "FINCEPT_SPY_DEVELOPMENT_DIAGNOSTIC_V1"
SNAPSHOT_SHA256 = "54d8a241d888969a94bc3c811905f9f09d31dda1d6afd9c4c95d647197dd6663"
BARS_SHA256 = "3a603e78bf67c345d38f96368830a0d232fc47d00fdd17c79da7f8acb30b4e87"
CAPTURED = 1795706381
MAX_BYTES = 100000
REQUEST_SHA256 = "62cc8f62d791b9fb186531973312345bb6f6b62262ebc609a5aa7c371a54a85d"
SUMMARY_SHA256 = "bc194974938bebae3f6b1a7197a93e404690df7c9f48500e36b3797ed05e4151"


class DevelopmentDenied(ValueError):
    """No usable development evidence."""


def require(ok):
    if not ok:
        raise DevelopmentDenied("DEVELOPMENT_REPLAY_DENIED")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    out = {}
    for k, v in pairs:
        require(k not in out)
        out[k] = v
    return out


def constant(_):
    raise DevelopmentDenied("NONFINITE_JSON")


def admit(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES
            and digest(raw) == SNAPSHOT_SHA256)
    e = json.loads(raw, object_pairs_hook=unique, parse_constant=constant)
    require(type(e) is dict and set(e) == {
        "schema", "provider", "symbol", "period", "interval", "adjustment",
        "captured_at_unix", "bars_sha256", "bars_base64"})
    require(e["schema"] == "YAHOO_HISTORY_SNAPSHOT_V1"
            and e["provider"] == "Yahoo Finance via original yfinance"
            and e["symbol"] == "SPY" and e["period"] == "6mo"
            and e["interval"] == "1d"
            and e["adjustment"] == "AUTO_ADJUST_TRUE_BACK_ADJUST_FALSE"
            and type(e["captured_at_unix"]) is int and e["captured_at_unix"] == CAPTURED)
    b = base64.b64decode(e["bars_base64"], validate=True)
    require(digest(b) == e["bars_sha256"] == BARS_SHA256)
    rows = json.loads(b, object_pairs_hook=unique, parse_constant=constant)
    require(type(rows) is list and len(rows) == 129)
    candles, last = [], 0
    for row in rows:
        require(type(row) is dict and set(row) == {"timestamp", "open", "high", "low", "close", "volume"})
        ts = row["timestamp"]
        require(type(ts) is int and ts > last and ts % 3600 == 0)
        last = ts
        require(all(type(row[k]) in (int, float) and math.isfinite(row[k]) and row[k] > 0
                    for k in ("open", "high", "low", "close")))
        require(row["low"] <= min(row["open"], row["close"]) <= max(row["open"], row["close"]) <= row["high"])
        require(type(row["volume"]) is int and row["volume"] >= 0)
        day = ts // 86400 * 86400
        require((not candles or day > candles[-1]["t"]) and day + 86400 <= CAPTURED)
        c = {"t": day, "v": row["volume"]}
        c.update({k: str(row[n]) for k, n in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close"))})
        candles.append(c)
    return candles[:-1]


def run_development(raw, *, scope):
    # This is not an extension of the synthetic fixture authority.
    require(type(scope) is str and scope == SCOPE)
    candles = admit(raw)
    require(len(candles) == 128)
    scenario = {"name": "fixed_5_20_development_diagnostic", "fast": 5, "slow": 20,
                "initial_capital": "100000", "commission": "0.001",
                "slippage": "0.0005", "execution": "next_open"}
    expected = oracle.simulate(candles, fast=5, slow=20, initial_capital="100000",
                               commission="0.001", slippage="0.0005", execution="next_open")
    for t in expected["trades"]:
        t["symbol"] = "SPY"
    req = probe.build_request(candles, scenario)
    req["symbols"] = ["SPY"]
    req["brokerCandles"] = {"SPY": req["brokerCandles"].pop(probe.SYMBOL)}
    req["brokerDataSource"] = "YAHOO_ADJUSTED_RETROSPECTIVE_DEVELOPMENT_ONLY"
    req["startDate"] = datetime.fromtimestamp(candles[0]["t"], timezone.utc).date().isoformat()
    req["endDate"] = datetime.fromtimestamp(candles[-1]["t"] + 86400, timezone.utc).date().isoformat()
    require(digest(canonical(req)) == REQUEST_SHA256)
    root = Path(__file__).resolve().parents[2] / probe.BACKTESTING_RELATIVE
    run = probe.run_original_provider(root, req)
    require(type(run["network_attempts"]) is int and run["network_attempts"] == 0)
    labels = probe.compare(run["response"], expected)
    require(labels["provider_data_source"] == req["brokerDataSource"]
            and labels["provider_using_synthetic_data"] is False)
    measured = metrics.metrics(expected["equity"], expected["trades"], Fraction(100000), 252, Fraction(0))
    probe.compare_metrics(run["response"], measured)
    capital, fee, slip = Fraction(100000), Fraction("0.001"), Fraction("0.0005")
    qty = capital / (Fraction(candles[0]["o"]) * (1 + slip) * (1 + fee))
    benchmark = qty * Fraction(candles[-1]["c"]) * (1 - slip) * (1 - fee) / capital - 1
    summary = {"status": "DEVELOPMENT_DIAGNOSTIC_ONLY", "market_as_of_verified": False,
               "scientific_claim": False, "promotion_eligible": False, "execution_authority": False,
               "broker_calls": 0, "snapshot_sha256": SNAPSHOT_SHA256, "bars": len(candles),
               "first": req["startDate"], "last": datetime.fromtimestamp(candles[-1]["t"], timezone.utc).date().isoformat(),
               "trades": len(expected["trades"]), "entry_signals": expected["entry_signals"],
               "exit_signals": expected["exit_signals"], "final_capital": float(expected["final_capital"]),
               "commission": float(expected["total_fees"]), "return": float(expected["total_return"]),
               "drawdown": float(measured["max_drawdown"]), "benchmark_return": float(benchmark),
               "forced_exit": any(t["exit_reason"] == "end_of_data" for t in expected["trades"]),
               "network_attempts": run["network_attempts"], "provider_oracle_match": True, "parameters": scenario}
    require(digest(canonical(summary)) == SUMMARY_SHA256)
    return {"schema": SCOPE, "dataset_class": "DEVELOPMENT_CONTAMINATED",
            "historical_publication_verified": False, "costs_verified": False,
            "out_of_sample_certified": False, "summary_sha256": SUMMARY_SHA256,
            "summary": summary}


def main():
    if sys.argv[1:] != ["--fixed-development-replay"]:
        print("DEVELOPMENT_REPLAY_DENIED", file=sys.stderr)
        return 2
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        result = run_development(raw, scope=SCOPE)
        sys.stdout.buffer.write(canonical(result) + b"\n")
        return 0
    except Exception:
        print("DEVELOPMENT_REPLAY_UNAVAILABLE", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
