"""Verify unmodified #46 C++ Supertrend against independently defined conventions.

Research-only: deterministic synthetic bars, no prices fetched or brokerage path.
The candidate uses EMA-smoothed ATR and an initially bullish Supertrend.
TradingView defaults to Wilder/RMA-smoothed ATR and an initially bearish line.
This is a mathematical *configuration difference*, not a strategy PnL finding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from tools.fincept_audit.supertrend_external_convention_audit_v1 import (
    PERIOD, compute, make_fixture, diagnostics,
)

ROOT = Path(__file__).resolve().parents[3]
CODE = ROOT / "fincept-qt/src/algo_engine/IndicatorEngine.cpp"
CANDIDATE_GIT_BLOB = "7d3c32ca4d9f4a265a77dbbe56d59b52129ecfb5"
SCHEMA = "fincept_supertrend_external_convention_audit_v1"
CLI_HEADER = "#schema=fincept_synthetic_supertrend_candidate_prefix_v1"
CASES = ("reversals", "shock")
EXPECTED_COUNTS = {
    "reversals": {
        "tradingview_state_EMA_matched_seed": (0, 0),
        "tradingview_state_Wilder_matched_seed": (0, 190),
        "tradingview_documented_down_initial": (15, 190),
    },
    "shock": {
        "tradingview_state_EMA_matched_seed": (0, 0),
        "tradingview_state_Wilder_matched_seed": (43, 167),
        "tradingview_documented_down_initial": (67, 190),
    },
}


def git_blob(path):
    content = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\x00" + content).hexdigest()


def parse_native_output(src):
    rows = src.splitlines()
    if len(rows) != 191 or rows[0] != CLI_HEADER:
        raise ValueError("UNEXPECTED_NATIVE_OUTPUT_SCHEMA_OR_ROWS")
    values = {}
    for offset, line in enumerate(rows[1:], 10):
        fields = line.split(",")
        if len(fields) != 3:
            raise ValueError("UNEXPECTED_NATIVE_NUMERIC_DELIMITER")
        try:
            index = int(fields[0])
            value = float(fields[1])
            direction = int(fields[2])
        except ValueError as e:
            raise ValueError("BAD_NATIVE_NUMERIC_VALUE") from e
        if index != offset or not math.isfinite(value) or direction not in (-1, 1):
            raise ValueError("INVALID_NATIVE_INDEX_OR_RESULT")
        values[index] = (value, direction)
    return values


def read_native(binary, fixture_name):
    result = subprocess.run(
        [str(binary), fixture_name], capture_output=True, text=True, timeout=60, check=False,
    )
    if result.returncode:
        raise ValueError("NATIVE_CANDIDATE_NONZERO_EXIT_%d" % result.returncode)
    return parse_native_output(result.stdout)


def run(binary):
    if git_blob(CODE) != CANDIDATE_GIT_BLOB:
        raise ValueError("CANDIDATE_GIT_BLOB_MISMATCH")
    report = {
        "schema": SCHEMA,
        "status": "RESEARCH_ONLY_NOT_PIT_NOT_TRADING",
        "indicator_engine_git_blob": CANDIDATE_GIT_BLOB,
        "external_convention": "TradingView documented Supertrend plus default Wilder/RMA ATR",
        "known_config_differences": {
            "fincept_ATR": "EMA alpha=2/(period+1)",
            "tradingview_default_ATR": "RMA/Wilder alpha=1/period",
            "fincept_initial_direction": "up",
            "tradingview_initial_direction": "down until ATR available",
        },
        "fixtures": [],
        "hard_limits": ["synthetic_data_only", "no_actual_trade", "no_actual_market_signal",
                        "no_strategy_returns", "no_PIT_admission", "no_CI_authority"],
    }
    for name in CASES:
        native = read_native(binary, name)
        expected = compute(make_fixture(name), smoothing="ema",
                           variant="candidate", initial_dir=1)
        errors = [abs(native[i][0] - float(expected[i][0])) for i in native]
        wrong_dirs = [i for i in native if native[i][1] != expected[i][1]]
        max_error = max(errors)
        if wrong_dirs or max_error > 1e-8:
            raise ValueError("CPP_CANDIDATE_VS_FRACTION_REFERENCE_MISMATCH:" + name)
        compare = diagnostics(name)
        for label, (want_dir, want_line) in EXPECTED_COUNTS[name].items():
            item = compare[label]
            if (item["direction_diff_count"], item["line_diff_count"]) != (want_dir, want_line):
                raise ValueError("CONVENTION_COMPARISON_NONVACUITY_FAILURE:" + name + ":" + label)
        report["fixtures"].append({
            "name": name,
            "synthetic_source_rows": len(make_fixture(name)),
            "native_prefixes": len(native),
            "cpp_vs_fraction_direction_mismatches": len(wrong_dirs),
            "cpp_vs_fraction_max_abs_error": max_error,
            "comparison": compare,
        })
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-binary", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    data = run(args.native_binary)
    args.report.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for entry in data["fixtures"]:
        print(entry["name"], "native_prefixes", entry["native_prefixes"],
              "candidate_cpp_vs_fraction_max_error",
              "%.4g" % entry["cpp_vs_fraction_max_abs_error"])
        for label, metrics in entry["comparison"].items():
            print(" ", label, "direction_diff", metrics["direction_diff_count"],
                  "line_diff", metrics["line_diff_count"])
    print("SYNTHETIC_AGGREGATES_ONLY_WRITTEN", args.report)


if __name__ == "__main__":
    main()
