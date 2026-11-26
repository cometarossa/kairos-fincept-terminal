"""Original Fincept synthetic optimization fixture, no market or order authority."""
import hashlib
import json
from pathlib import Path
import sys

SCHEMA="FINCEPT_SYNTHETIC_OPTIMIZER_V1"
OPTIMIZER_SHA="777dc53d6ef523939482428f0c9d12cc65b7cb3d21aadee7e952eb6113fb01e6"
METHODS=("min_volatility","risk_parity","max_sharpe","equal_weight","max_return","target_return")


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def run():
    import numpy as np
    import scipy
    if (np.__version__,scipy.__version__)!=("2.4.6","1.17.0"):
        raise ValueError("unadmitted numerical runtime")
    source=Path(__file__).resolve().parents[2]/"fincept-qt/scripts/optimize_portfolio_weights.py"
    if hashlib.sha256(source.read_bytes()).hexdigest()!=OPTIMIZER_SHA:
        raise ValueError("unadmitted source")
    sys.path.insert(0,str(source.parent))
    import optimize_portfolio_weights as opt
    mu=np.array([.08,.12]);cov=np.diag([.04,.16])
    rows=[]
    for method in METHODS:
        r=opt.run_strategy(method,mu,cov,2)
        if "error" in r or r["strategy"]!=method or r["methodology"]!=method.upper():
            raise ValueError("optimizer unavailable")
        rows.append({"method":method,"weights":r["weights"].tolist(),
                     "return":r["return"],"volatility":r["volatility"],"sharpe":r["sharpe"]})
    frontier=opt.build_frontier(mu,cov,2,num_points=9)
    if len(frontier)!=9:
        raise ValueError("incomplete frontier")
    risk=opt.risk_decomposition(np.array([.9,.1]),np.array([[.04,-.03],[-.03,.09]]))
    risk={k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in risk.items()}
    body={"schema":SCHEMA,"optimizer_sha256":OPTIMIZER_SHA,"dataset_class":"SYNTHETIC_ONLY",
          "runtime":{"numpy":np.__version__,"scipy":scipy.__version__},
          "methods":rows,"frontier":frontier,"risk":risk,
          "scientific_claim":False,"promotion_eligible":False,"execution_authority":False,"broker_calls":0}
    return {**body,"receipt_sha256":hashlib.sha256(canonical(body)).hexdigest()}


def main():
    if sys.argv[1:]!=["--fixed-synthetic-optimizer"]:
        return 2
    try:
        sys.stdout.buffer.write(canonical(run())+b"\n")
        return 0
    except Exception:
        print("OPTIMIZER_FIXTURE_UNAVAILABLE",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
