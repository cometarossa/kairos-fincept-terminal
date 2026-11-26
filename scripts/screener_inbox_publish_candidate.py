"""Offline publication of already acquired original Screener results.
No provider client, request scheduler, relay modification or network.
Trusted caller must independently admit acquisition and the private directory.
"""
import base64
import fcntl
import hashlib
import json
import os
import secrets
import stat
from screener_snapshot_v1 import make_envelope

MAX = 32768


def unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("DUPLICATE_KEY")
        out[key] = value
    return out


def reject_constant(_):
    raise ValueError("INVALID_CONSTANT")


def decode(raw):
    env = json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)
    if type(env) is not dict or set(env) != {"schema", "payload_base64", "payload_sha256"} or env["schema"] != "FINCEPT_SCREENER_INBOX_V1":
        raise ValueError("INVALID_ENVELOPE")
    body = base64.b64decode(env["payload_base64"], validate=True)
    if not 0 < len(body) <= 16384 or base64.b64encode(body).decode("ascii") != env["payload_base64"] or hashlib.sha256(body).hexdigest() != env["payload_sha256"]:
        raise ValueError("INVALID_DIGEST")
    payload = json.loads(body, object_pairs_hook=unique, parse_constant=reject_constant)
    if type(payload) is not dict or payload.get("schema") != "FINCEPT_SCREENER_SNAPSHOT_V1" or type(payload.get("captured_at_unix")) is not int or payload["captured_at_unix"] <= 0:
        raise ValueError("INVALID_CAPTURE")
    return payload["captured_at_unix"], env["payload_sha256"]


def safe_file(fd):
    s = os.fstat(fd)
    if not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid() or stat.S_IMODE(s.st_mode) != 0o600 or s.st_nlink != 1:
        raise ValueError("UNSAFE_FILE")
    return s


def publish(raw, directory, *, now):
    """Fixed-name atomic publication under a private per-inbox lock.
    Only rejects replay against an existing receipt; not a persistent acquisition ledger.
    """
    if os.geteuid() == 0:
        return "DENIED"
    d = lock = None
    temp = None
    replaced = False
    try:
        envelope = make_envelope(raw, now=now)
        data = json.dumps(envelope, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        if len(data) > MAX:
            return "DENIED"
        cap, digest = decode(data)
        path = os.path.abspath(directory)
        if os.path.realpath(path) != path:
            return "DENIED"
        d = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        st = os.fstat(d)
        if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
            return "DENIED"
        lock = os.open(".publish.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=d)
        safe_file(lock)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "BUSY"
        try:
            fd = os.open("snapshot.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=d)
        except FileNotFoundError:
            fd = None
        if fd is not None:
            with os.fdopen(fd, "rb") as stream:
                st = safe_file(stream.fileno())
                if not 0 < st.st_size <= MAX:
                    return "DENIED"
                old = stream.read(MAX+1)
                if len(old) != st.st_size:
                    return "DENIED"
            old_cap, old_digest = decode(old)
            if old_cap > cap or (old_cap == cap and old_digest != digest):
                return "REPLAY_DENIED"
            if old_cap == cap:
                return "ALREADY_PUBLISHED"
        name = ".next-" + secrets.token_hex(16)
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=d)
        temp = name
        with os.fdopen(fd, "wb") as stream:
            safe_file(stream.fileno())
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, "snapshot.json", src_dir_fd=d, dst_dir_fd=d)
        temp = None
        replaced = True
        os.fsync(d)
        return "PUBLISHED"
    except (OSError, ValueError, TypeError, OverflowError, RecursionError, KeyError):
        return "PUBLICATION_UNCERTAIN_REVIEW_REQUIRED" if replaced else "DENIED"
    finally:
        if d is not None and temp is not None:
            try: os.unlink(temp, dir_fd=d)
            except OSError: pass
        if lock is not None: os.close(lock)
        if d is not None: os.close(d)
