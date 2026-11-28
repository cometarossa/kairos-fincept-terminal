"""Scope observation to one synchronous history call in an isolated capture child.

No network, repair, alternate request, or persistence.
"""
from contextlib import contextmanager
import threading
import datetime as dt
import math
from zoneinfo import ZoneInfo
import pandas as pd
from fx_adjustment_origin_v1 import classify_order_origin, UNKNOWN, PREEXISTING

DECODED = "DECODED_QUOTE_OHLC_ORDER"


def frame_rows(frame):
    try:
        cols = ("Open", "High", "Low", "Close")
        if (type(frame) is not pd.DataFrame or not 1 <= len(frame) <= 160
                or type(frame.index) is not pd.DatetimeIndex
                or frame.index.tz is None or frame.index.hasnans
                or not frame.columns.is_unique
                or any(str(frame[k].dtype) != "float64" for k in cols)):
            return None
        return tuple((int(ts.value), *(float(x) for x in values))
                     for ts, values in zip(frame.index, frame[list(cols)].itertuples(index=False, name=None)))
    except Exception:
        return None


def decoded_quote_rows(data):
    """Bounded immutable snapshot at parse_quotes entry, not HTTP wire bytes."""
    try:
        if type(data) is not dict:
            return None
        meta = data["meta"]
        if (type(meta) is not dict or meta.get("symbol") != "EURUSD=X"
                or meta.get("instrumentType") != "CURRENCY"
                or meta.get("dataGranularity") != "1d"):
            return None
        tz = meta["exchangeTimezoneName"]
        if type(tz) is not str or not 1 <= len(tz) <= 64:
            return None
        zone = ZoneInfo(tz)
        timestamps = data["timestamp"]
        quotes = data["indicators"]["quote"]
        if (type(timestamps) is not list or not 1 <= len(timestamps) <= 160
                or type(quotes) is not list or len(quotes) != 1
                or type(quotes[0]) is not dict):
            return None
        columns = tuple(quotes[0][key] for key in ("open", "high", "low", "close"))
        if any(type(col) is not list or len(col) != len(timestamps) for col in columns):
            return None
        rows = []
        previous = None
        for stamp, *prices in zip(timestamps, *columns):
            if type(stamp) is not int or any(
                    type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                    or float(v) != v for v in prices):
                return None
            day = dt.datetime.fromtimestamp(stamp, zone).date()
            if previous is not None and day <= previous:
                return None
            rows.append((day, *prices))
            previous = day
        return tz, tuple(rows)
    except Exception:
        return None


def decoded_matches_before(decoded, before):
    """Require full exact daily lineage, no subset/duplicate/nearest matching."""
    try:
        if decoded is None or before is None:
            return False
        tz, rows = decoded
        mapped = tuple((pd.Timestamp(ts, unit="ns", tz="UTC").tz_convert(tz).date(), *prices)
                       for ts, *prices in before)
        return len(rows) == len(mapped) and rows == mapped
    except Exception:
        return False


class Observation:
    def __init__(self):
        self.calls = 0
        self.parse_calls = 0
        self.decoded = None
        self.parse_restored = False
        self.before = self.after = None
        self.closed = False
        self.restored = False

    def classify(self, returned, *, failure_position, reason):
        if not self.closed or not self.restored or self.calls != 1 or threading.active_count() != 1:
            return UNKNOWN
        origin = classify_order_origin(self.before, self.after, frame_rows(returned),
                                       failure_position=failure_position, reason=reason)
        if (origin == PREEXISTING and self.parse_restored and self.parse_calls == 1
                and decoded_matches_before(self.decoded, self.before)):
            return DECODED
        return origin


@contextmanager
def observe_once(utils):
    """Only for a single-threaded disposable QA child, not a shared daemon."""
    obs = Observation()
    if threading.active_count() != 1 or threading.current_thread() is not threading.main_thread():
        obs.closed = True
        yield obs
        return
    original = utils.auto_adjust
    original_parse = utils.parse_quotes
    def parse_wrapper(data, *args, **kwargs):
        obs.parse_calls += 1
        obs.decoded = decoded_quote_rows(data) if obs.parse_calls == 1 else None
        return original_parse(data, *args, **kwargs)
    def wrapper(frame, *args, **kwargs):
        obs.calls += 1
        if obs.calls == 1:
            obs.before = frame_rows(frame)
        else:
            obs.before = obs.after = None
        out = original(frame, *args, **kwargs)
        if obs.calls == 1:
            obs.after = frame_rows(out)
        return out
    utils.auto_adjust = wrapper
    try:
        utils.parse_quotes = parse_wrapper
        yield obs
    finally:
        if utils.parse_quotes is parse_wrapper:
            utils.parse_quotes = original_parse
            obs.parse_restored = True
        if utils.auto_adjust is wrapper:
            utils.auto_adjust = original
            obs.restored = True
        obs.closed = True
