"""Independent exact non-SMA signal reference (synthetic QA only).

Momentum is a close/lagged-close ratio, Donchian uses the previous N
closes (not intraday highs/lows), Z-score uses sample variance and
threshold crossings. This does not certify performance on market data.
"""
from fractions import Fraction


def reference(closes, kind, period=20):
    if type(period) is not int or period < 2 or period >= len(closes):
        raise ValueError("invalid period")
    if any(type(x) is not Fraction or x <= 0 for x in closes):
        raise ValueError("invalid close")
    if kind not in ("momentum", "breakout", "mean_reversion"):
        raise ValueError("unknown strategy")
    entries, exits = [], []
    prev_low = prev_high = False
    for i, c in enumerate(closes):
        enter = leave = False
        if kind == "momentum" and i >= period:
            enter, leave = c > closes[i-period], c < closes[i-period]
        elif kind == "breakout" and i >= period:
            prior = closes[i-period:i]
            enter, leave = c > max(prior), c < min(prior)
        elif kind == "mean_reversion" and i >= period-1:
            w = closes[i-period+1:i+1]
            mean = sum(w)/period
            var = sum((x-mean)**2 for x in w)/(period-1)
            delta = c-mean
            # Explicit implementation convention for degenerate variance:
            # original indicator substitutes a unit denominator.
            if var < Fraction(1,10**20):
                var = Fraction(1)
            low = delta < 0 and delta**2 > 4*var
            high = delta > 0 and delta**2 > var
            enter, leave = low and not prev_low, high and not prev_high
            prev_low, prev_high = low, high
        entries.append(enter)
        exits.append(leave)
    return entries, exits


def simulate_fixed(candles, kind):
    """Fixed next-open, long-only, 100% cash, no stops or leverage."""
    from tools.fincept_audit.backtest_oracle_v1 import _validate_candles
    times, opens, closes = _validate_candles(candles)
    entries, exits = reference(closes, kind)
    initial = cash = Fraction(100000)
    fee, slip = Fraction(1,1000), Fraction(1,2000)
    position = Fraction(0)
    total_fees = Fraction(0)
    equity, trades = [], []
    def sell(i, price, reason):
        nonlocal cash, position, total_fees
        fill = price*(1-slip)
        proceeds = position*fill*(1-fee)
        exit_fee = position*fill*fee
        trades.append({"entry_time":times[start],"exit_time":times[i],
                       "entry_price":paid,"exit_price":fill,"size":position,
                       "pnl":proceeds-basis,"fees":entry_fee+exit_fee,"exit_reason":reason})
        cash += proceeds
        total_fees += exit_fee
        position = Fraction(0)
    for i, c in enumerate(closes):
        if i:
            if position and exits[i-1]:
                sell(i, opens[i], "signal")
            elif not position and entries[i-1]:
                paid = opens[i]*(1+slip)
                basis = cash
                position = cash/(paid*(1+fee))
                entry_fee = position*paid*fee
                total_fees += entry_fee
                cash = Fraction(0)
                start = i
        equity.append(cash+position*c)
    if position:
        sell(len(closes)-1, closes[-1], "end_of_data")
        equity[-1] = cash
    return {"bars":len(closes),"times":times,"equity":equity,"trades":trades,
            "final_capital":equity[-1],"total_fees":total_fees,
            "total_return":equity[-1]/initial-1}
