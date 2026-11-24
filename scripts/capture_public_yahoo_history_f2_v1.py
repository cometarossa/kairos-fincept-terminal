#!/usr/bin/env python3
"""Single opt-in allowlisted 5d/1d capture via the original Fincept Yahoo adapter.

Research only. Local receipt clock is NOT exchange time. Adjusted OHLC,
provider volume; no quote, completed-session, scientific or execution claim.
The caller supplies the bounded Yahoo-only network QA environment and timeout.
No scheduled deployment, broker access or retries are implemented here.
"""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time

from capture_public_cnbc_rss_f2_v1 import private_directory, publish

ACK = "SPY_YAHOO_HISTORY_SNAPSHOT_V1"
MULTI_ACK = "MULTI_YAHOO_HISTORY_SNAPSHOT_V1"
DUAL_ACK = "DUAL_WINDOW_YAHOO_HISTORY_SNAPSHOT_V1"
LONG_SYMBOLS = frozenset({"SPY", "EURUSD=X"})
ALLOWED_SYMBOLS = frozenset(["SPY","EURUSD=X","GBPUSD=X","JPY=X","AUDUSD=X","CAD=X","^GSPC","^NDX","^GDAXI","AAPL","BTC-USD","GC=F"])
FIELDS = {"timestamp", "open", "high", "low", "close", "volume"}


def build_snapshot(rows, captured: int, symbol: str = "SPY", period: str = "5d") -> dict:
    long_window = period == "6mo"
    if period not in ("5d", "6mo") or (long_window and symbol not in LONG_SYMBOLS):
        raise ValueError("window denied")
    if type(symbol) is not str or symbol not in ALLOWED_SYMBOLS:
        raise ValueError("symbol denied")
    if type(captured) is not int or captured <= 0 or type(rows) is not list or not (100 if long_window else 1) <= len(rows) <= (160 if long_window else 5):
        raise ValueError("invalid history")
    previous = 0
    for row in rows:
        if type(row) is not dict or set(row) != FIELDS:
            raise ValueError("invalid bar")
        ts = row["timestamp"]
        if type(ts) is not int or not previous < ts <= captured or ts < captured - (200 if long_window else 14)*86400:
            raise ValueError("invalid timestamp")
        o, h, l, c, v = (row[k] for k in ("open", "high", "low", "close", "volume"))
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in (o,h,l,c,v)):
            raise ValueError("invalid number")
        if min(o,h,l,c) <= 0 or l > min(o,c) or h < max(o,c) or h < l:
            raise ValueError("invalid OHLC")
        if not 0 <= v <= 9007199254740991 or int(v) != v:
            raise ValueError("invalid volume")
        previous = ts
    if long_window and rows[0]["timestamp"] > captured - 140*86400:
        raise ValueError("short history span")
    if previous < captured - 7*86400:
        raise ValueError("stale history")
    raw = json.dumps(rows, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(raw) > (49152 if long_window else 16384):
        raise ValueError("oversized bars")
    return {"schema": "YAHOO_HISTORY_SNAPSHOT_V1",
            "provider": "Yahoo Finance via original yfinance",
            "symbol": symbol, "period": period, "interval": "1d",
            "adjustment": "AUTO_ADJUST_TRUE_BACK_ADJUST_FALSE",
            "captured_at_unix": captured,
            "bars_base64": base64.b64encode(raw).decode("ascii"),
            "bars_sha256": hashlib.sha256(raw).hexdigest()}


def capture(directory: Path, symbol: str = "SPY", period: str = "5d") -> None:
    long_window = period == "6mo"
    if period not in ("5d", "6mo") or (long_window and symbol not in LONG_SYMBOLS):
        raise ValueError("window denied")
    ack = os.environ.get("FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK")
    if type(symbol) is not str or symbol not in ALLOWED_SYMBOLS:
        raise ValueError("symbol denied")
    if (long_window and ack != DUAL_ACK) or (not long_window and ack not in (MULTI_ACK, DUAL_ACK) and not (ack == ACK and symbol == "SPY")):
        raise ValueError("explicit opt-in required")
    private_directory(directory)
    if long_window or symbol != "SPY":
        directory = directory / ("long-" + symbol if long_window else symbol)
        private_directory(directory)
    lock = os.open(directory / ".capture.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        st = os.fstat(lock)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1:
            raise ValueError("unsafe lock")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Import only after opt-in and private-directory checks. The original
        # adapter owns adjustment semantics and provider conversion.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fincept-qt" / "scripts"))
        import yfinance_data as original
        original._NET_TIMEOUT = 6.0
        rows = original.get_historical_period(symbol, period, "1d")
        snapshot = build_snapshot(rows, int(time.time()), symbol, period)
        publish(directory, snapshot)
        print("FINCEPT_F2_HISTORY_CAPTURE_OK", "symbol="+symbol, "bars="+str(len(rows)),
              "captured_at_unix="+str(snapshot["captured_at_unix"]),
              "sha256="+snapshot["bars_sha256"])
    finally:
        os.close(lock)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", required=True, type=Path)
    parser.add_argument("--symbol", default="SPY", choices=sorted(ALLOWED_SYMBOLS))
    parser.add_argument("--period", default="5d", choices=("5d", "6mo"))
    args = parser.parse_args()
    try:
        capture(args.inbox, args.symbol, args.period)
    except Exception:
        # Never print provider error strings, cookies, headers or prices.
        print("FINCEPT_F2_HISTORY_CAPTURE_UNAVAILABLE")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
