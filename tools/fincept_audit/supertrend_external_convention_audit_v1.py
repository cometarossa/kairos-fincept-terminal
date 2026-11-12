"""External-convention Supertrend audit, strictly offline and synthetic.

TradingView documents: final bands based on their own previous bands, then
direction determined by previous active Supertrend band and CURRENT final bands.
Unlike Fincept's candidate, which tests BOTH PREVIOUS bands to flip either way.
ATR smoothing differs as well: compare EMA-like (same Fincept ATR) separately
from Wilder RMA. These are distinct *conventions*, not a proof of strategy alpha.

No network, market prices, broker actions or installation involved.
"""
from __future__ import annotations
from fractions import Fraction as F

from tools.fincept_audit import supertrend_reversal_reference_v1 as original

PERIOD = 10
FACTOR = 3


def make_fixture(kind="reversals"):
    if kind == "reversals":
        return original.fixture()
    if kind == "shock":
        rows = []
        close = 10000
        for i in range(200):
            delta = (220 if i % 31 < 8 else -150 if i % 31 < 16
                     else 85 if i % 31 < 23 else -45)
            close += delta
            span = 30 if i % 9 < 4 else 270
            rows.append((close - 10, close + span, close - span, close, 1000+i))
        return rows
    raise ValueError("unknown fixture")


def compute(rows, *, smoothing="ema", variant="tradingview", initial_dir=1):
    if len(rows) < PERIOD + 1:
        raise ValueError("insufficient fixture")
    high = [F(r[1], 100) for r in rows]
    low = [F(r[2], 100) for r in rows]
    close = [F(r[3], 100) for r in rows]
    tr = [high[0] - low[0]]
    for i in range(1, len(rows)):
        tr.append(max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1])))
    atr = [None] * len(rows)
    atr[PERIOD-1] = sum(tr[:PERIOD], F(0))/PERIOD
    for i in range(PERIOD, len(rows)):
        if smoothing == "ema":
            atr[i] = (2*tr[i]+(PERIOD-1)*atr[i-1])/(PERIOD+1)
        elif smoothing == "wilder":
            atr[i] = (tr[i]+(PERIOD-1)*atr[i-1])/PERIOD
        else:
            raise ValueError("unsupported smoothing")

    upper = [None] * len(rows)
    lower = [None] * len(rows)
    direction = [None] * len(rows)
    line = [None] * len(rows)
    for i in range(PERIOD-1,len(rows)):
        mid = (high[i]+low[i])/2
        bu = mid + FACTOR * atr[i]
        bl = mid - FACTOR * atr[i]
        if i == PERIOD-1:
            upper[i],lower[i],direction[i] = bu,bl,initial_dir
        else:
            if variant == "tradingview":
                upper[i] = bu if bu < upper[i-1] or close[i-1] > upper[i-1] else upper[i-1]
                lower[i] = bl if bl > lower[i-1] or close[i-1] < lower[i-1] else lower[i-1]
                if direction[i-1] == -1:
                    direction[i] = 1 if close[i] > upper[i] else -1
                else:
                    direction[i] = -1 if close[i] < lower[i] else 1
            elif variant == "candidate":
                upper[i] = min(bu,upper[i-1]) if close[i-1] < upper[i-1] else bu
                lower[i] = max(bl,lower[i-1]) if close[i-1] > lower[i-1] else bl
                if close[i] > upper[i-1]:
                    direction[i] = 1
                elif close[i] < lower[i-1]:
                    direction[i] = -1
                else:
                    direction[i] = direction[i-1]
            else:
                raise ValueError("unknown variant")
        line[i] = lower[i] if direction[i] == 1 else upper[i]
    return list(zip(line,direction))


def swaps(rows):
    return [(i, rows[i][1]) for i in range(PERIOD, len(rows))
            if rows[i][1] != rows[i-1][1]]


def diagnostics(kind):
    data = make_fixture(kind)
    cand = compute(data,smoothing="ema",variant="candidate",initial_dir=1)
    if kind=="reversals" and cand!=original.reference():
        raise AssertionError("independent candidate implementation disagrees with pinned Fraction reference")
    result = {}
    for smoothing, initial_dir, label in (
        ("ema",1,"tradingview_state_EMA_matched_seed"),
        ("wilder",1,"tradingview_state_Wilder_matched_seed"),
        ("wilder",-1,"tradingview_documented_down_initial"),
    ):
        target=compute(data,smoothing=smoothing,variant="tradingview",initial_dir=initial_dir)
        dir_diff = [i for i in range(PERIOD, len(cand)) if cand[i][1] != target[i][1]]
        line_diff = [i for i in range(PERIOD, len(cand)) if cand[i][0] != target[i][0]]
        result[label]={
            "direction_diff_count":len(dir_diff),
            "line_diff_count":len(line_diff),
            "first_direction_diff":dir_diff[:8],
            "candidate_flips":swaps(cand),
            "reference_flips":swaps(target),
        }
    return result


if __name__=="__main__":
    for kind in ("reversals","shock"):
        print(kind,diagnostics(kind))
