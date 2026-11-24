#!/usr/bin/env python3
"""Single opt-in SPY 5d/1d capture via the original Fincept Yahoo adapter.

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
FIELDS = {"timestamp", "open", "high", "low", "close", "volume"}


def build_snapshot(rows, captured: int) -> dict:
    if type(captured) is not int or captured <= 0 or type(rows) is not list or not 1 <= len(rows) <= 5:
        raise ValueError("invalid history")
    previous = 0
    for row in rows:
        if type(row) is not dict or set(row) != FIELDS:
            raise ValueError("invalid bar")
        ts = row["timestamp"]
        if type(ts) is not int or not previous < ts <= captured or ts < captured - 14*86400:
            raise ValueError("invalid timestamp")
        o, h, l, c, v = (row[k] for k in ("open", "high", "low", "close", "volume"))
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in (o,h,l,c,v)):
            raise ValueError("invalid number")
        if min(o,h,l,c) <= 0 or l > min(o,c) or h < max(o,c) or h < l:
            raise ValueError("invalid OHLC")
        if not 0 <= v <= 9007199254740991 or int(v) != v:
            raise ValueError("invalid volume")
        previous = ts
    if previous < captured - 7*86400:
        raise ValueError("stale history")
    raw = json.dumps(rows, separators=(",", ":"), allow_nan=False).encode("ascii")
    return {"schema": "YAHOO_HISTORY_SNAPSHOT_V1",
            "provider": "Yahoo Finance via original yfinance",
            "symbol": "SPY", "period": "5d", "interval": "1d",
            "adjustment": "AUTO_ADJUST_TRUE_BACK_ADJUST_FALSE",
            "captured_at_unix": captured,
            "bars_base64": base64.b64encode(raw).decode("ascii"),
            "bars_sha256": hashlib.sha256(raw).hexdigest()}


def capture(directory: Path) -> None:
    if os.environ.get("FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK") != ACK:
        raise ValueError("explicit opt-in required")
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
        rows = original.get_historical_period("SPY", "5d", "1d")
        snapshot = build_snapshot(rows, int(time.time()))
        publish(directory, snapshot)
        print("FINCEPT_F2_HISTORY_CAPTURE_OK", "bars="+str(len(rows)),
              "captured_at_unix="+str(snapshot["captured_at_unix"]),
              "sha256="+snapshot["bars_sha256"])
    finally:
        os.close(lock)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", required=True, type=Path)
    args = parser.parse_args()
    try:
        capture(args.inbox)
    except Exception:
        # Never print provider error strings, cookies, headers or prices.
        print("FINCEPT_F2_HISTORY_CAPTURE_UNAVAILABLE")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
