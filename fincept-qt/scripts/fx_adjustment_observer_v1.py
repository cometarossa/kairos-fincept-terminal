"""Scope observation to one synchronous history call in an isolated capture child.

No network, repair, alternate request, or persistence.
"""
from contextlib import contextmanager
import threading
import inspect
import sys
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
        self.parse_linked = False
        self.before = self.after = None
        self.closed = False
        self.restored = False

    def classify(self, returned, *, failure_position, reason):
        if not self.closed or not self.restored or self.calls != 1 or threading.active_count() != 1:
            return UNKNOWN
        origin = classify_order_origin(self.before, self.after, frame_rows(returned),
                                       failure_position=failure_position, reason=reason)
        if (origin == PREEXISTING and self.parse_restored and self.parse_linked and self.parse_calls == 1
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
    try:
        from yfinance.scrapers.history import PriceHistory
        history_code = inspect.unwrap(PriceHistory.history).__code__
    except Exception:
        history_code = None
    parse_caller = None
    def parse_wrapper(data, *args, **kwargs):
        nonlocal parse_caller
        obs.parse_calls += 1
        parse_caller = None
        obs.decoded = None
        candidate = None
        caller = None
        try:
            caller = sys._getframe(1)
            local = caller.f_locals
            if (obs.parse_calls == 1 and obs.calls == 0
                    and caller.f_code is history_code
                    and local["data"]["chart"]["result"][0] is data
                    and local["self"].ticker == "EURUSD=X"
                    and local["params"]["interval"] == "1d"
                    and local["interval"] == "1d"
                    and not local["repair"]):
                candidate = decoded_quote_rows(data)
        except Exception:
            pass
        out = original_parse(data, *args, **kwargs)
        # Only a successfully returned parser result from the actual pinned
        # history frame can establish provenance. Retain the frame until
        # auto_adjust, then release it; no rows are persisted or logged.
        try:
            if candidate is not None and type(out) is pd.DataFrame:
                tz, rows = candidate
                cols = ["Open", "High", "Low", "Close"]
                index = out.index
                if (type(index) is pd.DatetimeIndex and index.tz is None
                        and not index.hasnans and out.columns.is_unique
                        and len(index) == len(rows)
                        and all(str(out[k].dtype) == "float64" for k in cols)
                        and tuple(int(t.value) for t in index) ==
                            tuple(t * 1000000000 for t in data["timestamp"])
                        and rows == tuple((t.date(), *prices) for t, prices in zip(
                            index.tz_localize("UTC").tz_convert(tz),
                            out[cols].itertuples(index=False, name=None)))):
                    obs.decoded = candidate
                    parse_caller = caller
        except Exception:
            pass
        return out
    def wrapper(frame, *args, **kwargs):
        nonlocal parse_caller
        obs.calls += 1
        if obs.calls == 1:
            obs.before = frame_rows(frame)
            try:
                caller = sys._getframe(1)
                obs.parse_linked = (parse_caller is not None
                                    and caller is parse_caller
                                    and caller.f_code is history_code
                                    and caller.f_locals.get("df") is frame)
            except Exception:
                obs.parse_linked = False
            finally:
                parse_caller = None
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
        parse_caller = None
        try:
            if getattr(utils, "parse_quotes", None) is parse_wrapper:
                utils.parse_quotes = original_parse
                obs.parse_restored = True
        except Exception:
            obs.parse_restored = False
        finally:
            try:
                if getattr(utils, "auto_adjust", None) is wrapper:
                    utils.auto_adjust = original
                    obs.restored = True
            except Exception:
                obs.restored = False
            finally:
                obs.closed = True
