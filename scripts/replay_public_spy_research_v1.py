"""Fixed archived public SPY replay, NOT a live or scientific admission tool.

Run from a trusted exact Fincept checkout, offline, with a caller-supplied
archive digest from the acquisition receipt. Never use protected datasets.
Original NumPy/pandas simulator; not external vectorbt, not IG economics.
"""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import sys

PINS = {
    "vbt_portfolio.py": "ba27a81d44ce6ebc1da9586b1b5cf0d49315e53b",
    "vbt_indicators.py": "be42d77309e9530a76daee0698fe3eb3347089a8",
    "vbt_strategies.py": "639d5294274385931c1ba0f64c4ad71a07afa5b1",
}
MAX_BYTES = 70000
INITIAL = 10000.0


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, "DUPLICATE_FIELD")
        result[k] = v
    return result


def decode(raw, expected):
    require(len(raw) <= MAX_BYTES, "OVERSIZE")
    s = json.loads(raw, object_pairs_hook=unique)
    require(type(s) is dict and s.get("schema") == "YAHOO_HISTORY_SNAPSHOT_V1"
            and s.get("provider") == "Yahoo Finance via original yfinance"
            and s.get("symbol") == "SPY" and s.get("period") == "6mo"
            and s.get("interval") == "1d"
            and s.get("adjustment") == "AUTO_ADJUST_TRUE_BACK_ADJUST_FALSE", "INPUT_CONTRACT")
    payload = base64.b64decode(s["bars_base64"], validate=True)
    require(len(payload) <= 49152 and digest(payload) == expected == s.get("bars_sha256"), "INPUT_HASH")
    rows = json.loads(payload, object_pairs_hook=unique)
    require(type(rows) is list and 100 <= len(rows) <= 160, "COUNT")
    captured = s.get("captured_at_unix")
    require(type(captured) is int and captured > 0, "CAPTURE_CLOCK")
    previous = 0
    for b in rows:
        require(type(b) is dict and set(b) == {"timestamp","open","high","low","close","volume"}, "BAR_SCHEMA")
        ts = b["timestamp"]
        require(type(ts) is int and previous < ts <= captured, "BAR_TIME")
        previous = ts
        vals = [b[k] for k in ("open","high","low","close")]
        require(all(type(v) in (int,float) and math.isfinite(v) and v > 0 for v in vals), "PRICE")
        o,h,l,c = vals
        require(l <= min(o,c) and h >= max(o,c) and h >= l, "OHLC")
        require(type(b["volume"]) is int and 0 <= b["volume"] <= 9007199254740991, "VOLUME")
    require(captured-200*86400 <= rows[0]["timestamp"] <= captured-140*86400
            and previous >= captured-7*86400, "SPAN")
    return rows, captured


def load_original():
    root = Path(__file__).resolve().parents[1] / "fincept-qt/scripts/Analytics/backtesting/vectorbt"
    for name, expected in PINS.items():
        data = (root / name).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(actual == expected, "ENGINE_PIN")
    sys.path.insert(0, str(root))
    from vbt_portfolio import build_portfolio
    from vbt_strategies import build_strategy_signals
    for name in PINS:
        require(Path(sys.modules[name[:-3]].__file__).resolve() == root / name, "ENGINE_ORIGIN")
    return build_portfolio, build_strategy_signals


def oracle(frame, entries, exits, cost):
    """Independent scalar cash/quantity reference, fixed next-open semantics."""
    cash, qty, pending, legs = INITIAL, 0., 0, 0
    values = []
    for i, row in enumerate(frame.itertuples()):
        if pending == 1:
            fill = row.open * (1+cost)
            qty = cash / (fill*(1+cost))
            cash = 0.
            legs += 1
        elif pending == -1:
            cash = qty*row.open*(1-cost)*(1-cost)
            qty = 0.
            legs += 1
        pending = -1 if qty and exits.iloc[i] else 1 if not qty and entries.iloc[i] else 0
        values.append(cash+qty*row.close)
    if qty:
        values[-1] = cash+qty*frame.close.iloc[-1]*(1-cost)*(1-cost)
        legs += 1
    return values, legs


def evaluate(build, frame, entries, exits, bps):
    import numpy as np
    c = bps/20000
    p = build(None, frame.close, entries, exits, initial_capital=INITIAL,
              request={"commission":c,"slippage":c,"execution":"next_open",
                       "positionSizing":"percent","positionSizeValue":100}, open_series=frame.open)
    expected, legs = oracle(frame, entries, exits, c)
    actual = p.value().to_numpy()
    require(len(actual) == len(expected) and np.isfinite(actual).all()
            and np.allclose(actual, expected, rtol=1e-10, atol=1e-8), "ORACLE_MISMATCH")
    require(p.trades.count == legs//2, "TRADE_COUNT")
    equity = np.r_[INITIAL,actual]
    return {"cost_bps_per_leg":bps, "return_pct":float(100*(actual[-1]/INITIAL-1)),
            "max_drawdown_pct":float(100*np.min(equity/np.maximum.accumulate(equity)-1)),
            "final_capital":float(actual[-1]), "legs":legs, "equity_checks":len(expected)}


def replay(raw, expected):
    rows, captured = decode(raw, expected)
    import pandas as pd
    import numpy as np
    build, signals = load_original()
    rows = rows[:-1]  # conservatively exclude potentially incomplete last bar
    df = pd.DataFrame(rows, index=pd.to_datetime([b["timestamp"] for b in rows],unit="s",utc=True))
    def cross(d):
        return signals(None,"sma_crossover",d.close,{"fastPeriod":20,"slowPeriod":50},d.high,d.low,d.volume)
    e,x = cross(df)
    for n in (75, min(100,len(df)-1),len(df)-1):
        a,b = cross(df.iloc[:n])
        require(a.equals(e.iloc[:n]) and b.equals(x.iloc[:n]),"PREFIX_CAUSALITY")
    d = df.iloc[75:]
    zero = pd.Series(False,index=d.index)
    hold = zero.copy()
    hold.iloc[0] = True
    results = []
    for bps in (0,10,25):
        for name,ent,ext in (("SMA20_50",e.loc[d.index],x.loc[d.index]),("BUY_HOLD",hold,zero),("CASH",zero,zero)):
            results.append(dict(strategy=name,**evaluate(build,d,ent,ext,bps)))
    result = {"schema":"fincept_archived_public_replay_v1","symbol":"SPY",
              "dataset_class":"RETROSPECTIVE_PUBLIC_EXPLORATORY","input_sha256":expected,
              "captured_at_unix":captured,"source_git_blobs":PINS,
              "numpy_version":np.__version__,"pandas_version":pd.__version__,
              "warmup":75,"evaluation_bars":len(d),"prefix_checks":3,
              "first_date":str(d.index[0].date()),"last_date":str(d.index[-1].date()),
              "initial_capital":INITIAL,"results":results,"decision":"HOLD_INSUFFICIENT_EVIDENCE",
              "scientific_claim":False,"market_as_of_verified":False,
              "execution_authority":False,"promotion_eligible":False,"broker_calls":0}
    result["receipt_sha256"] = digest(json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False).encode())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot",type=Path)
    parser.add_argument("--expected-sha256",required=True)
    args=parser.parse_args()
    with args.snapshot.open("rb") as fp:
        raw=fp.read(MAX_BYTES+1)
    print(json.dumps(replay(raw,args.expected_sha256),sort_keys=True,allow_nan=False))


if __name__ == "__main__":
    main()
