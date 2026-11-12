"""Independent exact-Fraction Supertrend reversal oracle for isolated native QA.

Synthetic 200-bar impulse fixture, explicit bands/last-close rules, no trading.
"""
from __future__ import annotations

from fractions import Fraction as F

START = "// BEGIN GENERATED SUPERTREND REVERSAL ORACLE"
END = "// END GENERATED SUPERTREND REVERSAL ORACLE"
SAMPLES = (11, 12, 20, 35, 42, 55, 75, 85, 100, 115, 125, 150, 155, 165, 180, 200)


def fixture():
    out = []
    close = 10000
    for i in range(200):
        if i < 35:
            delta = 48 + 5 * (i % 3)
        elif i < 75:
            delta = -(85 + 7 * (i % 5))
        elif i < 115:
            delta = 110 + 5 * (i % 5)
        elif i < 155:
            delta = -(90 + 9 * (i % 4))
        else:
            delta = 75 + 3 * (i % 6)
        close += delta
        out.append((close - 15 + (i % 5) * 5,
                    close + 125 + (i % 4) * 7,
                    close - 135 - (i % 3) * 9,
                    close, 1000 + i))
    return out


def reference():
    rows = fixture()
    high = [F(r[1], 100) for r in rows]
    low = [F(r[2], 100) for r in rows]
    close = [F(r[3], 100) for r in rows]
    tr = [high[0] - low[0]]
    for i in range(1, len(rows)):
        tr.append(max(high[i] - low[i], abs(high[i] - close[i - 1]),
                      abs(low[i] - close[i - 1])))
    atr = [None] * len(rows)
    atr[9] = sum(tr[:10], F(0)) / 10
    for i in range(10, len(rows)):
        atr[i] = (2 * tr[i] + 9 * atr[i - 1]) / 11

    upper = [None] * len(rows)
    lower = [None] * len(rows)
    line = [None] * len(rows)
    direction = [None] * len(rows)
    for i in range(9, len(rows)):
        mid = (high[i] + low[i]) / 2
        up, lo = mid + 3 * atr[i], mid - 3 * atr[i]
        if i == 9:
            upper[i], lower[i], direction[i] = up, lo, 1
        else:
            upper[i] = min(up, upper[i - 1]) if close[i - 1] < upper[i - 1] else up
            lower[i] = max(lo, lower[i - 1]) if close[i - 1] > lower[i - 1] else lo
            if close[i] > upper[i - 1]:
                direction[i] = 1
            elif close[i] < lower[i - 1]:
                direction[i] = -1
            else:
                direction[i] = direction[i - 1]
        line[i] = lower[i] if direction[i] == 1 else upper[i]
    return [(line[i], direction[i]) for i in range(len(rows))]


def cpp_rows():
    a = reference()
    rows = [START, "static const ReversalExpected kReversals[] = {"]
    for bars in SAMPLES:
        now, prev = a[bars - 1], a[bars - 2]
        rows.append("    {%d, %.17g, %.17g, %d, %d}," % (
            bars, float(now[0]), float(prev[0]), now[1], prev[1]))
    rows += ["};", END]
    return "\n".join(rows) + "\n"


if __name__ == "__main__":
    rows = reference()
    swaps = [(i, rows[i][1]) for i in range(10, 200) if rows[i][1] != rows[i-1][1]]
    print("reversals", swaps)
    print(cpp_rows())
