"""Read-only, training-era historical signal DIFFERENCE replay (not a backtest).

Source: frozen CC0 Kaggle dataset through 2017-11-10; retrospectively
adjusted and survivor-biased.  Do not use as a point-in-time trading source.
Never writes the archive, holds a broker connection or calculates P&L.
Emits aggregate counts and hashes only, never raw market OHLCV rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import zipfile

SCHEMA = "fincept_recorded_signal_comparison_v1"
SOURCE_SHA256 = "d9317c8fb2d63b9b00db5f933b6c9639d2bf7ea3b918169bb5cec5903dce85a1"
BASE_ENGINE_BLOB = "cf454fff4dc204a45248bc285f72fd38745e68b7"
FIX_ENGINE_BLOB = "7d3c32ca4d9f4a265a77dbbe56d59b52129ecfb5"
CONSUMER_BLOB = "1ae2adbd70fa143f528928338184da336ca0bc6d"
MEMBERS = {
    "AAPL": ("Stocks/aapl.us.txt", 3021795949),
    "IBM": ("Stocks/ibm.us.txt", 2247021503),
    "SPY": ("ETFs/spy.us.txt", 2487404040),
}
RULES = (
    "ADX_DI_CROSS_UP", "ADX_DI_CROSS_DOWN",
    "ST_VALUE_FALLING", "ST_VALUE_RISING",
    "ST_DIRECTION_UP_CROSS", "ST_DIRECTION_DOWN_CROSS",
    "ST_LONG_STATE", "ST_LINE_BELOW_CLOSE", "ST_LINE_ABOVE_CLOSE",
)
FIRST_DATA_DATE = "2014-01-02"
LAST_DATA_DATE = "2017-11-10"
FIRST_REPLAY_DATE = "2015-01-01"
EXPECTED_ROWS = 974
EXPECTED_REPLAY_ROWS = 722
# Strict expected outputs for the frozen archive + old/fixed code identities.
EXPECTED_LONG_COUNTS = {"AAPL": (722, 356), "IBM": (722, 299), "SPY": (722, 436)}
EXPECTED_ADX_CROSSINGS = {"AAPL": (29, 28), "IBM": (28, 27), "SPY": (40, 40)}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()


def input_from_member(z: zipfile.ZipFile, member: str, expected_crc: int):
    info = z.getinfo(member)
    if info.CRC != expected_crc or info.file_size > 3_000_000:
        raise ValueError("SOURCE_MEMBER_CRC_OR_SIZE_MISMATCH:" + member)
    # ZipFile verifies the member CRC when read to completion. No dataset copy.
    with z.open(info) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
        expected_fields = ["Date", "Open", "High", "Low", "Close", "Volume", "OpenInt"]
        if reader.fieldnames != expected_fields:
            raise ValueError("SOURCE_SCHEMA_DRIFT:" + member)
        rows = []
        dates = []
        for row in reader:
            date = row["Date"]
            if date < "2014-01-01" or date > LAST_DATA_DATE:
                continue
            if dates and date <= dates[-1]:
                raise ValueError("DATE_ORDER_OR_DUPLICATE:" + member)
            values = []
            for field in ("Open", "High", "Low", "Close", "Volume"):
                val = row[field]
                try:
                    numeric = float(val)
                except (ValueError, TypeError):
                    raise ValueError("INVALID_NUMBER:" + member) from None
                if not math.isfinite(numeric):
                    raise ValueError("NONFINITE_PRICE:" + member)
                values.append(val)
            dates.append(date)
            rows.append(",".join((date, *values)) + "\n")
    if len(rows) != EXPECTED_ROWS or (dates[0], dates[-1]) != (FIRST_DATA_DATE, LAST_DATA_DATE):
        raise ValueError("UNEXPECTED_WINDOW_OR_ROW_COUNT:" + member)
    return "".join(rows), dates


def parse_masks(output: str):
    lines = output.splitlines()
    if not lines:
        raise ValueError("MISSING_REPLAY_OUTPUT")
    expected_header = "#schema=fincept_recorded_signal_mask_v1;rules=" + "|".join(RULES)
    if lines[0] != expected_header:
        raise ValueError("REPLAY_SCHEMA_OR_RULE_MISMATCH")
    result = {}
    for line in lines[1:]:
        fields = line.split(",")
        if len(fields) != 2 or not fields[1].isdigit():
            raise ValueError("CORRUPT_REPLAY_OUTPUT")
        date, mask_str = fields
        if date in result or not FIRST_REPLAY_DATE <= date <= LAST_DATA_DATE:
            raise ValueError("REPLAY_DATE_OUT_OF_RANGE_OR_DUPLICATED")
        mask = int(mask_str)
        if mask < 0 or mask >= (1 << len(RULES)):
            raise ValueError("REPLAY_MASK_OUT_OF_RANGE")
        if result and date <= next(reversed(result)):
            raise ValueError("REPLAY_OUT_OF_ORDER")
        result[date] = mask
    if not result:
        raise ValueError("NO_REPLAY_EVENTS")
    return result


def replay_binary(binary: Path, data: str):
    proc = subprocess.run([str(binary)], input=data, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=120, check=False)
    if proc.returncode != 0:
        # Never print input or raw prices; only a bounded error diagnostic.
        raise RuntimeError("REPLAY_BINARY_FAILED code=%d: %s" %
                           (proc.returncode, proc.stderr[:200]))
    return parse_masks(proc.stdout)


def compare(old, new):
    if list(old) != list(new):
        raise ValueError("OLD_NEW_DATE_MISMATCH")
    rows = []
    for k, rule in enumerate(RULES):
        bit = 1 << k
        old_true = sum(bool(v & bit) for v in old.values())
        new_true = sum(bool(v & bit) for v in new.values())
        old_only = sum(bool(old[date] & bit) and not bool(new[date] & bit) for date in old)
        new_only = sum(not bool(old[date] & bit) and bool(new[date] & bit) for date in old)
        rows.append({"rule": rule, "old_true": old_true, "fixed_true": new_true,
                     "old_only": old_only, "fixed_only": new_only,
                     "changed": old_only + new_only})
    return rows


def run(archive: Path, old_binary: Path, fixed_binary: Path,
        old_engine: Path, fixed_engine: Path, consumer_source: Path):
    if file_sha256(archive) != SOURCE_SHA256:
        raise ValueError("ARCHIVE_SHA256_NOT_FROZEN_CC0")
    if git_blob(old_engine) != BASE_ENGINE_BLOB:
        raise ValueError("OLD_ENGINE_BLOB_MISMATCH")
    if git_blob(fixed_engine) != FIX_ENGINE_BLOB:
        raise ValueError("CANDIDATE_ENGINE_BLOB_MISMATCH")
    if git_blob(consumer_source) != CONSUMER_BLOB:
        raise ValueError("CONSUMER_ENGINE_BLOB_MISMATCH")
    result = {
        "schema": SCHEMA,
        "status": "DEVELOPMENT_DIAGNOSTICS_ONLY",
        "source": "Kaggle CC0 Huge Stock Market Dataset, 2017",
        "archive_sha256": SOURCE_SHA256,
        "original_engine_git_blob": BASE_ENGINE_BLOB,
        "candidate_engine_git_blob": FIX_ENGINE_BLOB,
        "unchanged_consumer_git_blob": CONSUMER_BLOB,
        "source_limit": LAST_DATA_DATE,
        "data_cutoff_convention": "retrospectively_adjusted_NOT_point_in_time",
        "prohibited_claims": ["alpha", "strategy_PnL", "strategy_trade_count", "broker_fitness",
                              "PIT_certification", "real_market_2018_plus"],
        "instruments": [],
    }
    with zipfile.ZipFile(archive) as z:
        for symbol, (member, expected_crc) in MEMBERS.items():
            input_data, dates = input_from_member(z, member, expected_crc)
            old = replay_binary(old_binary, input_data)
            fixed = replay_binary(fixed_binary, input_data)
            if not (set(old).issubset(set(dates)) and set(fixed).issubset(set(dates))):
                raise ValueError("EMITTED_DATES_NOT_IN_SOURCE")
            rows = compare(old, fixed)
            if len(old) != EXPECTED_REPLAY_ROWS:
                raise ValueError("UNEXPECTED_REPLAY_BAR_COUNT:" + symbol)
            summary = {r["rule"]: r for r in rows}
            longs = summary["ST_LONG_STATE"]
            if (longs["old_true"], longs["fixed_true"]) != EXPECTED_LONG_COUNTS[symbol]:
                raise ValueError("NONVACUITY_OR_ENGINE_MISWIRE:" + symbol)
            if (summary["ADX_DI_CROSS_UP"]["old_true"],
                    summary["ADX_DI_CROSS_DOWN"]["old_true"]) != EXPECTED_ADX_CROSSINGS[symbol]:
                raise ValueError("ADX_SOURCE_DRIFT:" + symbol)
            for name in ("ADX_DI_CROSS_UP", "ADX_DI_CROSS_DOWN"):
                if summary[name]["changed"] != 0:
                    raise ValueError("ADX_CONSUMER_PATH_CHANGED:" + symbol)
            result["instruments"].append({
                "symbol": symbol, "member": member, "crc32": expected_crc,
                "source_rows": len(dates),
                "source_first": dates[0], "source_last": dates[-1],
                "input_sha256": hashlib.sha256(input_data.encode("utf-8")).hexdigest(),
                "replay_rows": len(old), "replay_first": next(iter(old)),
                "replay_last": next(reversed(old)),
                "signal_changes": sum(row["changed"] for row in rows),
                "changed_dates_any_rule": sum(old[date] != fixed[date] for date in old),
                "unchanged_dates_all_rules": sum(old[date] == fixed[date] for date in old),
                "rules": rows,
            })
    return result


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--archive", type=Path, required=True)
    a.add_argument("--old-bin", type=Path, required=True)
    a.add_argument("--fixed-bin", type=Path, required=True)
    a.add_argument("--old-engine", type=Path, required=True)
    a.add_argument("--fixed-engine", type=Path, required=True)
    a.add_argument("--consumer-source", type=Path, required=True)
    a.add_argument("--report", type=Path, required=True)
    args = a.parse_args()
    result = run(args.archive, args.old_bin, args.fixed_bin,
                 args.old_engine, args.fixed_engine, args.consumer_source)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    for r in result["instruments"]:
        print(r["symbol"], "rows", r["replay_rows"], "rule_date_changes",
              r["signal_changes"], "distinct_changed_days", r["changed_dates_any_rule"])
        for item in r["rules"]:
            print(" ", item["rule"], "old", item["old_true"],
                  "new", item["fixed_true"], "old_only", item["old_only"],
                  "fixed_only", item["fixed_only"])
    print("AGGREGATES_ONLY_WRITTEN", args.report)


if __name__ == "__main__":
    main()
