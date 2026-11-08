#!/usr/bin/env python3
"""Read-only Fincept Backtesting audit using only synthetic data.

Runs metadata calls and ONE fixture-only VectorBT computation.
Does not access a broker, use stored application settings, or fetch prices.
Every child loads offline_netguard/sitecustomize.py to refuse Python sockets.
A Python socket guard is defense in depth, NOT a whole-OS network sandbox.
Never use this to evaluate strategy quality or trade with real capital.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

PROVIDERS = ("vectorbt", "backtestingpy", "fasttrade", "zipline", "bt", "fincept")
COMMANDS = ("get_strategies", "get_indicators", "get_command_options")


def child_env(script_root: Path, tmp: Path) -> dict[str, str]:
    guard = Path(__file__).resolve().parent / "offline_netguard"
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "HOME": str(tmp),
        "TMPDIR": str(tmp),
        "PYTHONNOUSERSITE": "1",
        "NO_PROXY": "*",
        "HTTP_PROXY": "",
        "HTTPS_PROXY": "",
        "ALL_PROXY": "",
        "PYTHONPATH": os.pathsep.join((str(guard), str(script_root))),
    }


def run_json(python: Path, script: Path, command: str, payload: dict,
             env: dict[str, str], *, timeout: int = 20) -> dict:
    result = subprocess.run(
        (str(python), str(script), command, "--stdin"),
        input=json.dumps(payload, separators=(",", ":")),
        text=True, capture_output=True, timeout=timeout, env=env,
        cwd=str(script.parent), check=False,
    )
    if result.returncode != 0:
        # Deliberately do not include stderr, which may contain user data
        return {"ok": False, "reason": "subprocess_exit", "rc": result.returncode}
    try:
        obj = json.loads(result.stdout.strip())
    except (ValueError, TypeError):
        return {"ok": False, "reason": "malformed_json"}
    if not isinstance(obj, dict):
        return {"ok": False, "reason": "invalid_response_type"}
    if obj.get("success") is False:
        return {"ok": False, "reason": "provider_declined"}
    return {"ok": True, "data": obj}


def count_items(command: str, obj: dict) -> int:
    data = obj.get("data", {})
    if command == "get_indicators":
        groups = obj.get("indicators", {})
        if isinstance(groups, dict):
            return sum(len(v) if isinstance(v, list) else 0 for v in groups.values())
        return len(groups) if isinstance(groups, list) else 0
    if command == "get_strategies":
        strategies = data.get("strategies", {}) if isinstance(data, dict) else data
        if isinstance(strategies, dict):
            return sum(len(v) for v in strategies.values() if isinstance(v, list))
        return len(strategies) if isinstance(strategies, list) else 0
    return len(data) if isinstance(data, (list, dict)) else 0


def synthetic_candles() -> list[dict]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(320):
        t = int((start + timedelta(days=i)).timestamp())
        px = 100 + 0.09 * i + 3 * math.sin(i / 10)
        rows.append({
            "t": t, "o": round(px - .3, 4),
            "h": round(px + 1.2, 4), "l": round(px - 1.5, 4),
            "c": round(px, 4), "v": 1000 + i,
        })
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scripts-root", type=Path, required=True,
                   help="Installed Fincept scripts directory (read-only)")
    p.add_argument("--venv1-python", type=Path, required=True,
                   help="Existing numpy1 venv Python binary")
    p.add_argument("--venv2-python", type=Path, required=True,
                   help="Existing numpy2 venv Python binary")
    args = p.parse_args()
    scripts = args.scripts_root.resolve(strict=True)
    # IMPORTANT: venv Python binaries are often symlinks. resolve() follows the
    # link to the global interpreter and LOSES the venv package environment.
    # Preserve the original binary path for process launch.
    py1 = args.venv1_python.absolute()
    py2 = args.venv2_python.absolute()
    if not py1.is_file() or not os.access(py1, os.X_OK):
        raise SystemExit("Missing venv1 Python executable")
    if not py2.is_file() or not os.access(py2, os.X_OK):
        raise SystemExit("Missing venv2 Python executable")
    if not (scripts / "Analytics/backtesting/vectorbt/vectorbt_provider.py").is_file():
        raise SystemExit("Invalid Fincept scripts root; no provider source")
    with tempfile.TemporaryDirectory(prefix="fincept-offline-audit-") as dir_name:
        temp = Path(dir_name)
        env = child_env(scripts, temp)
        guard_check = subprocess.run(
            (str(py1), "-c",
             "import socket; s=socket.socket(); "
             "assert socket.create_connection(('192.0.2.1', 80)) is None"),
            env=env, capture_output=True, text=True, timeout=6, check=False,
        )
        # Guard must reject socket access: the injected assertion must fail.
        if guard_check.returncode == 0 or "FINCEPT_AUDIT_NETWORK_BLOCKED" not in guard_check.stderr:
            raise SystemExit("STOP: Python network-deny guard not active")
        report: dict[str, object] = {
            "category": "synthetic_offline_functional_probe",
            "disclaimer": "No live data, no broker, no trading; no alpha claim",
            "verified_network_guard": True,
            "providers": {},
        }
        for name in PROVIDERS:
            provider_script = scripts / "Analytics/backtesting" / name / f"{name}_provider.py"
            results = {}
            for command in COMMANDS:
                try:
                    res = run_json(py1, provider_script, command, {}, env)
                    results[command] = {
                        "ok": bool(res["ok"]),
                        "count": count_items(command, res["data"]) if res["ok"] else 0,
                        "reason": res.get("reason"),
                    }
                except subprocess.TimeoutExpired:
                    results[command] = {"ok": False, "reason": "timeout"}
            report["providers"][name] = results
        # This is NOT a market backtest: supply 320 fabricated bars through
        # the existing brokerCandles injection seam without an actual broker.
        payload = {
            "symbols": ["KAIROS_FIXTURE"],
            "startDate": "2024-01-01", "endDate": "2024-12-31",
            "interval": "1d",
            "initialCapital": 100000,
            "commission": .001, "slippage": .0005,
            "strategy": {
                "type": "sma_crossover",
                "params": {"fastPeriod": 10, "slowPeriod": 30},
            },
            "brokerCandles": {"KAIROS_FIXTURE": synthetic_candles()},
            "brokerDataSource": "synthetic-regression-fixture",
            "allowSyntheticData": False,
            "benchmarkSymbol": "",
        }
        try:
            res = run_json(
                py1,
                scripts / "Analytics/backtesting/vectorbt/vectorbt_provider.py",
                "run_backtest", payload, env, timeout=55,
            )
            data = res["data"].get("data", {}) if res["ok"] else {}
            report["injected_vectorbt"] = {
                "ok": bool(res["ok"] and data.get("status") == "completed"),
                "fixture_candles": 320,
                "source": data.get("dataSource"),
                "provider_usingSyntheticData": data.get("usingSyntheticData"),
                "important": "These are fabricated bars regardless of provider flag",
            }
        except subprocess.TimeoutExpired:
            report["injected_vectorbt"] = {"ok": False, "reason": "timeout"}
        print(json.dumps(report, sort_keys=True, indent=2))
        checks = [
            row[command]["ok"]
            for row in report["providers"].values()
            for command in COMMANDS
        ]
        checks.append(report["injected_vectorbt"]["ok"])
        return 0 if all(checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
