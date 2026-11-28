"""Offline-only experiment: exclusive durable attempt marker and child deadline.

No provider request, real credential, production import or automatic retry.
Only the fixed synthetic child in this directory may run.
"""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

class AttemptDenied(ValueError):
    pass

_MODES = frozenset(("success", "failure", "stall", "tls_success", "tls_rate_limit", "tls_invalid"))
_MARKER = b'{"scope":"OFFLINE_FIXTURE_ONLY","attempt":"CONSUMED"}\n'
_CHILD = Path(__file__).with_name("twelve_fx_attempt_child_qa_v1.py")

def once(directory, mode, *, deadline_seconds=1.0):
    if (type(mode) is not str or mode not in _MODES
            or type(deadline_seconds) not in (int,float)
            or not .1 <= deadline_seconds <= 3):
        raise AttemptDenied("SCOPE_DENIED")
    fd = None
    try:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(fd)
        if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700):
            raise AttemptDenied("DIRECTORY_DENIED")
        try:
            claim = os.open("attempt.json", os.O_WRONLY | os.O_CREAT |
                            os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        except FileExistsError:
            raise AttemptDenied("ATTEMPT_ALREADY_CONSUMED") from None
        try:
            with os.fdopen(claim,"wb") as stream:
                stream.write(_MARKER)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(fd)
        except OSError:
            # Never remove a partial or uncertain claim.
            raise AttemptDenied("ATTEMPT_STATE_UNCERTAIN") from None
        try:
            result = subprocess.run(
                [sys.executable, "-I", str(_CHILD), mode],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=deadline_seconds,
                check=False, env={"PATH":"/usr/bin:/bin","PYTHONDONTWRITEBYTECODE":"1","TWELVE_DATA_API_KEY":"OFFLINE_FIXTURE_NOT_A_KEY","HOME":"/tmp"})
        except subprocess.TimeoutExpired:
            return "DEADLINE_EXCEEDED"
        except OSError:
            return "CHILD_UNAVAILABLE"
        if mode.startswith("tls_"):
            return {0:"TLS_FIXTURE_SHAPE_ONLY", 20:"TLS_FIXTURE_RATE_LIMITED",
                    21:"TLS_FIXTURE_DATA_REJECTED"}.get(result.returncode,"TLS_FIXTURE_FAILED")
        return "FIXTURE_OK" if result.returncode == 0 else "FIXTURE_FAILED"
    except AttemptDenied:
        raise
    except OSError:
        raise AttemptDenied("ATTEMPT_STATE_UNAVAILABLE") from None
    finally:
        if fd is not None:os.close(fd)
