"""Predeclared retrospective allocation diagnostic; not investment evidence."""
import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path
import math
import sys

SCOPE="FINCEPT_TIINGO_TRAIN_ALLOCATION_DIAGNOSTIC_V1"
DATA_SHA="072e3668589c0773dfeeb27f31c84bfce9611836fb7f747768e5b07e69ba9c0e"
PLAN_SHA="5538fae40df87b354ec8a5ebe62e6e60fa709011d3cb665f2e58528bd30de641"
OPT_SHA="777dc53d6ef523939482428f0c9d12cc65b7cb3d21aadee7e952eb6113fb01e6"
ASSETS=("AAPL","JPM","XOM")
METHODS=("fixed_40_30_30","equal_weight","min_volatility","risk_parity","max_sharpe")


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def digest(x):
    return hashlib.sha256(x).hexdigest()


def require(ok):
    if not ok:
        raise ValueError("ALLOCATION_DIAGNOSTIC_DENIED")


def admit(raw,plan):
    require(type(raw) is bytes and 0<len(raw)<=200000 and digest(raw)==DATA_SHA)
    require(type(plan) is bytes and 0<len(plan)<=4096 and digest(plan)==PLAN_SHA)
    p=json.loads(plan)
    require(p["schema"]==SCOPE and p["methods"]==list(METHODS)
            and p["dataset_sha256"]==DATA_SHA and p["assets"]==list(ASSETS))
    doc=json.loads(raw)
    require(doc["source"]=="TIINGO_EOD" and set(doc["series"])==set(ASSETS))
    rows=[doc["series"][s] for s in ASSETS]
    dates=[[r["t"] for r in leg] for leg in rows]
    require(len(dates[0])==251 and dates[0]==dates[1]==dates[2]
            and all(a<b for a,b in zip(dates[0],dates[0][1:]))
            and all(1514764800<=t<1546300800 for t in dates[0]))
    closes=[[Fraction(r["c"]) for r in leg] for leg in rows]
    require(all(x>0 for leg in closes for x in leg))
    return [[b/a-1 for a,b in zip(leg,leg[1:])] for leg in closes]


def exact_moments(returns):
    n=len(returns[0])
    means=[sum(r)/n for r in returns]
    cov=[[sum((a-means[i])*(b-means[j]) for a,b in zip(x,y))*252/(n-1)
          for j,y in enumerate(returns)] for i,x in enumerate(returns)]
    return [float(x*252) for x in means],[[float(x) for x in row] for row in cov]


def metrics(w,mu,cov):
    r=sum(w[i]*mu[i] for i in range(3))
    cw=[sum(cov[i][j]*w[j] for j in range(3)) for i in range(3)]
    var=sum(w[i]*cw[i] for i in range(3))
    require(var>0)
    vol=math.sqrt(var)
    return r,vol,(r-.04)/vol,[100*w[i]*cw[i]/var for i in range(3)]


def independent_weights(method,mu,cov):
    import numpy as np
    # Enumerate every nonempty support of the three-asset simplex.
    if method in ("min_volatility","max_sharpe"):
        candidates=[]
        excess=mu-.04
        if method=="max_sharpe" and np.max(excess)<=0:
            # For nonpositive excess returns, triangle inequality bounds the
            # portfolio Sharpe by the best individual asset's Sharpe.
            return np.eye(3)[np.argmax(excess/np.sqrt(np.diag(cov)))]
        for size in (1,2,3):
            for ids in itertools.combinations(range(3),size):
                ix=list(ids)
                b=np.ones(size) if method=="min_volatility" else excess[ix]
                x=np.linalg.solve(cov[np.ix_(ix,ix)],b)
                if x.sum()<=0 or np.any(x< -1e-12):
                    continue
                w=np.zeros(3);w[ix]=x/x.sum()
                candidates.append(w)
        require(bool(candidates))
        if method=="min_volatility":
            return min(candidates,key=lambda w:float(w@cov@w))
        return max(candidates,key=lambda w:float(w@excess/math.sqrt(w@cov@w)))
    if method=="risk_parity":
        # Independent convex log-barrier coordinate descent, not SLSQP.
        x=np.ones(3)
        for _ in range(10000):
            prev=x.copy()
            for i in range(3):
                a=cov[i,i];b=sum(cov[i,j]*x[j] for j in range(3) if j!=i)
                x[i]=(-b+math.sqrt(b*b+4*a/3))/(2*a)
            if np.max(np.abs(x-prev))<1e-12:
                break
        w=x/x.sum()
        require(max(abs(z-100/3) for z in metrics(w,mu,cov)[3])<1e-7)
        return w
    return np.array([.4,.3,.3] if method=="fixed_40_30_30" else [1/3]*3)


def run(raw,plan):
    returns=admit(raw,plan)
    import numpy as np
    import pandas as pd
    import scipy
    require((np.__version__,pd.__version__,scipy.__version__)==("2.4.6","2.3.3","1.17.0"))
    source=Path(__file__).resolve().parents[2]/"fincept-qt/scripts/optimize_portfolio_weights.py"
    require(digest(source.read_bytes())==OPT_SHA)
    sys.path.insert(0,str(source.parent))
    import optimize_portfolio_weights as opt
    mu,cov=map(np.array,exact_moments(returns))
    panel=pd.DataFrame({s:[float(x) for x in r] for s,r in zip(ASSETS,returns)})
    a,b,n=opt.build_params(panel)
    require(n==3 and np.allclose(a,mu,rtol=0,atol=1e-12) and np.allclose(b,cov,rtol=0,atol=1e-12))
    out=[]
    for method in METHODS:
        expected=independent_weights(method,mu,cov)
        try:
            if method=="fixed_40_30_30":
                w=expected
            else:
                r=opt.run_strategy(method,a,b,3)
                require("error" not in r and r["methodology"]==method.upper())
                w=r["weights"]
                rr,v,s,_=metrics(w,mu,cov)
                require(max(abs(r[k]-z) for k,z in zip(("return","volatility","sharpe"),(rr,v,s)))<1e-10)
            require(np.all(np.isfinite(w)) and np.all(w>=0) and abs(w.sum()-1)<1e-8)
            require(np.max(np.abs(w-expected))<=2e-4)
            rr,v,s,risk=metrics(w,mu,cov)
            d=opt.risk_decomposition(w,b)
            require(np.max(np.abs(d["percentage"]-risk))<1e-7)
            out.append({"method":method,"status":"MATCHED_ORACLE","weights":w.tolist(),
                        "annualized_historical_mean":rr,"annualized_sample_volatility":v,
                        "historical_mean_sharpe":s,"risk_percent":risk})
        except (ValueError,TypeError,KeyError,ArithmeticError):
            out.append({"method":method,"status":"REJECTED_OR_UNAVAILABLE"})
    body={"schema":SCOPE,"dataset_sha256":DATA_SHA,"plan_sha256":PLAN_SHA,"optimizer_sha256":OPT_SHA,
          "assets":list(ASSETS),"return_observations":250,"dataset_class":"DEVELOPMENT_CONTAMINATED",
          "annualized_mean":mu.tolist(),"annualized_covariance":cov.tolist(),
          "correlation":(cov/np.outer(np.sqrt(np.diag(cov)),np.sqrt(np.diag(cov)))).tolist(),
          "results":out,"attempted":len(out),"matched":sum(r["status"]=="MATCHED_ORACLE" for r in out),
          "selection_authorized":False,"scientific_claim":False,"execution_authority":False,
          "promotion_eligible":False,"holdout_access":False,"broker_calls":0}
    return {**body,"receipt_sha256":digest(canonical(body))}


def main():
    if sys.argv[1:]!=["--fixed-train-allocation"]:
        return 2
    try:
        p=Path(__file__).with_name("tiingo_train_allocation_plan_v1.json")
        with p.open("rb") as f:plan=f.read(4097)
        out=run(sys.stdin.buffer.read(200001),plan)
        sys.stdout.buffer.write(canonical(out)+b"\n")
        return 0 if out["matched"]==out["attempted"] else 3
    except Exception:
        print("ALLOCATION_DIAGNOSTIC_UNAVAILABLE",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
