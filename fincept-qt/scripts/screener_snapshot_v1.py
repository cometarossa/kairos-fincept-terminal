"""Pure candidate projection of original Fincept Screener output; no I/O.

First fixed research-only scope, not a provider capturer or native MCP service.
Refuse incomplete/ambiguous results instead of erasing original warnings.
"""
import math
import re

SYMBOL = re.compile(r"[A-Z0-9.^=_-]{1,32}\Z", re.ASCII)


def project(raw, *, now):
    if (type(raw) is not dict or type(now) is not int
            or raw.get('source') != 'Yahoo Finance screener'
            or raw.get('kind') != 'predefined' or raw.get('screen_id') != 'day_gainers'
            or type(raw.get('offset')) is not int or raw['offset'] != 0
            or raw.get('warnings') != []):
        raise ValueError('SCREENER_UNAVAILABLE')
    count, total, cap = (raw.get(k) for k in ('count', 'total', 'fetched_at'))
    if (any(type(x) is not int for x in (count, total, cap))
            or not 1 <= count <= 20 or total < count or not 0 < cap <= now < cap + 600
            or type(raw.get('rows')) is not list or len(raw['rows']) != count):
        raise ValueError('SCREENER_UNAVAILABLE')
    rows = []
    seen = set()
    for row in raw['rows']:
        if type(row) is not dict:
            raise ValueError('SCREENER_UNAVAILABLE')
        symbol, price, ccy, stamp, delay = (row.get(k) for k in ('symbol', 'price', 'currency', 'market_time', 'delay_min'))
        try:
            valid_price = type(price) in (int, float) and math.isfinite(price) and price > 0
        except OverflowError:
            valid_price = False
        if (type(symbol) is not str or SYMBOL.fullmatch(symbol) is None or symbol in seen
                or not valid_price or ccy != 'USD' or type(stamp) is not int or not 0 < stamp <= cap
                or type(delay) is not int or delay < 0):
            raise ValueError('SCREENER_UNAVAILABLE')
        seen.add(symbol)
        rows.append(dict(symbol=symbol, price=price, currency=ccy, market_time=stamp, delay_min=delay))
    return dict(schema='FINCEPT_SCREENER_SNAPSHOT_V1', source=raw['source'], screen_id=raw['screen_id'],
                count=count, total=total, captured_at_unix=cap, valid_until_unix=cap+600, rows=rows,
                research_only=True, market_as_of_verified=False, scientific_claim=False,
                execution_authority=False, broker_calls=0)


def make_envelope(raw, *, now):
    """Prepare a bounded ASCII envelope; caller owns admission and atomic publication."""
    import base64
    import hashlib
    import json
    payload = json.dumps(project(raw, now=now), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(payload) > 16384:
        raise ValueError("SCREENER_UNAVAILABLE")
    return {"schema": "FINCEPT_SCREENER_INBOX_V1",
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "payload_sha256": hashlib.sha256(payload).hexdigest()}
