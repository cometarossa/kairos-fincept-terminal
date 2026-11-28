"""Offline-only transport contract: construct a request, inspect a simulated reply.

No network entry point, API key lookup, retries, or production import.
The only credential accepted here is a public synthetic fixture marker.
"""
from datetime import date
import json
from urllib.parse import urlsplit, parse_qsl
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from twelve_fx_research_schema_v1 import qualify, Rejected

FIXTURE_KEY = "OFFLINE_FIXTURE_NOT_A_KEY"
URL = "https://api.twelvedata.com/time_series"
MAX_BYTES = 262144
class TransportRejected(ValueError):
    pass

def plan(first_day, last_day):
    if (type(first_day) is not date or type(last_day) is not date
            or not 150 <= (last_day-first_day).days <= 190):
        raise TransportRejected("SCOPE_INVALID")
    req = requests.Request("GET", URL, params={
        "symbol":"EUR/USD", "interval":"1day", "start_date":first_day.isoformat(),
        "end_date":last_day.isoformat(), "outputsize":"160", "apikey":FIXTURE_KEY
    }, headers={"Accept":"application/json"})
    return req.prepare()

def transport_policy():
    """Configuration candidate, not an opened connection or authorization."""
    retry = Retry(total=0, connect=0, read=0, redirect=0, status=0, other=0)
    return HTTPAdapter(max_retries=retry, pool_connections=1, pool_maxsize=1)

def _unique_pairs(pairs):
    out={}
    for k,v in pairs:
        if k in out:
            raise TransportRejected("JSON_DUPLICATE_KEY")
        out[k]=v
    return out

def _constant(_):
    raise TransportRejected("JSON_INVALID")

def evaluate_fixture(status, content_type, chunks, *, first_day, last_day, completed_before):
    """Evaluate one fixture response; no HTTP client, no retry path.

    A future admitted transport must enforce a total wall-clock deadline,
    byte cap during streaming/decompression, fixed origin and TLS verification.
    """
    if type(status) is not int:
        raise TransportRejected("HTTP_INVALID")
    if status in (401,403):
        raise TransportRejected("AUTH_DENIED")
    if status == 429:
        raise TransportRejected("RATE_LIMITED")
    if 300 <= status <= 399:
        raise TransportRejected("REDIRECT_DENIED")
    if status != 200:
        raise TransportRejected("HTTP_UNAVAILABLE")
    if type(content_type) is not str or content_type.split(";",1)[0].strip().lower()!="application/json":
        raise TransportRejected("CONTENT_TYPE_DENIED")
    raw=bytearray()
    try:
        # Count also bounds zero-length chunks in a fixture. No live stream here.
        for n,chunk in enumerate(chunks):
            if n>=1024 or type(chunk) is not bytes:
                raise TransportRejected("BODY_INVALID")
            if len(chunk)>MAX_BYTES-len(raw):
                raise TransportRejected("BODY_TOO_LARGE")
            raw.extend(chunk)
    except TransportRejected:
        raise
    except Exception:
        raise TransportRejected("BODY_UNAVAILABLE") from None
    try:
        payload=json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_constant)
    except TransportRejected:
        raise
    except Exception:
        raise TransportRejected("JSON_INVALID") from None
    return qualify(payload,first_day=first_day,last_day=last_day,completed_before=completed_before)
