"""One fixed research capture, called only by a separately admitted supervisor.
No CLI, scheduling daemon, provider credentials, relay registration or direct egress.
"""
import os
import time
import stat
import math
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"fincept-qt"/"scripts"))
from screener_inbox_publish_candidate import publish

SCOPE = "FINCEPT_SCREENER_CAPTURE_CANDIDATE_V1"

def capture_once(*, scope=None, inbox, clock=time.time, mono=time.monotonic):
    # This is an inner worker, not a host or network admission decision.
    if type(scope) is not str or scope != SCOPE:
        return "DISABLED"
    try:
        if os.geteuid() == 0 or set(os.listdir("/sys/class/net")) != {"lo"}:
            return "ISOLATION_DENIED"
        if any(k.startswith(("IG_", "BROKER_")) for k in os.environ):
            return "ISOLATION_DENIED"
        path = os.path.abspath(inbox)
        if os.path.realpath(path) != path:
            return "INBOX_DENIED"
        st = os.lstat(path)
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or stat.S_IMODE(st.st_mode) != 0o700):
            return "INBOX_DENIED"
        before = int(clock())
        start = mono()
        if before <= 0 or not math.isfinite(start):
            return "CLOCK_DENIED"
        from screener_data import run_predefined
        raw = run_predefined("day_gainers", 20, 0)
        after = int(clock())
        end = mono()
        if (not math.isfinite(end) or not 0 <= end - start <= 45
                or after < before or after - before > 45):
            return "CLOCK_DENIED"
        if type(raw) is not dict or type(raw.get("fetched_at")) is not int:
            return "CAPTURE_DENIED"
        if not before <= raw["fetched_at"] <= after:
            return "CAPTURE_DENIED"
        return publish(raw, path, now=after)
    except Exception:
        # Never log raw provider errors or retry.
        return "CAPTURE_UNAVAILABLE"

def main():
    if len(sys.argv)!=1 or os.environ.get("FINCEPT_PUBLIC_SCREENER_CAPTURE_ACK")!=SCOPE:
        return 2
    if os.geteuid()==0 or set(os.listdir("/sys/class/net"))!={"lo"} or any(k.startswith(("IG_","BROKER_")) for k in os.environ):
        return 2
    proxy=os.environ.get("HTTPS_PROXY","")
    if not re.fullmatch(r"http://127[.]0[.]0[.]1:[0-9]{1,5}",proxy) or not 1<=int(proxy.rsplit(":",1)[1])<=65535:
        return 2
    if any(os.environ.get(k)!=proxy for k in ("HTTP_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy")) or any(os.environ.get(k)!="" for k in ("NO_PROXY","no_proxy")):
        return 2
    try:
        # The original Screener uses this same process-local YfData singleton.
        from yfinance.data import YfData
        YfData(proxy=proxy)
        result=capture_once(scope=SCOPE,inbox="/screener-inbox")
        return 0 if result in ("PUBLISHED","ALREADY_PUBLISHED") else 1
    except Exception:
        return 1
if __name__=="__main__":raise SystemExit(main())
