"""Offline, research-only input guard; not wired into Fincept or any trade path.

Validate only the OHLCV information available *through* a specified as-of bar.
A decision about indicator values requires a separate downstream contract.
"""
from __future__ import annotations

import numpy as np

PRICE_COLS = ("high", "low", "close")


def evaluate_window(df, *, asof_bar: int, lookback: int, volume_required: bool = False) -> dict:
    """Return explicit fail-closed status; never inspect future bars after asof_bar."""
    def result(ok: bool, reason: str) -> dict:
        return {"admissible": ok, "reason": reason}

    if (not isinstance(asof_bar, int) or isinstance(asof_bar, bool)
            or not isinstance(lookback, int) or isinstance(lookback, bool)
            or lookback < 2):
        return result(False, "INVALID_REQUEST")
    if not all(hasattr(df, attr) for attr in ("iloc", "columns", "index")):
        return result(False, "INVALID_INPUT")
    if asof_bar < 0 or asof_bar >= len(df) or asof_bar + 1 < lookback:
        return result(False, "INSUFFICIENT_HISTORY")
    required = PRICE_COLS + (("volume",) if volume_required else ())
    if not all(c in df.columns for c in required):
        return result(False, "MISSING_COLUMN")

    # Use only the trailing window ending at the requested time, *not* df.tail().
    window = df.iloc[asof_bar - lookback + 1:asof_bar + 1]
    if not window.index.is_unique or not window.index.is_monotonic_increasing:
        return result(False, "NON_MONOTONIC_INDEX")
    try:
        price = window.loc[:, PRICE_COLS].to_numpy(dtype=float)
        if not np.isfinite(price).all():
            return result(False, "NON_FINITE_PRICE")
        highs, lows, closes = price[:, 0], price[:, 1], price[:, 2]
        if np.any(highs < lows) or np.any(closes > highs) or np.any(closes < lows):
            return result(False, "INVALID_CANDLE")
        if np.all(highs == lows):
            return result(False, "DEGENERATE_RANGE")
        if np.all(closes == closes[0]):
            return result(False, "NO_PRICE_MOVEMENT")
        if volume_required:
            volumes = window["volume"].to_numpy(dtype=float)
            if not np.isfinite(volumes).all() or np.any(volumes < 0):
                return result(False, "INVALID_VOLUME")
            if not np.any(volumes > 0):
                return result(False, "NO_VOLUME")
    except (TypeError, ValueError, OverflowError):
        return result(False, "UNREADABLE_INPUT")
    return result(True, "OK")
