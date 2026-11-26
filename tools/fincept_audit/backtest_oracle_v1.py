"""Independent exact-arithmetic oracle for a long-only signal backtest.

Written from the execution model the ORIGINAL Fincept VectorBT provider states
in its own `assumptions` block, NOT from its code path: no numpy, no pandas,
no floats. Every price is a decimal string turned into a `Fraction`, so the
oracle has no rounding of its own and any disagreement with the provider is
a real difference, not float noise.

Model (TOOL-01 scope):
  * SMA crossover. `above[t]` is true only when both averages exist and
    fast > slow. Entry signal on a False->True edge, exit on True->False.
  * `next_open`: a signal on the close of bar t fills at the OPEN of bar t+1.
    `same_close`: it fills at the close of bar t (look-ahead, comparison only).
  * Buy fills at price*(1+slippage), sell at price*(1-slippage); commission is
    a fraction of the filled notional on each leg.
  * Sizing `percent`: fraction of the cash-affordable size. `fixed`: currency
    amount capped at cash.
  * A position still open on the last bar is closed at the last close, with
    exit costs, so equity and the trade list agree.

Out of scope and refused: stops, kelly, vol_target, risk sizing, shorts,
multi-asset. A synthetic fixture is NOT market data; nothing here estimates
edge, and no output is a trading signal.
"""
from __future__ import annotations

from fractions import Fraction
import math

SCHEMA = "kairos_fincept_backtest_oracle_v1"
# A fast/slow gap smaller than this could flip under float rounding inside
# the provider; such a fixture cannot decide who is right, so it is refused.
MIN_CROSS_MARGIN = Fraction(1, 10**6)
EPOCH_2024 = 1704067200  # 2024-01-01T00:00:00Z
DAY = 86400


class OracleRefused(ValueError):
    """The request or fixture is outside what this oracle can decide."""


def synthetic_candles(bars: int = 160, drift_cents: int = 5, wave: float = 6.0,
                      wave_period: float = 9.0, base: float = 100.0):
    """Deterministic synthetic daily OHLCV with two-decimal prices as strings.

    Shape only: a drift plus a sine wave so that an SMA crossover trades a few
    times. It encodes no market behaviour.
    """
    if not 30 <= bars <= 2000:
        raise OracleRefused("BARS_OUT_OF_RANGE")
    rows = []
    for i in range(bars):
        close = round(base + drift_cents * i / 100 + wave * math.sin(i / wave_period), 2)
        open_ = round(close - 0.3 + 0.2 * math.sin(i / 5), 2)
        rows.append({
            "t": EPOCH_2024 + DAY * i,
            "o": f"{open_:.2f}",
            "h": f"{max(open_, close) + 0.8:.2f}",
            "l": f"{min(open_, close) - 0.9:.2f}",
            "c": f"{close:.2f}",
            "v": 10000 + i,
        })
    return rows


def _dec(value, name: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise OracleRefused("NON_DECIMAL_INPUT:" + name)
    try:
        number = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise OracleRefused("NON_DECIMAL_INPUT:" + name) from exc
    return number


def _validate_candles(candles):
    if not isinstance(candles, list) or len(candles) < 30:
        raise OracleRefused("TOO_FEW_BARS")
    opens, closes, times = [], [], []
    for row in candles:
        if not isinstance(row, dict):
            raise OracleRefused("MALFORMED_BAR")
        o, c = _dec(row.get("o"), "o"), _dec(row.get("c"), "c")
        h, low = _dec(row.get("h"), "h"), _dec(row.get("l"), "l")
        if min(o, c, h, low) <= 0 or h < max(o, c) or low > min(o, c):
            raise OracleRefused("INCONSISTENT_OHLC")
        t = row.get("t")
        if isinstance(t, bool) or not isinstance(t, int):
            raise OracleRefused("NON_INTEGER_TIMESTAMP")
        if times and t <= times[-1]:
            raise OracleRefused("NON_INCREASING_TIMESTAMPS")
        opens.append(o)
        closes.append(c)
        times.append(t)
    return times, opens, closes


def sma_cross_signals(closes, fast: int, slow: int):
    """Return (entries, exits, min_margin) from exact rolling means."""
    if isinstance(fast, bool) or isinstance(slow, bool) or not (
            isinstance(fast, int) and isinstance(slow, int)) or not 1 <= fast < slow:
        raise OracleRefused("INVALID_SMA_PERIODS")
    if slow >= len(closes):
        raise OracleRefused("SLOW_PERIOD_EXCEEDS_HISTORY")
    above, margin = [], None
    for i in range(len(closes)):
        if i + 1 < slow:
            above.append(False)
            continue
        fast_ma = sum(closes[i + 1 - fast:i + 1], Fraction(0)) / fast
        slow_ma = sum(closes[i + 1 - slow:i + 1], Fraction(0)) / slow
        gap = abs(fast_ma - slow_ma)
        margin = gap if margin is None else min(margin, gap)
        above.append(fast_ma > slow_ma)
    if margin is None or margin < MIN_CROSS_MARGIN:
        raise OracleRefused("AMBIGUOUS_CROSSOVER_MARGIN")
    entries = [False] + [above[i] and not above[i - 1] for i in range(1, len(above))]
    exits = [False] + [above[i - 1] and not above[i] for i in range(1, len(above))]
    return entries, exits, margin


def simulate(candles, *, fast: int, slow: int, initial_capital="100000",
             commission="0", slippage="0", sizing_mode: str = "percent",
             sizing_value="100", execution: str = "next_open") -> dict:
    """Exact long-only simulation. All monetary results are Fractions."""
    times, opens, closes = _validate_candles(candles)
    capital = _dec(initial_capital, "initial_capital")
    fee_rate = _dec(commission, "commission")
    slip = _dec(slippage, "slippage")
    size_value = _dec(sizing_value, "sizing_value")
    if capital <= 0 or not 0 <= fee_rate < Fraction(1, 10) or not 0 <= slip < Fraction(1, 10):
        raise OracleRefused("INVALID_CAPITAL_OR_COSTS")
    if execution not in ("next_open", "same_close"):
        raise OracleRefused("UNSUPPORTED_EXECUTION")
    if sizing_mode == "percent":
        if not 0 < size_value <= 100:
            raise OracleRefused("INVALID_PERCENT_SIZING")
    elif sizing_mode == "fixed":
        if size_value <= 0:
            raise OracleRefused("INVALID_FIXED_SIZING")
    else:
        raise OracleRefused("UNSUPPORTED_SIZING_MODE")

    entries, exits, margin = sma_cross_signals(closes, fast, slow)
    next_bar = execution == "next_open"
    cash, shares = capital, Fraction(0)
    entry_price = entry_fee = Fraction(0)
    entry_bar = 0
    total_fees = Fraction(0)
    trades, equity = [], []
    pending = None

    def buy(bar, raw):
        nonlocal cash, shares, entry_price, entry_fee, entry_bar, total_fees
        price = raw * (1 + slip)
        affordable = cash / (price * (1 + fee_rate))
        if sizing_mode == "percent":
            size = affordable * size_value / 100
        else:
            size = min(size_value, cash) / (price * (1 + fee_rate))
        size = min(size, affordable)
        if size <= 0:
            return
        fee = size * price * fee_rate
        cash -= size * price + fee
        total_fees += fee
        shares, entry_price, entry_fee, entry_bar = size, price, fee, bar

    def sell(bar, raw, reason):
        nonlocal cash, shares, total_fees
        price = raw * (1 - slip)
        fee = shares * price * fee_rate
        total_fees += fee
        pnl = (price - entry_price) * shares - entry_fee - fee
        trades.append({
            "entry_bar": entry_bar, "exit_bar": bar,
            "entry_time": times[entry_bar], "exit_time": times[bar],
            "entry_price": entry_price, "exit_price": price, "size": shares,
            "pnl": pnl, "fees": entry_fee + fee, "exit_reason": reason,
        })
        cash += shares * price - fee
        shares = Fraction(0)

    for i in range(len(closes)):
        if next_bar:
            if pending == "exit" and shares > 0:
                sell(i, opens[i], "signal")
            elif pending == "entry" and shares == 0:
                buy(i, opens[i])
            pending = None
            if shares > 0:
                if exits[i]:
                    pending = "exit"
            elif entries[i]:
                pending = "entry"
        else:
            if shares > 0:
                if exits[i]:
                    sell(i, closes[i], "signal")
            elif entries[i]:
                buy(i, closes[i])
        equity.append(cash + shares * closes[i])

    if shares > 0:
        sell(len(closes) - 1, closes[-1], "end_of_data")
        equity[-1] = cash

    return {
        "schema": SCHEMA,
        "source_kind": "SYNTHETIC_FIXTURE_NOT_MARKET_DATA",
        "bars": len(closes),
        "times": times,
        "equity": equity,
        "trades": trades,
        "final_capital": equity[-1],
        "total_fees": total_fees,
        "total_return": equity[-1] / capital - 1,
        "min_cross_margin": margin,
        "entry_signals": sum(entries),
        "exit_signals": sum(exits),
    }
