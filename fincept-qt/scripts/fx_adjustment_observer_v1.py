"""Scope observation to one synchronous history call in an isolated capture child.

No network, repair, alternate request, or persistence.
"""
from contextlib import contextmanager
import threading
import pandas as pd
from fx_adjustment_origin_v1 import classify_order_origin, UNKNOWN


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


class Observation:
    def __init__(self):
        self.calls = 0
        self.before = self.after = None
        self.closed = False
        self.restored = False

    def classify(self, returned, *, failure_position, reason):
        if not self.closed or not self.restored or self.calls != 1 or threading.active_count() != 1:
            return UNKNOWN
        return classify_order_origin(self.before, self.after, frame_rows(returned),
                                     failure_position=failure_position, reason=reason)


@contextmanager
def observe_once(utils):
    """Only for a single-threaded disposable QA child, not a shared daemon."""
    obs = Observation()
    if threading.active_count() != 1 or threading.current_thread() is not threading.main_thread():
        obs.closed = True
        yield obs
        return
    original = utils.auto_adjust
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
        yield obs
    finally:
        if utils.auto_adjust is wrapper:
            utils.auto_adjust = original
            obs.restored = True
        obs.closed = True
