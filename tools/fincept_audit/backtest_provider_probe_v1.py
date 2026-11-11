"""Run the ORIGINAL Fincept VectorBT provider offline and check it against an oracle.

What runs: the unmodified `vectorbt_provider.py` through the same CLI contract
the Qt host uses (`run_backtest --stdin`), in a child interpreter, on synthetic
candles passed through the provider's own `brokerCandles` input. The result is
compared bar by bar and trade by trade with `backtest_oracle_v1`, which is
exact rational arithmetic written from the provider's stated execution model.

What this is NOT: a Qt/GUI test, a market-data test, an estimate of edge, a
sandbox, or a signal source. The provider labels injected candles as broker
data (`usingSyntheticData=false`); this probe therefore stamps its own
`SYNTHETIC_FIXTURE_NOT_MARKET_DATA` label and never forwards the provider's.

Isolation, as far as a Python-level harness can give it:
  * every repository file the child imports must be in PINNED_SOURCES and hash
    to the value recorded from fork main 7716ee86; hashes are checked before
    and after the run, and the child reports what it actually loaded;
  * the child runs with `-I -B` and an empty `pycache_prefix`, so a stale
    `.pyc` next to a source cannot replace it and nothing is written back;
  * Python socket connections are denied and counted inside the child;
  * the child gets a minimal environment and an empty working directory.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

try:  # package import (tests) or direct script execution
    from tools.fincept_audit import backtest_oracle_v1 as oracle
    from tools.fincept_audit import backtest_metrics_oracle_v1 as metrics_oracle
except ImportError:  # pragma: no cover - direct execution
    import backtest_oracle_v1 as oracle
    import backtest_metrics_oracle_v1 as metrics_oracle

SCHEMA = "kairos_fincept_backtest_provider_probe_v1"
BACKTESTING_RELATIVE = "fincept-qt/scripts/Analytics/backtesting"
PROVIDER_RELATIVE = "vectorbt/vectorbt_provider.py"
# sha256 of the ORIGINAL files on fork main 7716ee8613249fb44c4d14036c5bc16ed6f34e97.
PINNED_SOURCES = {
    "vectorbt/vectorbt_provider.py": "1d6c338fa49772bd4a3d9a86fde1e9be1c389a471706ae9b6604f5354ef8b703",
    "vectorbt/vbt_portfolio.py": "ce9fd43e9a27be55d440d36e06ac6f19204400a2b83bca71876ca48952cd65cf",
    "vectorbt/vbt_strategies.py": "c94ae482e8933b1fc967347c8512e388e795ec5ebf8f7e405dc03c261841071c",
    "vectorbt/vbt_indicators.py": "28d6b6efe22e0947067d580159b05627cf75ed75aaa45acdf8bebe18f3c76b87",
    "vectorbt/vbt_metrics.py": "d56d18c157b6e0192c4ef2d9f7224cef31bddd24ecb41caa99fcdf885e8d739d",
    "base/base_provider.py": "cb2f2323ba459607637beab40215b65f820e9b83759c5d98fc8443ab4f5fd153",
    "base/__init__.py": "117ae7fa23328078d50d5809d797dca4c85f8523142aabf251d36078cb30655a",
    "base/advanced_metrics.py": "d368aa7c0160f306cd5d81d1253a37428f452251dbe89ff339f80ecc5b01732c",
    "vectorbt/__init__.py": "e5b6f442fa24df54ba9d4b5340b31f2082eaeb0382a7b7ef292611886dcf6411",
}
# sha256 of the canonical JSON of oracle.synthetic_candles(bars). The fixture is
# built with libm sin(); if a platform rounds a cent differently the run stops
# instead of silently comparing on different data.
FIXTURE_SHA256 = {
    "160": "96228c052d7daeb8da5f079ac1c221c0db4fe7971a25487f6bb3d2f1a7ca1a4e",
    "130": "8d5947c974752a706fc7b47f8cff3884fe886fed580d21ea5658b26935cf04dd",
    "160/shock53x500": "6f9d2f5d04801dc64e160faa0a19ceaa48ce52cdd297538f5e1602bbe0325d46",
    "160/second": "c05a9e363560c2a5fbe78e2e2599291362f168b9a7f743bd81e843bcb034431d",
    "160/weekdays": "11f6b0fdfd4948b527e87e214d403f1180d4ff43747b3928a1dfe33371dc497a",
}
SHOCK = {"bars": 160, "shock_bar": 53, "shock_cents": 500}
WEEKDAYS = {"bars": 160, "weekdays_only": True}
# A second, differently shaped series for multi-asset runs (other level, wave and drift).
SECOND = {"bars": 160, "wave": 4.0, "wave_period": 7.0, "base": 50.0, "drift_cents": 3}
MULTI_SYMBOLS = ("KAIROSSYNA", "KAIROSSYNB")
# Bars per year the provider must infer from the bar spacing, and the text it
# must print in `assumptions.annualization` for it.
ANNUALIZATION_TEXT = {365: "365 bars/year (daily bars, 7-day market)",
                      252: "252 bars/year (daily equity bars)"}
# oracle argument -> provider request key (both are fractions of price)
STOP_KEYS = {"stop_loss": "stopLoss", "take_profit": "takeProfit", "trailing_stop": "trailingStop"}
SYMBOL = "KAIROSSYNTH"
DATA_SOURCE_TAG = "kairos_synthetic_fixture"
REL_TOL = 1e-9
ABS_TOL = 1e-6          # currency amounts around 1e5
RATIO_ABS_TOL = 1e-12   # dimensionless metrics, some as small as 1e-4
TIMEOUT_SECONDS = 120

# Runs inside the child. Denies Python sockets, executes the provider file as
# __main__ and reports the repository modules that were really imported.
_CHILD = r'''
import json, os, runpy, socket, sys
provider, root, report = sys.argv[1], os.path.realpath(sys.argv[2]), sys.argv[3]
attempts = []
def deny(*args, **kwargs):
    attempts.append(1)
    raise OSError("NETWORK_ATTEMPT_DENIED_BY_KAIROS_PROBE")
socket.socket.connect = deny
socket.socket.connect_ex = deny
socket.create_connection = deny
socket.getaddrinfo = deny
sys.argv = [provider, "run_backtest", "--stdin"]
code = 0
try:
    runpy.run_path(provider, run_name="__main__")
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else 1
finally:
    loaded = set()
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path:
            real = os.path.realpath(path)
            if real.startswith(root + os.sep):
                loaded.add(os.path.relpath(real, root).replace(os.sep, "/"))
    loaded.add(os.path.relpath(os.path.realpath(provider), root).replace(os.sep, "/"))
    with open(report, "w", encoding="utf-8") as handle:
        json.dump({"loaded": sorted(loaded), "network_attempts": len(attempts)}, handle)
sys.exit(code)
'''


class ProbeError(ValueError):
    pass


def default_scenarios():
    """Small grid: costs, sizing, both execution modes, and an open final position."""
    return [
        {"name": "next_open_no_costs", "fast": 5, "slow": 20},
        {"name": "next_open_costs", "fast": 5, "slow": 20,
         "commission": "0.001", "slippage": "0.0005"},
        {"name": "next_open_costs_40pct", "fast": 5, "slow": 20,
         "commission": "0.001", "slippage": "0.0005", "sizing_value": "40"},
        {"name": "next_open_fixed_25000", "fast": 3, "slow": 12,
         "commission": "0.0025", "sizing_mode": "fixed", "sizing_value": "25000"},
        {"name": "same_close_costs", "fast": 5, "slow": 20,
         "commission": "0.001", "slippage": "0.0005", "execution": "same_close"},
        {"name": "open_position_at_end", "fast": 5, "slow": 20, "bars": 130,
         "commission": "0.001", "slippage": "0.0005"},
    ]


def stop_scenarios():
    """Stop-loss, take-profit and trailing stop, alone, combined and in both execution modes.

    The shock fixture drops the price by 5.00 two bars after an entry so that a
    3% stop-loss exits four bars before the crossover would.
    """
    costs = {"fast": 5, "slow": 20, "commission": "0.001", "slippage": "0.0005"}
    return [
        dict(costs, name="stop_loss_after_shock", fixture=SHOCK, stop_loss="0.03"),
        dict(costs, name="stop_loss_after_shock_same_close", fixture=SHOCK, stop_loss="0.03",
             execution="same_close"),
        dict(costs, name="take_profit", take_profit="0.03"),
        dict(costs, name="take_profit_60pct", take_profit="0.02", sizing_value="60"),
        dict(costs, name="trailing_stop", trailing_stop="0.01"),
        dict(costs, name="trailing_stop_same_close", trailing_stop="0.01", execution="same_close"),
        dict(costs, name="all_three_after_shock", fixture=SHOCK, stop_loss="0.03",
             take_profit="0.06", trailing_stop="0.04"),
        dict(costs, name="stop_loss_ties_with_signal", stop_loss="0.005"),
    ]


def metric_scenarios():
    """Scenarios added for the metrics block: risk-free rate and a 252-bar year."""
    costs = {"fast": 5, "slow": 20, "commission": "0.001", "slippage": "0.0005"}
    return [
        dict(costs, name="risk_free_4pct", risk_free_rate="0.04"),
        dict(costs, name="weekday_calendar_252", fixture=WEEKDAYS),
        dict(costs, name="weekday_calendar_252_risk_free", fixture=WEEKDAYS, risk_free_rate="0.025"),
    ]


def expected_periods_per_year(scenario: dict) -> int:
    return 252 if (scenario.get("fixture") or {}).get("weekdays_only") else 365


def fixture_for(scenario: dict):
    """Build the scenario's candles and refuse them unless their hash is pinned."""
    spec = dict(scenario.get("fixture") or {"bars": scenario.get("bars", 160)})
    key = str(spec["bars"])
    if spec.get("shock_bar") is not None:
        key += "/shock%dx%d" % (spec["shock_bar"], spec["shock_cents"])
    if spec.get("weekdays_only"):
        key += "/weekdays"
    if "base" in spec:
        key += "/second"
    candles = oracle.synthetic_candles(**spec)
    digest = sha256(json.dumps(candles, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if FIXTURE_SHA256.get(key) != digest:
        raise ProbeError("SYNTHETIC_FIXTURE_DRIFT:" + key)
    return candles


def _verify_sources(backtesting_dir: Path) -> None:
    for relative, expected in PINNED_SOURCES.items():
        path = backtesting_dir / relative
        if path.is_symlink() or not path.is_file():
            raise ProbeError("MISSING_OR_INVALID_PINNED_ORIGINAL:" + relative)
        if sha256(path.read_bytes()).hexdigest() != expected:
            raise ProbeError("CHANGED_ORIGINAL_SOURCE_SHA256:" + relative)


def build_request(candles, scenario: dict) -> dict:
    """The provider's own request shape; prices become floats only here."""
    request = {
        "strategy": {"type": "sma_crossover",
                     "params": {"fastPeriod": scenario["fast"], "slowPeriod": scenario["slow"]}},
        "symbols": [SYMBOL],
        "startDate": "2024-01-01",
        "endDate": "2030-01-01",
        "initialCapital": float(Fraction(scenario.get("initial_capital", "100000"))),
        "commission": float(Fraction(scenario.get("commission", "0"))),
        "slippage": float(Fraction(scenario.get("slippage", "0"))),
        "positionSizing": scenario.get("sizing_mode", "percent"),
        "positionSizeValue": float(Fraction(scenario.get("sizing_value", "100"))),
        "execution": scenario.get("execution", "next_open"),
        **{key: float(Fraction(scenario[name])) for name, key in STOP_KEYS.items()
           if scenario.get(name) is not None},
        **({"riskFreeRate": float(Fraction(scenario["risk_free_rate"]))}
           if scenario.get("risk_free_rate") is not None else {}),
        "brokerDataSource": DATA_SOURCE_TAG,
        "brokerCandles": {SYMBOL: [
            {"t": row["t"], "o": float(row["o"]), "h": float(row["h"]),
             "l": float(row["l"]), "c": float(row["c"]), "v": row["v"]}
            for row in candles]},
    }
    return request


def execute_child(provider: Path, root: Path, request: dict, python: str = sys.executable):
    """Run `provider` as __main__ under the socket guard. Returns (stdout, report)."""
    with tempfile.TemporaryDirectory(prefix="kairos_bt_probe_") as scratch:
        scratch_path = Path(scratch)
        report_path = scratch_path / "loaded.json"
        cache = scratch_path / "pycache"
        cache.mkdir()
        workdir = scratch_path / "cwd"
        workdir.mkdir()
        command = [python, "-I", "-B", "-X", "pycache_prefix=" + str(cache), "-c", _CHILD,
                   str(provider), str(root), str(report_path)]
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(workdir),
               "TMPDIR": str(scratch_path), "PYTHONDONTWRITEBYTECODE": "1",
               "MPLBACKEND": "Agg", "NUMBA_CACHE_DIR": str(scratch_path / "numba")}
        try:
            done = subprocess.run(command, input=json.dumps(request), capture_output=True,
                                  text=True, env=env, cwd=str(workdir), timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            raise ProbeError("ORIGINAL_PROVIDER_TIMEOUT") from exc
        if done.returncode != 0:
            raise ProbeError("ORIGINAL_PROVIDER_EXIT_%d" % done.returncode)
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProbeError("ORIGINAL_PROVIDER_OUTPUT_UNREADABLE") from exc
    return done.stdout, report


def run_original_provider(backtesting_dir: Path, request: dict, python: str = sys.executable) -> dict:
    """Execute the pinned provider in a child interpreter. Returns its JSON and run facts."""
    backtesting_dir = backtesting_dir.resolve()
    _verify_sources(backtesting_dir)
    stdout, report = execute_child(backtesting_dir / PROVIDER_RELATIVE, backtesting_dir, request, python)
    try:
        response = json.loads(stdout)
    except ValueError as exc:
        raise ProbeError("ORIGINAL_PROVIDER_OUTPUT_UNREADABLE") from exc
    # Nothing outside the pinned set may have been imported from the repository,
    # and the pinned files must still be the same bytes after the run.
    unpinned = sorted(set(report.get("loaded", [])) - set(PINNED_SOURCES))
    if unpinned:
        raise ProbeError("UNPINNED_REPOSITORY_MODULE_LOADED:" + ",".join(unpinned))
    _verify_sources(backtesting_dir)
    if not isinstance(response, dict) or response.get("success") is not True:
        raise ProbeError("ORIGINAL_PROVIDER_REPORTED_FAILURE:" +
                         str(response.get("error") if isinstance(response, dict) else "")[:120])
    return {"response": response, "loaded": report["loaded"],
            "network_attempts": int(report.get("network_attempts", -1))}


def _close(observed, expected: Fraction, what: str, abs_tol: float = ABS_TOL) -> None:
    if isinstance(observed, bool) or not isinstance(observed, (int, float)) or not math.isfinite(observed):
        raise ProbeError("NON_FINITE_PROVIDER_VALUE:" + what)
    if not math.isclose(float(observed), float(expected), rel_tol=REL_TOL, abs_tol=abs_tol):
        raise ProbeError("ORACLE_MISMATCH:%s:provider=%r:oracle=%r" % (what, observed, float(expected)))


def _iso_day(epoch: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d")


def compare(response: dict, expected: dict) -> dict:
    """Raise ProbeError on the first difference; return the provider's own labels."""
    data = response.get("data")
    if not isinstance(data, dict):
        raise ProbeError("PROVIDER_DATA_MISSING")
    equity = data.get("equity")
    if not isinstance(equity, list) or len(equity) != expected["bars"]:
        raise ProbeError("EQUITY_LENGTH_MISMATCH")
    for i, (point, value) in enumerate(zip(equity, expected["equity"])):
        if point.get("date") != _iso_day(expected["times"][i]):
            raise ProbeError("EQUITY_DATE_MISMATCH:%d" % i)
        _close(point.get("equity"), value, "equity[%d]" % i)
    trades = data.get("trades")
    if not isinstance(trades, list) or len(trades) != len(expected["trades"]):
        raise ProbeError("TRADE_COUNT_MISMATCH:provider=%s:oracle=%d" % (
            len(trades) if isinstance(trades, list) else "?", len(expected["trades"])))
    for i, (got, want) in enumerate(zip(trades, expected["trades"])):
        if got.get("side") != "long" or got.get("symbol") != want.get("symbol", SYMBOL):
            raise ProbeError("TRADE_IDENTITY_MISMATCH:%d" % i)
        if got.get("entryDate") != _iso_day(want["entry_time"]) or \
                got.get("exitDate") != _iso_day(want["exit_time"]):
            raise ProbeError("TRADE_DATE_MISMATCH:%d" % i)
        if got.get("exitReason") != want["exit_reason"]:
            raise ProbeError("TRADE_EXIT_REASON_MISMATCH:%d" % i)
        _close(got.get("entryPrice"), want["entry_price"], "trade[%d].entryPrice" % i)
        _close(got.get("exitPrice"), want["exit_price"], "trade[%d].exitPrice" % i)
        _close(got.get("quantity"), want["size"], "trade[%d].quantity" % i)
        _close(got.get("pnl"), want["pnl"], "trade[%d].pnl" % i)
        _close(got.get("commission"), want["fees"], "trade[%d].commission" % i)
    statistics = data.get("statistics") or {}
    performance = data.get("performance") or {}
    _close(statistics.get("finalCapital"), expected["final_capital"], "finalCapital")
    # Multi-asset runs on the pinned sources report 0 here (characterised defect).
    _close(statistics.get("totalFees"), expected.get("provider_total_fees", expected["total_fees"]),
           "totalFees")
    _close(performance.get("totalReturn"), expected["total_return"], "totalReturn")
    if performance.get("totalTrades") != len(expected["trades"]):
        raise ProbeError("TOTAL_TRADES_MISMATCH")
    return {"provider_using_synthetic_data": data.get("usingSyntheticData"),
            "provider_data_source": data.get("dataSource"),
            "provider_total_slippage": statistics.get("totalSlippage")}


# provider `performance` / `statistics` key -> oracle key
PERFORMANCE_KEYS = {
    "totalReturn": "total_return", "annualizedReturn": "annualized_return",
    "volatility": "volatility", "sharpeRatio": "sharpe", "sortinoRatio": "sortino",
    "maxDrawdown": "max_drawdown", "calmarRatio": "calmar", "winRate": "win_rate",
    "averageWin": "average_win", "averageLoss": "average_loss",
    "largestWin": "largest_win", "largestLoss": "largest_loss",
    "expectancy": "expectancy", "averageTradeReturn": "expectancy",
}
STATISTICS_KEYS = {"averageDailyReturn": "average_bar_return", "bestDay": "best_bar",
                   "worstDay": "worst_bar"}
COUNT_KEYS = {("performance", "totalTrades"): "total_trades",
              ("performance", "winningTrades"): "winning_trades",
              ("performance", "losingTrades"): "losing_trades",
              ("statistics", "winningDays"): "winning_bars",
              ("statistics", "losingDays"): "losing_bars"}


def compare_metrics(response: dict, expected: dict) -> None:
    """Check the provider's performance and statistics blocks against the metric oracle."""
    data = response.get("data") or {}
    performance, statistics = data.get("performance") or {}, data.get("statistics") or {}
    for block, mapping in ((performance, PERFORMANCE_KEYS), (statistics, STATISTICS_KEYS)):
        for key, name in mapping.items():
            _close(block.get(key), Fraction(expected[name]), key, RATIO_ABS_TOL)
    _close(performance.get("lossRate"), 1 - expected["win_rate"], "lossRate", RATIO_ABS_TOL)
    for (block_name, key), name in COUNT_KEYS.items():
        observed = (performance if block_name == "performance" else statistics).get(key)
        if isinstance(observed, bool) or observed != expected[name]:
            raise ProbeError("ORACLE_MISMATCH:%s:provider=%r:oracle=%r" % (key, observed, expected[name]))
    factor = performance.get("profitFactor")
    if expected["profit_factor"] is None:
        if factor is not None:  # +inf is serialised as null by the provider
            raise ProbeError("ORACLE_MISMATCH:profitFactor:provider=%r:oracle=inf" % (factor,))
    else:
        _close(factor, expected["profit_factor"], "profitFactor", RATIO_ABS_TOL)
    text = (data.get("assumptions") or {}).get("annualization", "")
    wanted = ANNUALIZATION_TEXT[expected["periods_per_year"]]
    if not isinstance(text, str) or not text.startswith(wanted):
        raise ProbeError("ANNUALIZATION_BASIS_MISMATCH:provider=%r" % (text[:60],))


def run_scenario(backtesting_dir: Path, scenario: dict, python: str = sys.executable) -> dict:
    candles = fixture_for(scenario)
    expected = oracle.simulate(
        candles, fast=scenario["fast"], slow=scenario["slow"],
        initial_capital=scenario.get("initial_capital", "100000"),
        commission=scenario.get("commission", "0"), slippage=scenario.get("slippage", "0"),
        sizing_mode=scenario.get("sizing_mode", "percent"),
        sizing_value=scenario.get("sizing_value", "100"),
        execution=scenario.get("execution", "next_open"),
        **{name: scenario.get(name) for name in STOP_KEYS})
    if not expected["trades"]:
        raise ProbeError("SCENARIO_HAS_NO_TRADES:" + scenario["name"])
    run = run_original_provider(backtesting_dir, build_request(candles, scenario), python)
    labels = compare(run["response"], expected)
    measured = metrics_oracle.metrics(
        expected["equity"], expected["trades"],
        Fraction(scenario.get("initial_capital", "100000")), expected_periods_per_year(scenario),
        Fraction(scenario.get("risk_free_rate", "0")))
    compare_metrics(run["response"], measured)
    return {
        "scenario": scenario["name"],
        "bars": expected["bars"],
        "trades": len(expected["trades"]),
        "exit_reasons": sorted({t["exit_reason"] for t in expected["trades"]}),
        "exit_bars": [t["exit_bar"] for t in expected["trades"]],
        "oracle_total_return": float(expected["total_return"]),
        "oracle_total_fees": float(expected["total_fees"]),
        "periods_per_year": measured["periods_per_year"],
        "oracle_sharpe_as_stated_by_provider": float(measured["sharpe"]),
        "oracle_sharpe_arithmetic_mean_convention": float(measured["conventional_sharpe"]),
        "oracle_max_drawdown": float(measured["max_drawdown"]),
        "network_attempts_denied": run["network_attempts"],
        "status": "ORIGINAL_PROVIDER_MATCHES_EXACT_ORACLE",
        **labels,
    }


def multi_asset_scenarios():
    """Two symbols, weighted and equal allocation, with and without a stop."""
    costs = {"fast": 5, "slow": 20, "commission": "0.001", "slippage": "0.0005"}
    return [
        dict(costs, name="multi_asset_75_25", weights=["0.75", "0.25"]),
        dict(costs, name="multi_asset_equal_weight"),
        dict(costs, name="multi_asset_75_25_take_profit", weights=["0.75", "0.25"], take_profit="0.03"),
    ]


def run_multi_asset_scenario(backtesting_dir: Path, scenario: dict, python: str = sys.executable) -> dict:
    """The provider's multi-asset path: each symbol simulated on its share of the
    capital, equity summed bar by bar, trades listed symbol by symbol."""
    capital = Fraction(scenario.get("initial_capital", "100000"))
    weights = [Fraction(w) for w in scenario.get("weights") or ["0.5", "0.5"]]
    if len(weights) != len(MULTI_SYMBOLS) or sum(weights) != 1 or min(weights) <= 0:
        raise ProbeError("INVALID_MULTI_ASSET_WEIGHTS")
    series = [fixture_for({}), fixture_for({"fixture": SECOND})]
    legs = []
    for symbol, candles, weight in zip(MULTI_SYMBOLS, series, weights):
        leg = oracle.simulate(
            candles, fast=scenario["fast"], slow=scenario["slow"],
            initial_capital=str(capital * weight),
            commission=scenario.get("commission", "0"), slippage=scenario.get("slippage", "0"),
            **{name: scenario.get(name) for name in STOP_KEYS})
        if not leg["trades"]:
            raise ProbeError("SCENARIO_HAS_NO_TRADES:" + scenario["name"] + ":" + symbol)
        legs.append(leg)
    equity = [sum(values, Fraction(0)) for values in zip(*(leg["equity"] for leg in legs))]
    trades = [dict(trade, symbol=symbol) for symbol, leg in zip(MULTI_SYMBOLS, legs)
              for trade in leg["trades"]]
    true_fees = sum((leg["total_fees"] for leg in legs), Fraction(0))
    expected = {"bars": legs[0]["bars"], "times": legs[0]["times"], "equity": equity,
                "trades": trades, "final_capital": equity[-1], "total_fees": true_fees,
                "total_return": equity[-1] / capital - 1,
                # ORIGINAL behaviour on the pinned sources: the combined portfolio is
                # built without the per-symbol fees, so the statistic reads 0.
                "provider_total_fees": Fraction(0)}

    request = build_request(series[0], scenario)
    request["symbols"] = list(MULTI_SYMBOLS)
    request["brokerCandles"] = {
        symbol: [{"t": row["t"], "o": float(row["o"]), "h": float(row["h"]),
                  "l": float(row["l"]), "c": float(row["c"]), "v": row["v"]} for row in candles]
        for symbol, candles in zip(MULTI_SYMBOLS, series)}
    if scenario.get("weights"):
        request["weights"] = [float(w) for w in weights]
    run = run_original_provider(backtesting_dir, request, python)
    labels = compare(run["response"], expected)
    measured = metrics_oracle.metrics(equity, trades, capital, 365)
    compare_metrics(run["response"], measured)
    return {
        "scenario": scenario["name"],
        "bars": expected["bars"],
        "trades": len(trades),
        "trades_per_symbol": {s: len(leg["trades"]) for s, leg in zip(MULTI_SYMBOLS, legs)},
        "exit_reasons": sorted({t["exit_reason"] for t in trades}),
        "exit_bars": [t["exit_bar"] for t in trades],
        "oracle_total_return": float(expected["total_return"]),
        "oracle_total_fees": float(true_fees),
        "provider_total_fees": (run["response"]["data"].get("statistics") or {}).get("totalFees"),
        "periods_per_year": measured["periods_per_year"],
        "oracle_sharpe_as_stated_by_provider": float(measured["sharpe"]),
        "oracle_sharpe_arithmetic_mean_convention": float(measured["conventional_sharpe"]),
        "oracle_max_drawdown": float(measured["max_drawdown"]),
        "network_attempts_denied": run["network_attempts"],
        "status": "ORIGINAL_PROVIDER_MATCHES_EXACT_ORACLE",
        **labels,
    }


def run_all(backtesting_dir: Path, python: str = sys.executable, scenarios=None) -> dict:
    results = [run_scenario(backtesting_dir, s, python)
               for s in (scenarios or default_scenarios() + stop_scenarios() + metric_scenarios())]
    if scenarios is None:
        results += [run_multi_asset_scenario(backtesting_dir, s, python)
                    for s in multi_asset_scenarios()]
    return {
        "schema": SCHEMA,
        "source_kind": "SYNTHETIC_FIXTURE_NOT_MARKET_DATA",
        "scientific_status": "NOT_EVALUATED",
        "broker_authority": False,
        "promotion_eligible": False,
        "pinned_fork_main": "7716ee8613249fb44c4d14036c5bc16ed6f34e97",
        "tolerance": {"relative": REL_TOL, "absolute": ABS_TOL},
        "pinned_original_sources": sorted(PINNED_SOURCES),
        "scenario_count": len(results),
        "scenarios": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backtesting-dir", type=Path, required=True,
                        help="path to " + BACKTESTING_RELATIVE)
    parser.add_argument("--python", default=sys.executable,
                        help="interpreter with numpy and pandas for the original provider")
    args = parser.parse_args()
    try:
        result = run_all(args.backtesting_dir, args.python)
    except (ProbeError, oracle.OracleRefused, OSError) as exc:
        print(json.dumps({"schema": SCHEMA, "status": "FAILED_OR_UNVERIFIED",
                          "reason": str(exc)[:240], "broker_authority": False,
                          "promotion_eligible": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
