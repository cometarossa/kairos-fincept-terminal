#!/usr/bin/env python3
"""One bounded, explicit public CNBC capture for the original F2 RSS inbox.

Host-side only; not an MCP tool, market-time attestation, scheduler or broker.
The destination must already be a dedicated private directory owned by this uid.
The service consumes the atomic envelope through a read-only bind. Capture
failure never renews the previous envelope's absolute expiry.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

URL = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"
SCHEMA = "CNBC_SNAPSHOT_V1"
MAX_XML = 180_000


def build_snapshot(xml: bytes, captured: int) -> dict:
    if type(captured) is not int or captured <= 0 or not 0 < len(xml) <= MAX_XML:
        raise ValueError("invalid capture")
    decoded = xml.decode("utf-8-sig")
    if "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
        raise ValueError("unsafe XML")
    root = ET.fromstring(decoded)
    items = root.findall("./channel/item")
    if root.tag != "rss" or not 1 <= len(items) <= 100:
        raise ValueError("invalid RSS")
    recent = 0
    for item in items:
        try:
            date = parsedate_to_datetime(item.findtext("pubDate", ""))
            if date.tzinfo is None:
                continue
            age = captured - date.timestamp()
            link = urlsplit(item.findtext("link", ""))
            if (-300 <= age <= 86400 and item.findtext("title", "").strip()
                    and link.scheme == "https" and link.hostname in ("www.cnbc.com", "cnbc.com")
                    and link.username is None and link.password is None and link.port is None):
                recent += 1
        except (ValueError, TypeError, OverflowError):
            continue
    if not recent:
        raise ValueError("no eligible publisher dates")
    return {"schema": SCHEMA, "source_url": URL, "captured_at_unix": captured,
            "rss_sha256": hashlib.sha256(xml).hexdigest(),
            "rss_base64": base64.b64encode(xml).decode("ascii")}


def private_directory(directory: Path) -> None:
    if not directory.is_absolute() or directory.resolve(strict=True) != directory:
        raise ValueError("not canonical directory")
    st = directory.lstat()
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
            or stat.S_IMODE(st.st_mode) != 0o700 or os.geteuid() == 0):
        raise ValueError("unsafe inbox directory")


def publish(directory: Path, snapshot: dict) -> None:
    raw = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(raw) > 250000:
        raise ValueError("oversized envelope")
    private_directory(directory)
    previous = directory / "snapshot.json"
    if previous.exists() or previous.is_symlink():
        st = previous.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1
                or not 0 < st.st_size <= 250000):
            raise ValueError("unsafe previous envelope")
        with previous.open("rb") as existing:
            old = json.load(existing)
        if type(old.get("captured_at_unix")) is not int or old["captured_at_unix"] >= snapshot["captured_at_unix"]:
            raise ValueError("non-increasing capture clock")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".snapshot-", delete=False) as out:
            tmp = Path(out.name)
            os.fchmod(out.fileno(), 0o600)
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, previous)
        tmp = None
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def capture(directory: Path) -> None:
    private_directory(directory)
    lock_fd = os.open(directory / ".capture.lock",
                      os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        st = os.fstat(lock_fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1:
            raise ValueError("unsafe capture lock")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Fixed destination, no arbitrary URLs, redirects, proxy credentials,
        # user curl config or retries. Timeout and response size are bounded.
        with tempfile.TemporaryFile(dir=directory) as response:
            result = subprocess.run(
                ["curl", "-q", "--fail", "--silent", "--show-error",
                 "--proto", "=https", "--max-redirs", "0", "--retry", "0",
                 "--noproxy", "*", "--connect-timeout", "8", "--max-time", "25",
                 "--max-filesize", str(MAX_XML), "--header", "Accept: application/rss+xml, application/xml",
                 "--user-agent", "OriginalFincept-Kairos-ReadOnly-QA/1.0",
                 "--output", "-", "--write-out", "%{http_code}", URL],
                stdout=response, stderr=subprocess.DEVNULL, timeout=30,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, check=False)
            response.seek(0)
            raw = response.read(MAX_XML + 4)
        if result.returncode != 0 or len(raw) > MAX_XML + 3 or not raw.endswith(b"200"):
            raise ValueError("capture HTTP failure")
        snapshot = build_snapshot(raw[:-3], int(datetime.now(timezone.utc).timestamp()))
        publish(directory, snapshot)
        print("FINCEPT_F2_CAPTURE_OK", "captured_at_unix=" + str(snapshot["captured_at_unix"]),
              "sha256=" + snapshot["rss_sha256"])
    finally:
        os.close(lock_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", required=True, type=Path)
    args = parser.parse_args()
    try:
        capture(args.inbox)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, ET.ParseError):
        print("FINCEPT_F2_CAPTURE_UNAVAILABLE")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
