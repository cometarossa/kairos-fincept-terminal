"""Exact reference values for Fincept's native C++ IndicatorEngine.

Standard library only. Every indicator is computed from its textbook
definition with `Fraction` arithmetic (60-digit `Decimal` for the one square
root, in Bollinger), on a fixture built from integer cents by a formula that
the C++ test repeats verbatim. Nothing is read from the engine's source at run
time and no float enters the reference.

`python tools/fincept_audit/indicator_reference_v1.py` prints the C++ table that
is pasted between the markers in
`tools/fincept_audit/qt_unit_harness/tst_indicator_engine_reference.cpp`; a
Python test keeps the two identical.

Definitions used (period in parentheses is what the test asks for):
  SMA(14), WMA(14, weights 1..n), EMA(14, seeded with the SMA of the first n
  values, k = 2/(n+1)), DEMA(10) = 2*E1 - E2, TEMA(10) = 3*E1 - 3*E2 + E3,
  RSI(14, Wilder), MACD(12, 26, 9), Stochastic %K(14) and %D = SMA(3) of %K,
  CCI(20, constant 0.015), Williams %R(14), MFI(14), ROC(10), Aroon(14),
  ATR(14, Wilder, first value the mean of TR[1..n]), Bollinger(20, 2,
  population deviation), Keltner(20, 1.5, EMA of true range), Donchian(20),
  OBV, CMF(20), cumulative VWAP, windowed volume change(10), Ichimoku(9, 26, 52).
`previous` is the same indicator one bar earlier.

Synthetic integers, not market data. A match says the C++ arithmetic follows
these definitions on this fixture; it says nothing about any strategy.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
import json

BARS = 120
SCHEMA = "kairos_fincept_indicator_reference_v1"
BEGIN = "// BEGIN GENERATED REFERENCE (tools/fincept_audit/indicator_reference_v1.py)"
END = "// END GENERATED REFERENCE"


def fixture(bars: int = BARS):
    """Integer-cent OHLCV. The C++ test builds the same numbers with the same formula."""
    rows = []
    for i in range(bars):
        close = 10000 + 9 * i + (((i * 37) % 23) - 11) * 15 + (((i * i) % 7) - 3) * 8
        open_ = close - 25 + (i % 6) * 10
        high = max(open_, close) + 20 + (i % 4) * 10
        low = min(open_, close) - 15 - (i % 3) * 10
        volume = 1000 + ((i * 53) % 200) + (i % 5) * 40
        rows.append((open_, high, low, close, volume))
    return rows


def _sma(values, n):
    out = [None] * len(values)
    start = next((i for i, v in enumerate(values) if v is not None), len(values))
    for i in range(start + n - 1, len(values)):
        out[i] = sum(values[i - n + 1:i + 1], Fraction(0)) / n
    return out


def _ema(values, n):
    out = [None] * len(values)
    start = next((i for i, v in enumerate(values) if v is not None), len(values))
    if len(values) - start < n:
        return out
    seed = start + n - 1
    out[seed] = sum(values[start:seed + 1], Fraction(0)) / n
    k = Fraction(2, n + 1)
    for i in range(seed + 1, len(values)):
        out[i] = (values[i] - out[i - 1]) * k + out[i - 1]
    return out


def _true_range(high, low, close):
    tr = [high[0] - low[0]]
    for i in range(1, len(close)):
        tr.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    return tr


def _sqrt(value: Fraction) -> Fraction:
    with localcontext() as ctx:
        ctx.prec = 60
        root = (Decimal(value.numerator) / Decimal(value.denominator)).sqrt()
    return Fraction(root)


def reference(bars: int = BARS):
    """Return [(indicator, params, key, current, previous)] with Fraction values."""
    rows = fixture(bars)
    o = [Fraction(r[0], 100) for r in rows]
    h = [Fraction(r[1], 100) for r in rows]
    low = [Fraction(r[2], 100) for r in rows]
    c = [Fraction(r[3], 100) for r in rows]
    v = [Fraction(r[4]) for r in rows]
    n = len(c)
    tp = [(h[i] + low[i] + c[i]) / 3 for i in range(n)]
    out = []

    def add(name, params, key, series):
        out.append((name, params, key, series[-1], series[-2]))

    add("SMA", {"period": 14}, "value", _sma(c, 14))
    add("EMA", {"period": 14}, "value", _ema(c, 14))
    add("WMA", {"period": 14}, "value",
        [None] * 13 + [sum((c[i - 13 + j] * (j + 1) for j in range(14)), Fraction(0)) / 105
                       for i in range(13, n)])
    e1 = _ema(c, 10)
    e2 = _ema(e1, 10)
    e3 = _ema(e2, 10)
    add("DEMA", {"period": 10}, "value",
        [None if e2[i] is None else 2 * e1[i] - e2[i] for i in range(n)])
    add("TEMA", {"period": 10}, "value",
        [None if e3[i] is None else 3 * e1[i] - 3 * e2[i] + e3[i] for i in range(n)])

    # RSI, Wilder smoothing.
    period = 14
    gains = [Fraction(0)] + [max(c[i] - c[i - 1], Fraction(0)) for i in range(1, n)]
    losses = [Fraction(0)] + [max(c[i - 1] - c[i], Fraction(0)) for i in range(1, n)]
    avg_gain = sum(gains[1:period + 1], Fraction(0)) / period
    avg_loss = sum(losses[1:period + 1], Fraction(0)) / period
    rsi = [None] * n
    rsi[period] = 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi[i] = 100 - 100 / (1 + avg_gain / avg_loss)
    add("RSI", {"period": 14}, "value", rsi)

    fast, slow = _ema(c, 12), _ema(c, 26)
    macd = [None if slow[i] is None else fast[i] - slow[i] for i in range(n)]
    signal = _ema(macd, 9)
    macd_params = {"fast": 12, "slow": 26, "signal": 9}
    add("MACD", macd_params, "line", macd)
    add("MACD", macd_params, "signal_line", signal)
    add("MACD", macd_params, "histogram",
        [None if signal[i] is None else macd[i] - signal[i] for i in range(n)])

    def window(series, i, length):
        return series[i - length + 1:i + 1]

    stoch_k = [None] * 13 + [
        (c[i] - min(window(low, i, 14))) / (max(window(h, i, 14)) - min(window(low, i, 14))) * 100
        for i in range(13, n)]
    stoch_params = {"k_period": 14, "d_period": 3}
    add("STOCHASTIC", stoch_params, "k", stoch_k)
    add("STOCHASTIC", stoch_params, "d", _sma(stoch_k, 3))

    tp_sma = _sma(tp, 20)
    cci = [None] * n
    for i in range(19, n):
        mean_dev = sum((abs(x - tp_sma[i]) for x in window(tp, i, 20)), Fraction(0)) / 20
        cci[i] = (tp[i] - tp_sma[i]) / (Fraction(15, 1000) * mean_dev)
    add("CCI", {"period": 20}, "value", cci)

    add("WILLIAMS_R", {"period": 14}, "value", [None] * 13 + [
        (max(window(h, i, 14)) - c[i]) / (max(window(h, i, 14)) - min(window(low, i, 14))) * -100
        for i in range(13, n)])

    mfi = [None] * n
    for end in range(14, n):
        positive = sum((tp[i] * v[i] for i in range(end - 13, end + 1) if tp[i] > tp[i - 1]), Fraction(0))
        negative = sum((tp[i] * v[i] for i in range(end - 13, end + 1) if tp[i] < tp[i - 1]), Fraction(0))
        mfi[end] = 100 - 100 / (1 + positive / negative)
    add("MFI", {"period": 14}, "value", mfi)

    add("ROC", {"period": 10}, "value",
        [None] * 10 + [(c[i] - c[i - 10]) / c[i - 10] * 100 for i in range(10, n)])

    aroon_up, aroon_down = [None] * n, [None] * n
    for end in range(14, n):
        highs, lows = h[end - 14:end + 1], low[end - 14:end + 1]
        # bars since the most recent highest high / lowest low in the 15-bar window
        since_high = min(14 - j for j, x in enumerate(highs) if x == max(highs))
        since_low = min(14 - j for j, x in enumerate(lows) if x == min(lows))
        aroon_up[end] = Fraction(14 - since_high, 14) * 100
        aroon_down[end] = Fraction(14 - since_low, 14) * 100
    add("AROON", {"period": 14}, "up", aroon_up)
    add("AROON", {"period": 14}, "down", aroon_down)

    tr = _true_range(h, low, c)
    atr = [None] * n
    atr[14] = sum(tr[1:15], Fraction(0)) / 14
    for i in range(15, n):
        atr[i] = (atr[i - 1] * 13 + tr[i]) / 14
    add("ATR", {"period": 14}, "value", atr)

    mid = _sma(c, 20)
    boll = {key: [None] * n for key in ("upper", "middle", "lower", "width", "pct_b")}
    for i in range(19, n):
        deviation = _sqrt(sum(((x - mid[i]) ** 2 for x in window(c, i, 20)), Fraction(0)) / 20)
        upper, lower = mid[i] + 2 * deviation, mid[i] - 2 * deviation
        boll["upper"][i], boll["middle"][i], boll["lower"][i] = upper, mid[i], lower
        boll["width"][i] = (upper - lower) / mid[i]
        boll["pct_b"][i] = (c[i] - lower) / (upper - lower)
    boll_params = {"period": 20, "std_dev": 2.0}
    for key in ("upper", "middle", "lower", "width", "pct_b"):
        add("BOLLINGER", boll_params, key, boll[key])

    kelt_mid, kelt_range = _ema(c, 20), _ema(tr, 20)
    kelt_params = {"period": 20, "multiplier": 1.5}
    add("KELTNER", kelt_params, "upper",
        [None if kelt_mid[i] is None else kelt_mid[i] + Fraction(3, 2) * kelt_range[i] for i in range(n)])
    add("KELTNER", kelt_params, "middle", kelt_mid)
    add("KELTNER", kelt_params, "lower",
        [None if kelt_mid[i] is None else kelt_mid[i] - Fraction(3, 2) * kelt_range[i] for i in range(n)])

    add("DONCHIAN", {"period": 20}, "upper", [None] * 19 + [max(window(h, i, 20)) for i in range(19, n)])
    add("DONCHIAN", {"period": 20}, "lower", [None] * 19 + [min(window(low, i, 20)) for i in range(19, n)])

    obv = [Fraction(0)]
    for i in range(1, n):
        obv.append(obv[-1] + (v[i] if c[i] > c[i - 1] else -v[i] if c[i] < c[i - 1] else 0))
    add("OBV", {}, "value", obv)

    cmf = [None] * n
    for i in range(19, n):
        flow = sum((((c[j] - low[j]) - (h[j] - c[j])) / (h[j] - low[j]) * v[j]
                    for j in range(i - 19, i + 1)), Fraction(0))
        cmf[i] = flow / sum(window(v, i, 20), Fraction(0))
    add("CMF", {"period": 20}, "value", cmf)

    vwap = []
    numerator = denominator = Fraction(0)
    for i in range(n):
        numerator += tp[i] * v[i]
        denominator += v[i]
        vwap.append(numerator / denominator)
    add("VWAP", {}, "value", vwap)

    add("VOL_WIN_CHG", {"window": 10}, "value", [None] * 19 + [
        (sum(window(v, i, 10), Fraction(0)) / sum(window(v, i - 10, 10), Fraction(0)) - 1) * 100
        for i in range(19, n)])

    def midpoint(i, length):
        return (max(window(h, i, length)) + min(window(low, i, length))) / 2

    ichi_params = {"tenkan": 9, "kijun": 26, "senkou": 52}
    tenkan = [None] * 51 + [midpoint(i, 9) for i in range(51, n)]
    kijun = [None] * 51 + [midpoint(i, 26) for i in range(51, n)]
    add("ICHIMOKU", ichi_params, "tenkan_sen", tenkan)
    add("ICHIMOKU", ichi_params, "kijun_sen", kijun)
    add("ICHIMOKU", ichi_params, "senkou_a",
        [None if tenkan[i] is None else (tenkan[i] + kijun[i]) / 2 for i in range(n)])
    add("ICHIMOKU", ichi_params, "senkou_b", [None] * 51 + [midpoint(i, 52) for i in range(51, n)])

    # `o` is part of the fixture contract even though no indicator here reads it.
    assert len(o) == n and all(value is not None for row in out for value in row[3:])
    return out


def cpp_table(bars: int = BARS) -> str:
    """The generated block, markers included, exactly as it must appear in the C++ test."""
    lines = [BEGIN, "// bars=%d  schema=%s" % (bars, SCHEMA),
             "static const Expected kExpected[] = {"]
    for name, params, key, current, previous in reference(bars):
        text = json.dumps(params, sort_keys=True, separators=(",", ":")).replace('"', '\\"')
        lines.append('    {"%s", "%s", "%s", %s, %s},' % (
            name, text, key, repr(float(current)), repr(float(previous))))
    lines += ["};", END]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(cpp_table(), end="")
