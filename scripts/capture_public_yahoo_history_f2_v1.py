#!/usr/bin/env python3
"""Single opt-in allowlisted daily capture via the original Fincept Yahoo adapter.

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
ARCHIVE_ACK = "TWO_YEAR_YAHOO_DAILY_ARCHIVE_V1"
# Archive-only namespace: never put the 2y window into a live MCP inbox.
LONG_SYMBOLS = frozenset({"SPY", "EURUSD=X"})
ALLOWED_SYMBOLS = frozenset(["SPY","EURUSD=X","GBPUSD=X","JPY=X","AUDUSD=X","CAD=X","^GSPC","^NDX","^GDAXI","AAPL","BTC-USD","GC=F"])
FIELDS = {"timestamp", "open", "high", "low", "close", "volume"}

# Only fixed codes cross the diagnostic boundary. Never emit an exception
# message originating in the adapter, provider, filesystem, or input data.
REASONS = frozenset({
    "WINDOW_DENIED", "SYMBOL_DENIED", "OPT_IN_REQUIRED", "UNSAFE_DIRECTORY",
    "LOCK_UNAVAILABLE", "ADAPTER_UNAVAILABLE", "EMPTY_HISTORY",
    "INVALID_COUNT", "INVALID_TIMESTAMP", "INVALID_BAR", "INVALID_NUMBER",
    "RAW_INVALID_BAR",
    "INVALID_OHLC", "INVALID_VOLUME", "INSUFFICIENT_SPAN", "STALE_HISTORY",
    "OVERSIZED_BARS", "PUBLICATION_REJECTED", "INTERNAL_FAILURE",
})


class CaptureRejected(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def failure_reason(exc: Exception) -> str:
    if type(exc) is CaptureRejected and type(exc.reason) is str and exc.reason in REASONS:
        return exc.reason
    return "INTERNAL_FAILURE"


def build_snapshot(rows, captured: int, symbol: str = "SPY", period: str = "5d") -> dict:
    long_window = period in ("6mo", "2y")
    archive_window = period == "2y"
    if period not in ("5d", "6mo", "2y") or (long_window and symbol not in LONG_SYMBOLS):
        raise CaptureRejected("WINDOW_DENIED", "window denied")
    if type(symbol) is not str or symbol not in ALLOWED_SYMBOLS:
        raise CaptureRejected("SYMBOL_DENIED", "symbol denied")
    if type(captured) is not int or captured <= 0:
        raise CaptureRejected("INVALID_TIMESTAMP", "invalid capture clock")
    if type(rows) is list and not rows:
        raise CaptureRejected("EMPTY_HISTORY", "invalid history")
    if type(rows) is not list or not (440 if archive_window else 100 if long_window else 1) <= len(rows) <= (560 if archive_window else 160 if long_window else 5):
        raise CaptureRejected("INVALID_COUNT", "invalid history")
    previous = 0
    for row in rows:
        if type(row) is not dict or set(row) != FIELDS:
            raise CaptureRejected("INVALID_BAR", "invalid bar")
        ts = row["timestamp"]
        if type(ts) is not int or not previous < ts <= captured or ts < captured - (760 if archive_window else 200 if long_window else 14)*86400:
            raise CaptureRejected("INVALID_TIMESTAMP", "invalid timestamp")
        o, h, l, c, v = (row[k] for k in ("open", "high", "low", "close", "volume"))
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in (o,h,l,c,v)):
            raise CaptureRejected("INVALID_NUMBER", "invalid number")
        if min(o,h,l,c) <= 0 or l > min(o,c) or h < max(o,c) or h < l:
            raise CaptureRejected("INVALID_OHLC", "invalid OHLC")
        if not 0 <= v <= 9007199254740991 or int(v) != v:
            raise CaptureRejected("INVALID_VOLUME", "invalid volume")
        previous = ts
    if long_window and rows[0]["timestamp"] > captured - (680 if archive_window else 140)*86400:
        raise CaptureRejected("INSUFFICIENT_SPAN", "short history span")
    if previous < captured - 7*86400:
        raise CaptureRejected("STALE_HISTORY", "stale history")
    raw = json.dumps(rows, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(raw) > (180000 if archive_window else 49152 if long_window else 16384):
        raise CaptureRejected("OVERSIZED_BARS", "oversized bars")
    return {"schema": "YAHOO_HISTORY_SNAPSHOT_V1",
            "provider": "Yahoo Finance via original yfinance",
            "symbol": symbol, "period": period, "interval": "1d",
            "adjustment": "AUTO_ADJUST_TRUE_BACK_ADJUST_FALSE",
            "captured_at_unix": captured,
            "bars_base64": base64.b64encode(raw).decode("ascii"),
            "bars_sha256": hashlib.sha256(raw).hexdigest()}


def capture(directory: Path, symbol: str = "SPY", period: str = "5d") -> None:
    long_window = period in ("6mo", "2y")
    archive_window = period == "2y"
    if period not in ("5d", "6mo", "2y") or (long_window and symbol not in LONG_SYMBOLS):
        raise CaptureRejected("WINDOW_DENIED", "window denied")
    ack = os.environ.get("FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK")
    if type(symbol) is not str or symbol not in ALLOWED_SYMBOLS:
        raise CaptureRejected("SYMBOL_DENIED", "symbol denied")
    if (archive_window and ack != ARCHIVE_ACK) or (period == "6mo" and ack != DUAL_ACK) or (not long_window and ack not in (MULTI_ACK, DUAL_ACK) and not (ack == ACK and symbol == "SPY")):
        raise CaptureRejected("OPT_IN_REQUIRED", "explicit opt-in required")
    try:
        private_directory(directory)
        if long_window or symbol != "SPY":
            directory = directory / ("archive-2y-" + symbol if archive_window else "long-" + symbol if long_window else symbol)
            private_directory(directory)
    except (OSError, ValueError):
        raise CaptureRejected("UNSAFE_DIRECTORY", "unsafe directory") from None
    try:
        lock = os.open(directory / ".capture.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    except OSError:
        raise CaptureRejected("LOCK_UNAVAILABLE", "unsafe lock") from None
    try:
        st = os.fstat(lock)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1:
            raise CaptureRejected("LOCK_UNAVAILABLE", "unsafe lock")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise CaptureRejected("LOCK_UNAVAILABLE", "capture lock unavailable") from None
        # Import only after opt-in and private-directory checks. The original
        # adapter owns adjustment semantics and provider conversion.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fincept-qt" / "scripts"))
        try:
            import yfinance_data as original
            original._NET_TIMEOUT = 6.0
            rows = original.get_historical_period(symbol, period, "1d", strict_research=True)
        except Exception:
            raise CaptureRejected("ADAPTER_UNAVAILABLE", "original adapter unavailable") from None
        if type(rows) is dict and rows == {"error": "RESEARCH_RAW_INVALID_BAR"}:
            raise CaptureRejected("RAW_INVALID_BAR", "invalid unrounded provider bar")
        snapshot = build_snapshot(rows, int(time.time()), symbol, period)
        try:
            publish(directory, snapshot)
        except (OSError, ValueError):
            raise CaptureRejected("PUBLICATION_REJECTED", "publication rejected") from None
        print("FINCEPT_F2_HISTORY_CAPTURE_OK", "symbol="+symbol, "bars="+str(len(rows)),
              "captured_at_unix="+str(snapshot["captured_at_unix"]),
              "sha256="+snapshot["bars_sha256"])
    finally:
        os.close(lock)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", required=True, type=Path)
    parser.add_argument("--symbol", default="SPY", choices=sorted(ALLOWED_SYMBOLS))
    parser.add_argument("--period", default="5d", choices=("5d", "6mo", "2y"))
    args = parser.parse_args()
    try:
        capture(args.inbox, args.symbol, args.period)
    except Exception as exc:
        # Never print provider error strings, cookies, headers or prices.
        print("FINCEPT_F2_HISTORY_CAPTURE_UNAVAILABLE", "reason="+failure_reason(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
