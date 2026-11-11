"""Third leg: the real VectorBT library against the exact oracle.

Fincept's "VectorBT" provider no longer calls vectorbt for the simulation; it
uses its own numpy loop. This module asks the installed vectorbt package
(`Portfolio.from_signals`) to simulate the same fills, so the oracle is also
checked against an independent, widely used implementation.

Limits: only all-in sizing (vectorbt `size=inf`) is compared, and an open
final position is not force-closed by vectorbt, so such scenarios are refused.
Requires `vectorbt` (Fincept pins 0.28.2 with plotly<6). Synthetic input only.
"""
from __future__ import annotations

from fractions import Fraction

try:
    from tools.fincept_audit import backtest_oracle_v1 as oracle
except ImportError:  # pragma: no cover - direct execution
    import backtest_oracle_v1 as oracle


class ReferenceRefused(ValueError):
    pass


def vectorbt_equity(candles, *, fast: int, slow: int, initial_capital="100000",
                    commission="0", slippage="0", execution: str = "next_open"):
    """Return (equity list of floats, trade count, vectorbt version)."""
    import numpy as np
    import pandas as pd
    import vectorbt as vbt

    times, opens, closes = oracle._validate_candles(candles)
    entries, exits, _ = oracle.sma_cross_signals(closes, fast, slow)
    if execution == "next_open":
        # A signal on the close of t is an order at the open of t+1.
        entry_fill = [False] + entries[:-1]
        exit_fill = [False] + exits[:-1]
        price = [float(x) for x in opens]
    elif execution == "same_close":
        entry_fill, exit_fill = entries, exits
        price = [float(x) for x in closes]
    else:
        raise ReferenceRefused("UNSUPPORTED_EXECUTION")
    index = pd.to_datetime(times, unit="s")
    portfolio = vbt.Portfolio.from_signals(
        close=pd.Series([float(x) for x in closes], index=index),
        entries=pd.Series(entry_fill, index=index),
        exits=pd.Series(exit_fill, index=index),
        price=pd.Series(price, index=index),
        size=np.inf,
        fees=float(Fraction(str(commission))),
        slippage=float(Fraction(str(slippage))),
        init_cash=float(Fraction(str(initial_capital))),
        freq="1D",
    )
    if int(portfolio.trades.open.count()) != 0:
        raise ReferenceRefused("OPEN_FINAL_POSITION_NOT_COMPARABLE")
    return ([float(x) for x in portfolio.value().to_numpy()],
            int(portfolio.trades.closed.count()), str(vbt.__version__))
