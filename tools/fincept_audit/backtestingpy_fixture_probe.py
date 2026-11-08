#!/usr/bin/env python3
"""Offline fixture-only functional probe for installed Fincept Backtesting.py.

Executes the REAL installed Fincept provider, but overrides only its data loader
with a fixed, reproducible OHLCV DataFrame. The override is TEST-ONLY and does
not establish an external data adapter for this provider.

Run only with the supplied offline Python socket guard on PYTHONPATH:
PYTHONPATH=/path/to/offline_netguard:/path/to/Fincept/scripts \
 venv-numpy1/bin/python backtestingpy_fixture_probe.py --scripts-root /path/to/Fincept/scripts

No broker, paid provider, user secrets, or trading operations.
No performance results from these fabricated candles have financial meaning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import socket
import sys


def _check_network_guard() -> None:
    # Introspection only: never attempt a socket connection in a diagnostic.
    try:
        import sitecustomize
        if (socket.create_connection is sitecustomize._block
                and socket.socket.connect is sitecustomize._block):
            return
    except (ImportError, AttributeError):
        pass
    raise SystemExit("STOP: offline network-deny guard not active")


def fixture():
    import pandas as pd

    dates = pd.bdate_range("2024-01-01", periods=260, tz=None)
    rows = []
    for i in range(len(dates)):
        # Slow cycle plus bounded trend, guaranteeing multiple MA crossovers.
        px = 100 + 0.025 * i + 9 * math.sin(i / 7)
        opn = px - 0.15
        rows.append((
            round(opn, 4),
            round(max(px, opn) + 1.0, 4),
            round(min(px, opn) - 1.0, 4),
            round(px, 4),
            1000 + i,
        ))
    return pd.DataFrame(
        rows, index=dates, columns=["Open", "High", "Low", "Close", "Volume"]
    )


def _run(provider, data, commission, slippage):
    provider._allow_synthetic = False
    provider._last_load_was_real = False

    # This is not an implemented public extension of Backtesting.py provider.
    # It deliberately tests the existing computation independently of Yahoo.
    def _load_data(symbol, _start, _end, _interval="1d"):
        if symbol != "KAIROS_FIXTURE":
            raise ValueError("Synthetic audit permits only KAIROS_FIXTURE")
        return data.copy()

    provider._load_data = _load_data
    result = provider.run_backtest({
        "symbols": ["KAIROS_FIXTURE"],
        "startDate": "2024-01-01",
        "endDate": "2025-01-01",
        "initialCapital": 100000,
        "interval": "1d",
        "strategy": {"type": "sma_crossover", "params": {"fastPeriod": 5, "slowPeriod": 20}},
        "commission": commission,
        "slippage": slippage,
        "leverage": 1.0,
        "benchmarkSymbol": "",
    })
    if not isinstance(result, dict) or result.get("success") is not True:
        reason = str(result.get("error", "provider_declined")) if isinstance(result, dict) else "invalid_json"
        raise RuntimeError("Provider functional FAIL: " + reason[:220])
    payload = result.get("data", {})
    if not isinstance(payload, dict):
        raise RuntimeError("Provider returned invalid data payload")
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scripts-root", type=Path, required=True)
    args = parser.parse_args()
    _check_network_guard()

    scripts = args.scripts_root.resolve(strict=True)
    source = scripts / "Analytics/backtesting/backtestingpy/backtestingpy_provider.py"
    if not source.is_file():
        raise SystemExit("STOP: installed provider not found")
    sys.path.insert(0, str(source.parent))
    sys.path.insert(0, str(source.parent.parent))

    from backtestingpy_provider import BacktestingPyProvider  # noqa: PLC0415

    data = fixture()
    if data.isna().any().any() or not all(
        (data["High"] >= data[["Open", "Close", "Low"]].max(axis=1))
        & (data["Low"] <= data[["Open", "Close", "High"]].min(axis=1))
    ):
        raise SystemExit("STOP: malformed fixture OHLCV")

    hash_input = data.to_csv(index=True, float_format="%.4f").encode("utf-8")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    baseline = _run(BacktestingPyProvider(), data, 0.0, 0.0)
    with_costs = _run(BacktestingPyProvider(), data, 0.001, 0.0005)

    def read(payload):
        performance = payload.get("performance", {})
        stats = payload.get("statistics", {})
        if not isinstance(performance, dict) or not isinstance(stats, dict):
            raise RuntimeError("No performance/statistics in computed payload")
        value = stats.get("final_capital", stats.get("finalCapital"))
        count = performance.get("total_trades", performance.get("totalTrades"))
        if value is None or count is None:
            raise RuntimeError("Missing trade count or final capital")
        return float(value), int(count)

    baseline_value, baseline_trades = read(baseline)
    costs_value, costs_trades = read(with_costs)
    if baseline_trades < 1 or costs_trades < 1:
        raise RuntimeError("Fixture generated no trades, cannot test transaction costs")
    if not math.isfinite(baseline_value) or not math.isfinite(costs_value):
        raise RuntimeError("Non-finite equity value")
    if costs_value >= baseline_value:
        raise RuntimeError("Costs did not reduce final capital on fixed fixture")

    report = {
        "category": "OFFLINE_SYNTHETIC_FIXTURE_ONLY",
        "provider": "backtestingpy",
        "provider_computation": "PASS",
        "network_guard": "PASS",
        "market_data": "NONE",
        "broker_authority": False,
        "synthetic_fixture_bars": len(data),
        "fixture_sha256": hashlib.sha256(hash_input).hexdigest(),
        "installed_provider_source_sha256": source_hash,
        "baseline_trade_count": baseline_trades,
        "with_costs_trade_count": costs_trades,
        "transaction_cost_sensitivity": "PASS",
        "scientific_status": "NOT_EVALUATED",
        "bridge_status": "PRIVATE_TEST_LOADER_OVERRIDE_ONLY",
        "no_alpha_claim": True,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
