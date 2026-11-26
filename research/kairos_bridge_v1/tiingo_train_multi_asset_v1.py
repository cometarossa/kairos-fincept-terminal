"""Pinned retrospective Tiingo TRAIN portfolio diagnostic, offline only.

Receives a single admitted export, never database access or caller parameters.
This is development compatibility QA, not the canonical scientific evaluator.
"""
from fractions import Fraction
import json
from pathlib import Path
import sys

from research.kairos_bridge_v1 import development_backtest_v1 as dev
from tools.fincept_audit import backtest_provider_probe_v1 as probe
from tools.fincept_audit import backtest_oracle_v1 as oracle
from tools.fincept_audit import backtest_metrics_oracle_v1 as metrics

SCOPE = "FINCEPT_TIINGO_TRAIN_MULTI_ASSET_DEVELOPMENT_V1"
PLAN = Path(__file__).with_name("tiingo_train_multi_asset_plan_v1.json")
PLAN_SHA = "d0d4b250b81871b4c92127b47b59445d36567fc60d0eb0e892a61e655eacae69"
DATA_SHA = "072e3668589c0773dfeeb27f31c84bfce9611836fb7f747768e5b07e69ba9c0e"
PROVENANCE_SHA = "ba7b1a6ccdc69a0636cc2ef6222acd5c9e5bd20ba6fd88fb90ccb90000153dff"
REQUEST_SHA = "bba6a94edb8b4f77e2a80f32b766d5e0949435cd6eb8408c0ca74aff950c39db"
RECEIPT_SHA = "0794573a8dc5e078a0c13c5c1e9c6d9f537cb09145b23a52fba75b5ea855dd71"
MAX_BYTES = 200000
SYMBOLS = ("AAPL","JPM","XOM")


def admit(raw, plan):
    dev.require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES and dev.digest(raw)==DATA_SHA)
    dev.require(type(plan) is bytes and 0 < len(plan) <= 4096 and dev.digest(plan)==PLAN_SHA)
    cfg=json.loads(plan,object_pairs_hook=dev.unique,parse_constant=dev.constant)
    dev.require(cfg["schema"]==SCOPE and cfg["assets"]==list(SYMBOLS)
                and cfg["weights"]==["0.4","0.3","0.3"]
                and cfg["start_inclusive"]=="2018-01-01" and cfg["end_exclusive"]=="2019-01-01"
                and all(cfg[k] is False for k in ("selection_authorized","scientific_claim","execution_authority","costs_verified","holdout_access")))
    doc=json.loads(raw,object_pairs_hook=dev.unique,parse_constant=dev.constant)
    dev.require(type(doc) is dict and set(doc)=={"schema","source","series","provenance_sha256"}
                and doc["schema"]=="FINCEPT_TIINGO_TRAIN_EXPORT_V1" and doc["source"]=="TIINGO_EOD"
                and doc["provenance_sha256"]==PROVENANCE_SHA)
    series=doc["series"]
    dev.require(type(series) is dict and set(series)==set(SYMBOLS))
    times=[]
    for sym in SYMBOLS:
        bars=series[sym]
        dev.require(type(bars) is list and len(bars)==251)
        for row in bars:
            dev.require(type(row) is dict and set(row)=={"t","o","h","l","c","v"}
                        and type(row["t"]) is int and 1514764800<=row["t"]<1546300800
                        and row["t"]%86400==0 and type(row["v"]) is int and row["v"]>=0
                        and all(type(row[k]) is str for k in ("o","h","l","c")))
        t,_,_=oracle._validate_candles(bars)
        times.append(t)
    dev.require(times[0]==times[1]==times[2])
    return cfg,series


def run_portfolio(raw, *, plan):
    cfg,series=admit(raw,plan)
    symbols=list(SYMBOLS)
    weights=list(map(Fraction,cfg["weights"]))
    capital=Fraction(cfg["initial_capital"])
    scenario={k:cfg[k] for k in ("fast","slow","commission","slippage","execution")}
    legs=[oracle.simulate(series[s],initial_capital=str(capital*w),**scenario)
          for s,w in zip(symbols,weights)]
    equity=[sum(x,Fraction(0)) for x in zip(*(leg["equity"] for leg in legs))]
    trades=[dict(t,symbol=sym) for sym,leg in zip(symbols,legs) for t in leg["trades"]]
    fees=sum((leg["total_fees"] for leg in legs),Fraction(0))
    expected={"bars":251,"times":legs[0]["times"],"equity":equity,"trades":trades,
              "final_capital":equity[-1],"total_fees":fees,"total_return":equity[-1]/capital-1,
              "provider_total_fees":fees}
    req=probe.build_request(series["AAPL"],scenario)
    req.update(symbols=symbols,weights=[float(w) for w in weights],startDate=cfg["start_inclusive"],
               endDate=cfg["end_exclusive"],brokerDataSource="TIINGO_ADJUSTED_TRAIN_DEVELOPMENT_ONLY",
               brokerCandles={s:[{"t":r["t"],"o":float(r["o"]),"h":float(r["h"]),
                                  "l":float(r["l"]),"c":float(r["c"]),"v":r["v"]} for r in series[s]]
                              for s in symbols})
    dev.require(dev.digest(dev.canonical(req))==REQUEST_SHA)
    run=probe.run_original_provider(Path(__file__).resolve().parents[2]/probe.BACKTESTING_RELATIVE,req)
    dev.require(type(run["network_attempts"]) is int and run["network_attempts"]==0)
    labels=probe.compare(run["response"],expected)
    dev.require(labels["provider_data_source"]==req["brokerDataSource"] and labels["provider_using_synthetic_data"] is False)
    met=metrics.metrics(equity,trades,capital,252,Fraction(0))
    probe.compare_metrics(run["response"],met)
    out={"schema":SCOPE,"manifest_sha256":PLAN_SHA,"dataset_sha256":DATA_SHA,"request_sha256":REQUEST_SHA,
         "bars_per_asset":251,"observations":753,"assets":symbols,"weights":[str(w) for w in weights],
         "return":float(expected["total_return"]),"final_capital":float(equity[-1]),"commission":float(fees),
         "provider_fees":run["response"]["data"]["statistics"]["totalFees"],"drawdown":float(met["max_drawdown"]),
         "trades":len(trades),"legs":{s:{"trades":len(l["trades"]),"return":float(l["total_return"]),
                                        "fees":float(l["total_fees"])} for s,l in zip(symbols,legs)},
         "status":"MATCHED_ORACLE","dataset_class":"DEVELOPMENT_CONTAMINATED",
         "selection_authorized":False,"scientific_claim":False,"costs_verified":False,
         "market_as_of_verified":False,"execution_authority":False,"promotion_eligible":False,
         "holdout_access":False,"broker_calls":0,"network_attempts":0}
    dev.require(dev.digest(dev.canonical(out))==RECEIPT_SHA)
    return {**out,"receipt_sha256":RECEIPT_SHA}


def main():
    if sys.argv[1:]!=["--fixed-tiingo-portfolio"]:
        return 2
    try:
        with PLAN.open("rb") as f:
            plan=f.read(4097)
        out=run_portfolio(sys.stdin.buffer.read(MAX_BYTES+1),plan=plan)
        sys.stdout.buffer.write(dev.canonical(out)+b"\n")
        return 0
    except Exception:
        print("TIINGO_PORTFOLIO_UNAVAILABLE",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
