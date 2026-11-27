"""Bounded diagnostic classifier for a single strict FX history child.

Classify the *same* row at the yfinance adjustment boundary. No I/O,
provider calls, repair, tolerance, or change to the admission predicate.
The caller must supply the actual first strict-validator failure position.
"""
import math

UNKNOWN = "ADJUSTMENT_ORIGIN_UNVERIFIED"
PREEXISTING = "PRE_ADJUSTMENT_OHLC_ORDER"
INTRODUCED = "ADJUSTMENT_STAGE_OHLC_ORDER"


def _rows(frame):
    if type(frame) is not tuple or not 1 <= len(frame) <= 160:
        raise ValueError("coverage")
    previous = None
    for row in frame:
        if type(row) is not tuple or len(row) != 5:
            raise ValueError("row")
        ts, *prices = row
        if type(ts) is not int or (previous is not None and ts <= previous):
            raise ValueError("identity")
        if any((type(x) is not int and type(x) is not float) or not math.isfinite(x) or x <= 0
               for x in prices):
            raise ValueError("price")
        previous = ts
    return frame


def _ordered(row):
    _, o, h, l, c = row
    return l <= min(o, c) and h >= max(o, c) and h >= l


def classify_order_origin(before, adjusted, returned, *, failure_position, reason):
    """Fixed labels; unknown unless all three bounded series align exactly.

    PREEXISTING means the price ordering already failed immediately before
    auto_adjust; it does not attest raw wire data. INTRODUCED identifies the
    adjustment stage, not the numerical mechanism or the size of the error.
    Both outcomes leave the original strict rejection intact.
    """
    if type(reason) is not str or reason != "OHLC_ORDER" or type(failure_position) is not int:
        return UNKNOWN
    try:
        before, adjusted, returned = map(_rows, (before, adjusted, returned))
        if (len(before) != len(adjusted) or adjusted != returned
                or any(type(a) is not type(b) for ar, rr in zip(adjusted, returned)
                       for a, b in zip(ar, rr))
                or tuple(r[0] for r in before) != tuple(r[0] for r in adjusted)
                or not 0 <= failure_position < len(returned)
                or any(not _ordered(r) for r in returned[:failure_position])
                or _ordered(returned[failure_position])):
            return UNKNOWN
        return INTRODUCED if _ordered(before[failure_position]) else PREEXISTING
    except (ValueError, TypeError, OverflowError):
        return UNKNOWN

