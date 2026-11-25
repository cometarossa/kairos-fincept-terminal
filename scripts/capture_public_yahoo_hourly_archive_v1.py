"""Archive-only original Fincept EURUSD 1y/1h capture; not a live MCP inbox.

One explicit caller invocation, no scheduler, fallback, retries or broker.
Run only in the separately admitted bounded Yahoo-only network environment.
Provider timestamps and adjusted prices are not independently attested.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import time

from capture_public_cnbc_rss_f2_v1 import private_directory

SCHEMA = "FINCEPT_YAHOO_HOURLY_ARCHIVE_V1"
ACK = "EURUSD_ONE_YEAR_HOURLY_ARCHIVE_V1"
SYMBOL = "EURUSD=X"
FILENAME = "eurusd-1y-h1.archive.json"
MAX_RAW = 1_400_000
MAX_ENVELOPE = 2_000_000
FIELDS = {"timestamp", "open", "high", "low", "close", "volume"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def validate_bars(rows, captured):
    if type(captured) is not int or captured <= 0:
        raise ValueError("INVALID_CAPTURE_CLOCK")
    if type(rows) is not list or not 5000 <= len(rows) <= 6500:
        raise ValueError("INSUFFICIENT_OR_OVERSIZED_COVERAGE")
    previous = 0
    for row in rows:
        if type(row) is not dict or set(row) != FIELDS:
            raise ValueError("INVALID_BAR")
        ts = row["timestamp"]
        if (type(ts) is not int or ts % 3600 or not previous < ts <= captured
                or ts < captured - 380 * 86400
                or (previous and ts - previous > 96 * 3600)):
            raise ValueError("INVALID_HOURLY_TIMESTAMP_OR_GAP")
        o, h, l, c, v = (row[k] for k in ("open", "high", "low", "close", "volume"))
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in (o, h, l, c, v)):
            raise ValueError("INVALID_NUMBER")
        if min(o, h, l, c) <= 0 or not l <= min(o, c) <= max(o, c) <= h:
            raise ValueError("INVALID_OHLC")
        if not 0 <= v <= 9007199254740991 or int(v) != v:
            raise ValueError("INVALID_VOLUME")
        previous = ts
    if previous - rows[0]["timestamp"] < 300 * 86400 or previous < captured - 7 * 86400:
        raise ValueError("INSUFFICIENT_SPAN_OR_STALE")


def build_archive(rows, captured):
    validate_bars(rows, captured)
    raw = _canonical(rows)
    if len(raw) > MAX_RAW:
        raise ValueError("OVERSIZED_ARCHIVE")
    envelope = {
        "schema": SCHEMA, "symbol": SYMBOL, "period": "1y", "interval": "1h",
        "provider": "Yahoo Finance via original yfinance",
        "adjustment": "AUTO_ADJUST_TRUE_BACK_ADJUST_FALSE",
        "captured_at_unix": captured, "rows": len(rows),
        "bars_sha256": hashlib.sha256(raw).hexdigest(),
        "bars_base64": base64.b64encode(raw).decode("ascii"),
        "classification": "RETROSPECTIVE_PUBLIC_EXPLORATORY",
        "research_only": True, "market_as_of_verified": False,
        "completed_bars_attested": False, "scientific_claim": False,
        "execution_authority": False, "broker_calls": 0,
    }
    encoded = _canonical(envelope)
    if len(encoded) > MAX_ENVELOPE:
        raise ValueError("OVERSIZED_ENVELOPE")
    return encoded


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_KEY")
        result[key] = value
    return result


def inspect_archive(encoded, expected_sha256):
    if type(encoded) is not bytes or not 0 < len(encoded) <= MAX_ENVELOPE:
        raise ValueError("INVALID_ENVELOPE_SIZE")
    if hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise ValueError("ARCHIVE_HASH_MISMATCH")
    env = json.loads(encoded, object_pairs_hook=_unique)
    raw = base64.b64decode(env["bars_base64"], validate=True)
    if len(raw) > MAX_RAW or hashlib.sha256(raw).hexdigest() != env["bars_sha256"]:
        raise ValueError("BARS_HASH_MISMATCH")
    rows = json.loads(raw, object_pairs_hook=_unique)
    # Exact canonical reconstruction checks all schema/authority fields,
    # unknown fields, count, provenance labels and canonical representation.
    if build_archive(rows, env["captured_at_unix"]) != encoded:
        raise ValueError("ARCHIVE_CONTRACT_MISMATCH")
    return rows


def capture(directory: Path):
    if os.environ.get("FINCEPT_PUBLIC_HOURLY_ARCHIVE_ACK") != ACK:
        raise ValueError("OPT_IN_REQUIRED")
    private_directory(directory)
    destination = directory / FILENAME
    if destination.exists() or destination.is_symlink():
        raise ValueError("ARCHIVE_ALREADY_EXISTS")
    # Create an exclusive reservation before any provider import/call.
    fd = os.open(directory / ".hourly-archive.lock",
                 os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    tmp = None
    try:
        if destination.exists() or destination.is_symlink():
            raise ValueError("ARCHIVE_ALREADY_EXISTS")
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fincept-qt" / "scripts"))
        import yfinance_data as original
        original._NET_TIMEOUT = 6.0
        rows = original.get_historical_period(SYMBOL, "1y", "1h", strict_research=True)
        encoded = build_archive(rows, int(time.time()))
        digest = hashlib.sha256(encoded).hexdigest()
        inspect_archive(encoded, digest)
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".hourly-", delete=False) as out:
            tmp = Path(out.name)
            os.fchmod(out.fileno(), 0o400)
            out.write(encoded)
            out.flush()
            os.fsync(out.fileno())
        # Atomic no-clobber publication. A completed archive is never replaced.
        os.link(tmp, destination, follow_symlinks=False)
        tmp.unlink()
        tmp = None
        dir_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return {"sha256": digest, "rows": len(rows), "bytes": len(encoded)}
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
        os.close(fd)
        (directory / ".hourly-archive.lock").unlink(missing_ok=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = capture(args.archive_dir)
    except Exception:
        # Do not reveal provider diagnostics, paths or prices.
        print("FINCEPT_HOURLY_ARCHIVE_UNAVAILABLE")
        return 1
    print("FINCEPT_HOURLY_ARCHIVE_OK", json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
