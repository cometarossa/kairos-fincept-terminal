"""Explicit, local-only single Screener attempt; no provider or broker client.
The host must independently admit the fixed request and transaction mounts.
A fresh transaction directory is authority-sensitive: never recreate it for a retry.
"""
import json
import os
import secrets
import socket
import stat
import struct
import sys
import time
from pathlib import Path

ACK = "FINCEPT_SCREENER_SINGLE_ATTEMPT_V1"
SCOPE = "FINCEPT_PUBLIC_SCREENER_ON_DEMAND_V1"
STATUSES = frozenset({"CAPTURE_OK", "CAPTURE_UNAVAILABLE", "COOLDOWN", "BUSY",
                      "DENIED", "DISABLED", "HISTORY_PRIORITY"})


def _private_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        s = os.fstat(fd)
        if s.st_uid != os.geteuid() or stat.S_IMODE(s.st_mode) != 0o700:
            raise ValueError("unsafe directory")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _socket_stat(fd):
    s = os.stat("request.sock", dir_fd=fd, follow_symlinks=False)
    if not stat.S_ISSOCK(s.st_mode) or s.st_uid != os.geteuid() or stat.S_IMODE(s.st_mode) != 0o600:
        raise ValueError("unsafe socket")
    return s.st_dev, s.st_ino, s.st_uid, s.st_mode


def _write_once(fd, name, obj):
    f = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600, dir_fd=fd)
    with os.fdopen(f, "wb") as out:
        out.write(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("ascii"))
        out.flush()
        os.fsync(out.fileno())
    os.fsync(fd)


def _peer_allowed(cred):
    # PID can be zero when the peer is outside this PID namespace. It is not
    # an authentication factor. The independently admitted private socket
    # mount and matching UID/GID are required; same-UID host compromise is
    # outside this boundary.
    _, uid, gid = struct.unpack("3i", cred)
    return uid == os.geteuid() and gid == os.getegid()


def _exchange(fd, identity, raw):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(3)
        # Resolve through the opened directory, not a replaceable pathname.
        conn.connect(f"/proc/self/fd/{fd}/request.sock")
        if not _peer_allowed(conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))):
            raise ValueError("unexpected peer")
        if _socket_stat(fd) != identity:
            raise ValueError("socket replaced")
        conn.sendall(raw)
        conn.shutdown(socket.SHUT_WR)
        deadline = time.monotonic() + 52
        reply = bytearray()
        while len(reply) <= 64:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("reply deadline")
            conn.settimeout(remaining)
            chunk = conn.recv(65 - len(reply))
            if not chunk:
                break
            reply.extend(chunk)
        if len(reply) > 64 or not reply.endswith(b"\n") or reply.count(b"\n") != 1:
            raise ValueError("invalid reply")
        status = bytes(reply[:-1]).decode("ascii")
        if status not in STATUSES:
            raise ValueError("unknown reply")
        return status


def _run(request_dir, attempt_dir):
    request_fd = attempt_fd = None
    try:
        request_fd = _private_dir(request_dir)
        attempt_fd = _private_dir(attempt_dir)
        entries = set(os.listdir(attempt_fd))
        if "attempt.json" in entries:
            return "ALREADY_ATTEMPTED"
        if entries:
            return "PRECHECK_DENIED"
        identity = _socket_stat(request_fd)
        now = int(time.time())
        if now <= 0:
            return "PRECHECK_DENIED"
        req = {"scope": SCOPE, "screen_id": "day_gainers",
               "request_id": secrets.token_hex(16), "issued_at_unix": now}
        try:
            _write_once(attempt_fd, "attempt.json", req)
        except FileExistsError:
            return "ALREADY_ATTEMPTED"
        except OSError:
            # File may have been created before a durability failure. Do not send.
            return "ATTEMPT_UNCERTAIN"
        try:
            status = _exchange(request_fd, identity, json.dumps(req, separators=(",", ":")).encode("ascii"))
        except (OSError, ValueError, UnicodeError, struct.error):
            status = "ATTEMPT_UNCERTAIN"
        try:
            _write_once(attempt_fd, "result.json", {"request_id": req["request_id"],
                        "status": status, "automatic_retry": False})
        except OSError:
            return "RESULT_UNCERTAIN"
        return status
    except (OSError, ValueError, OverflowError):
        return "PRECHECK_DENIED"
    finally:
        for fd in (attempt_fd, request_fd):
            if fd is not None:
                os.close(fd)


def main():
    if (len(sys.argv) != 1 or os.environ.get("FINCEPT_SCREENER_ONCE_ACK") != ACK
            or os.geteuid() == 0 or sys.platform != "linux"
            or any(k.startswith(("IG_", "BROKER_")) for k in os.environ)
            or set(os.listdir("/sys/class/net")) != {"lo"}):
        print("FINCEPT_SCREENER_ONCE_DISABLED")
        return 2
    status = _run(Path("/request"), Path("/attempt"))
    print("FINCEPT_SCREENER_ONCE_" + status)
    # CAPTURE_OK is only the supervisor result, not verified market evidence.
    return 0 if status == "CAPTURE_OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
