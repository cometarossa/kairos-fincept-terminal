"""Shared in-memory sliding-window admission for existing Yahoo CONNECT handler.

Use one lock and one ledger for all servers. No DNS, socket, credentials or
provider access here. A quote lane may consume at most two of eight admissions
per 600s; history can consume all eight if no quotes. Count attempted
admissions (including rejected/malformed CONNECT), not successful requests.
A fresh ledger must start closed for a full window; do not reset budget on
restart. Not an execution or freshness authority.
"""
import collections
import math
import threading
import time

class SharedWindow:
    WINDOW = 600
    TOTAL = 8
    QUOTES = 2

    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._events = collections.deque()
        self._started = self._last = self._now()
        self._fault = False

    def _now(self):
        value = self._clock()
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("CLOCK_INVALID")
        return value

    def admit(self, lane):
        if type(lane) is not str or lane not in ("history", "quote"):
            return False
        with self._lock:
            try:
                now = self._now()
            except (ValueError, OverflowError):
                self._fault = True
                return False
            if now < self._last:
                self._fault = True
            self._last = now
            if self._fault or now - self._started < self.WINDOW:
                return False
            while self._events and self._events[0][0] <= now - self.WINDOW:
                self._events.popleft()
            if len(self._events) >= self.TOTAL:
                return False
            if lane == "quote" and sum(event[1] == "quote" for event in self._events) >= self.QUOTES:
                return False
            self._events.append((now,lane))
            return True
