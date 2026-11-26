"""
optimize_portfolio_weights.py — Portfolio optimization for Fincept Terminal.

Input (stdin JSON):
  {
    "symbols":        ["AAPL", "MSFT", "GOOGL"],
    "weights":        [0.4, 0.35, 0.25],       # current weights (fractions)
    "method":         "max_sharpe",             # see STRATEGIES below
    "returns_method": "mean_historical",        # ignored (scipy only for now)
    "risk_model":     "sample_covariance"       # ignored (scipy only for now)
  }

Output (stdout JSON):
  {
    "weights":                {"AAPL": 0.45, ...},   # optimal weights
    "expected_annual_return": 0.142,
    "annual_volatility":      0.178,
    "sharpe_ratio":           1.25,
    "strategy":               "max_sharpe",
    "frontier": [                                    # 40 points on efficient frontier
      {"volatility": 0.10, "return": 0.06, "sharpe": 0.20},
      ...
    ],
    "comparison": {                                  # all-methods comparison
      "max_sharpe":      {"weights": {...}, "return": ..., "volatility": ..., "sharpe": ...},
      "min_volatility":  {...},
      "risk_parity":     {...},
      "hrp":             {...},
      "equal_weight":    {...}
    }
  }

STRATEGIES (method field):
  max_sharpe        — Maximise Sharpe ratio (default)
  min_volatility    — Minimise portfolio standard deviation
  risk_parity       — Equal risk contribution per asset
  max_return        — Maximise expected return (fully invests in best asset)
  equal_weight      — 1/N allocation (no optimisation)
  hrp               — Hierarchical Risk Parity (inverse-variance proxy)
  target_return     — Efficient portfolio at 10% target return
  black_litterman   — BL with equal-weight market prior
"""
import sys
import json
import numpy as np


# ── Helpers ───────────────────────────────────────────────────────────────────

def convert_numpy(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        v = float(obj)
        return 0.0 if (v != v or v == float("inf") or v == float("-inf")) else v
    elif isinstance(obj, np.ndarray):
        return [convert_numpy(x) for x in obj]
    elif isinstance(obj, float):
        return 0.0 if (obj != obj or obj == float("inf") or obj == float("-inf")) else obj
    return obj


def fetch_price_data(symbols, period="1y"):
    import yfinance as yf
    import pandas as pd

    data = yf.download(symbols, period=period, interval="1d",
                       progress=False, auto_adjust=True)
    if data is None or data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        level0 = data.columns.get_level_values(0)
        if "Close" in level0:
            close = data["Close"]
        elif "Adj Close" in level0:
            close = data["Adj Close"]
        else:
            close = data.iloc[:, :len(symbols)]
    else:
        close = data[["Close"]] if "Close" in data.columns else data

    if not isinstance(close, pd.DataFrame):
        close = pd.DataFrame(close)

    if len(symbols) == 1 and list(close.columns) != symbols:
        close.columns = [symbols[0]]

    # Keep only requested symbols
    available = [s for s in symbols if s in close.columns]
    if not available:
        return None
    close = close[available].dropna(how="all")
    # A ticker yfinance could not price (delisted, mutual-fund code, bad suffix) comes
    # back as an all-NaN column. Left in, the main() pct_change().dropna() discards
    # EVERY row and the whole run fails with "Insufficient price history" because of
    # one holding. Drop such columns; main() derives `available` from what is left
    # and reports it in the "symbols" output key.
    close = close.dropna(axis=1, how="all")
    if close.shape[1] == 0:
        return None
    return close


# ── Core optimiser ────────────────────────────────────────────────────────────

def _validate_moments(mean_ret, cov, n):
    """Conservative numerical admission: strictly positive definite covariance."""
    if type(n) is not int or n < 1:
        raise ValueError("Invalid asset count")
    mu, sigma = np.asarray(mean_ret), np.asarray(cov)
    if (mu.shape != (n,) or sigma.shape != (n, n)
            or mu.dtype.kind not in "fiu" or sigma.dtype.kind not in "fiu"
            or not np.all(np.isfinite(mu)) or not np.all(np.isfinite(sigma))):
        raise ValueError("Invalid portfolio moments")
    mu, sigma = mu.astype(float), sigma.astype(float)
    if not np.all(np.isfinite(mu)) or not np.all(np.isfinite(sigma)):
        raise ValueError("Invalid portfolio moments")
    scale = float(np.max(np.abs(sigma)))
    if scale <= 0 or not np.allclose(sigma / scale, sigma.T / scale, rtol=0, atol=1e-12):
        raise ValueError("Covariance must be symmetric and nonzero")
    sigma = sigma * 0.5 + sigma.T * 0.5
    eigenvalues = np.linalg.eigvalsh(sigma / scale)
    if not np.all(np.isfinite(eigenvalues)) or eigenvalues[0] <= 1e-12:
        raise ValueError("Singular or indefinite covariance; no implicit regularization")
    return mu, sigma


def build_params(returns_df):
    """Return annual sample moments from a complete, aligned return panel."""
    if (not returns_df.index.is_unique or not returns_df.index.is_monotonic_increasing
            or not returns_df.columns.is_unique or len(returns_df) < 2):
        raise ValueError("Invalid return panel index or columns")
    arr = returns_df.to_numpy()
    if arr.dtype.kind not in "fiu" or not np.all(np.isfinite(arr)):
        raise ValueError("Incomplete or nonnumeric return panel")
    mean_ret = returns_df.mean().values * 252
    cov = returns_df.cov().values * 252
    n = len(mean_ret)
    mean_ret, cov = _validate_moments(mean_ret, cov, n)
    return mean_ret, cov, n


def run_strategy(strategy, mean_ret, cov, n, extra=None):
    """
    Returns dict: {weights, return, volatility, sharpe} or {error}.
    weights is a numpy array of length n.
    """
    try:
        mean_ret, cov = _validate_moments(mean_ret, cov, n)
    except (ValueError, TypeError, np.linalg.LinAlgError):
        return {"error": "Invalid portfolio moments"}
    if extra is None:
        extra = {}
    RF = 0.04

    from scipy.optimize import minimize

    bounds      = tuple((0.0, 1.0) for _ in range(n))
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    w0          = np.ones(n) / n

    def port_ret(w):  return float(np.dot(w, mean_ret))
    def port_vol(w):  return float(np.sqrt(max(np.dot(w, np.dot(cov, w)), 0.0)))
    def neg_sharpe(w):
        r, v = port_ret(w), port_vol(w)
        return -(r - RF) / v if v > 1e-10 else 0.0

    try:
        if strategy in ("max_sharpe", "max_return_adj"):
            res = minimize(neg_sharpe, w0, method="SLSQP",
                           bounds=bounds, constraints=constraints,
                           options={"ftol": 1e-9, "maxiter": 1000})

        elif strategy == "min_volatility":
            res = minimize(port_vol, w0, method="SLSQP",
                           bounds=bounds, constraints=constraints,
                           options={"ftol": 1e-9, "maxiter": 1000})

        elif strategy == "max_return":
            res = minimize(lambda w: -port_ret(w), w0, method="SLSQP",
                           bounds=bounds, constraints=constraints,
                           options={"ftol": 1e-9, "maxiter": 1000})

        elif strategy == "risk_parity":
            def rp_obj(w):
                v = port_vol(w)
                if v < 1e-10:
                    return 0.0
                mrc = np.dot(cov, w) / v
                rc  = w * mrc
                target = v / n
                return float(np.sum((rc - target) ** 2))
            res = minimize(rp_obj, w0, method="SLSQP",
                           bounds=bounds, constraints=constraints,
                           options={"ftol": 1e-12, "maxiter": 2000})

        elif strategy in ("equal_weight", "equal"):
            w = np.ones(n) / n
            return _build_result(w, mean_ret, cov, strategy)

        elif strategy in ("hrp", "inv_var"):
            diag = np.diag(cov)
            diag = np.where(diag > 1e-12, diag, 1e-12)
            inv_var = 1.0 / diag
            w = inv_var / inv_var.sum()
            return _build_result(w, mean_ret, cov, strategy)

        elif strategy in ("target_return",):
            tgt = extra.get("target_return", 0.10)
            if (isinstance(tgt, bool) or not isinstance(tgt, (int, float))
                    or not np.isfinite(tgt)
                    or tgt < float(np.min(mean_ret)) or tgt > float(np.max(mean_ret))):
                return {"error": "Infeasible target return"}
            cons = constraints + [{"type": "eq", "fun": lambda w: port_ret(w) - tgt}]
            res = minimize(port_vol, w0, method="SLSQP",
                           bounds=bounds, constraints=cons,
                           options={"ftol": 1e-9, "maxiter": 1000})

        elif strategy == "black_litterman":
            delta = 2.5
            pi    = delta * np.dot(cov, w0)
            def neg_bl_sharpe(w):
                r = float(np.dot(w, pi))
                v = port_vol(w)
                return -(r - RF) / v if v > 1e-10 else 0.0
            res = minimize(neg_bl_sharpe, w0, method="SLSQP",
                           bounds=bounds, constraints=constraints,
                           options={"ftol": 1e-9, "maxiter": 1000})

        else:
            return {"error": "Unknown optimization strategy"}

        if not _valid_solution(res, n):
            return {"error": "Optimization failed or violated weight constraints"}
        result = _build_result(res.x, mean_ret, cov, strategy)
        if strategy == "target_return" and abs(result["return"] - tgt) > 1e-7:
            return {"error": "Optimization violated target return"}
        if strategy == "risk_parity":
            shares = risk_decomposition(result["weights"], cov)["percentage"] / 100.0
            if np.max(np.abs(shares - 1.0 / n)) > 1e-4:
                return {"error": "Risk parity contribution residual too large"}
        return result

    except Exception as exc:
        return {"error": str(exc)}


def _valid_solution(res, n):
    if not getattr(res, "success", False):
        return False
    w = np.asarray(res.x, dtype=float)
    return (w.shape == (n,) and np.all(np.isfinite(w))
            and np.all(w >= -1e-8) and np.all(w <= 1.0 + 1e-8)
            and abs(float(w.sum()) - 1.0) <= 1e-8)


def _build_result(weights, mean_ret, cov, strategy):
    RF   = 0.04
    w    = np.clip(weights, 0.0, 1.0)
    s    = w.sum()
    if s > 1e-10:
        w = w / s
    r    = float(np.dot(w, mean_ret))
    v    = float(np.sqrt(max(np.dot(w, np.dot(cov, w)), 0.0)))
    sh   = float((r - RF) / v) if v > 1e-10 else 0.0
    if not np.all(np.isfinite([r, v, sh])) or v <= 1e-12:
        raise ValueError("Invalid portfolio performance")
    methodology = {"hrp": "INVERSE_VARIANCE_PROXY", "inv_var": "INVERSE_VARIANCE_PROXY",
                   "black_litterman": "EQUILIBRIUM_PRIOR_NO_VIEWS"}.get(strategy, strategy.upper())
    return {"weights": w, "return": r, "volatility": v, "sharpe": sh,
            "strategy": strategy, "methodology": methodology}


def risk_decomposition(weights, cov):
    """Euler decomposition; negative hedge contributions are preserved."""
    w = np.asarray(weights)
    if w.ndim != 1 or w.dtype.kind not in "fiu":
        raise ValueError("Invalid weights")
    n = len(w)
    _, cov = _validate_moments(np.zeros(n), cov, n)
    if (not np.all(np.isfinite(w)) or np.any(w < 0) or np.any(w > 1)
            or abs(float(w.sum()) - 1.0) > 1e-8):
        raise ValueError("Invalid weights")
    cov_w = cov @ w
    var = float(w @ cov_w)
    if not np.isfinite(var) or var <= 1e-24:
        raise ValueError("Undefined portfolio risk")
    vol = np.sqrt(var)
    marginal = cov_w / vol
    component = w * marginal
    percentage = component / vol * 100.0
    if not np.all(np.isfinite(percentage)) or abs(float(percentage.sum()) - 100.0) > 1e-7:
        raise ValueError("Invalid risk decomposition")
    return {"volatility": float(vol), "marginal": marginal, "component": component,
            "percentage": percentage, "asset_volatility": np.sqrt(np.diag(cov))}


# ── Efficient frontier ────────────────────────────────────────────────────────

def build_frontier(mean_ret, cov, n, num_points=40):
    """Return list of {volatility, return, sharpe} frontier points."""
    try:
        mean_ret, cov = _validate_moments(mean_ret, cov, n)
    except (ValueError, TypeError, np.linalg.LinAlgError):
        return []
    if type(num_points) is not int or not 2 <= num_points <= 1000:
        return []
    from scipy.optimize import minimize
    RF = 0.04

    bounds      = tuple((0.0, 1.0) for _ in range(n))
    w0          = np.ones(n) / n

    # Find min-vol and max-return to span the frontier
    min_vol_res = minimize(
        lambda w: float(np.sqrt(max(np.dot(w, np.dot(cov, w)), 0.0))),
        w0, method="SLSQP",
        bounds=bounds,
        constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
        options={"ftol": 1e-9, "maxiter": 1000},
    )
    if not _valid_solution(min_vol_res, n):
        return []
    min_ret = float(np.dot(min_vol_res.x, mean_ret))
    max_ret = float(np.max(mean_ret))          # upper bound: all-in best asset

    targets = np.linspace(min_ret, max_ret, num_points)
    points  = []

    for tgt in targets:
        try:
            cons = [
                {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
                {"type": "eq", "fun": lambda w, t=tgt: float(np.dot(w, mean_ret)) - t},
            ]
            res = minimize(
                lambda w: float(np.sqrt(max(np.dot(w, np.dot(cov, w)), 0.0))),
                w0, method="SLSQP",
                bounds=bounds, constraints=cons,
                options={"ftol": 1e-9, "maxiter": 500},
            )
            if _valid_solution(res, n):
                result = _build_result(res.x, mean_ret, cov, "target_return")
                ret, vol = result["return"], result["volatility"]
                if abs(ret - tgt) <= 1e-7 and np.isfinite(vol):
                    points.append({"volatility": vol, "return": ret, "sharpe": result["sharpe"]})
        except Exception:
            pass

    return points


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Support both command-line args (--args <json>) and stdin
    stdin_data = ""
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--args" and i + 1 < len(args):
            stdin_data = args[i + 1]
            i += 2
        elif not args[i].startswith("--") and not stdin_data:
            stdin_data = args[i]
            i += 1
        else:
            i += 1

    if not stdin_data.strip():
        # Fall back to stdin for backwards compatibility
        stdin_data = sys.stdin.read()

    if not stdin_data.strip():
        print(json.dumps({"error": "No input data"}))
        return

    try:
        params = json.loads(stdin_data)
    except Exception as exc:
        print(json.dumps({"error": f"JSON parse error: {exc}"}))
        return

    symbols = params.get("symbols", [])
    if not symbols:
        print(json.dumps({"error": "No symbols provided"}))
        return

    # Map C++ method name to internal strategy key
    method_map = {
        "max_sharpe":        "max_sharpe",
        "max sharpe":        "max_sharpe",
        "min_volatility":    "min_volatility",
        "min volatility":    "min_volatility",
        "risk_parity":       "risk_parity",
        "risk parity":       "risk_parity",
        "max_return":        "max_return",
        "max return":        "max_return",
        "equal_weight":      "equal_weight",
        "equal weight":      "equal_weight",
        "hrp":               "hrp",
        "target_return":     "target_return",
        "target return":     "target_return",
        "black_litterman":   "black_litterman",
        "b-l model":         "black_litterman",
        "b_l_model":         "black_litterman",  # "B-L Model" → lower → replace(-,_)
        "b-l_model":         "black_litterman",
    }
    raw_method = params.get("method", "max_sharpe").lower().replace("-", "_")
    strategy   = method_map.get(raw_method, raw_method)

    close = fetch_price_data(symbols)
    if close is None:
        print(json.dumps({"error": "Could not fetch price data"}))
        return

    available = [s for s in symbols if s in close.columns]
    if not available:
        print(json.dumps({"error": "No price data for any symbol"}))
        return

    returns_df = close[available].pct_change().dropna()
    if len(returns_df) < 20:
        print(json.dumps({"error": "Insufficient price history (need ≥ 20 trading days)"}))
        return

    try:
        mean_ret, cov, n = build_params(returns_df)
    except (ValueError, TypeError, np.linalg.LinAlgError):
        print(json.dumps({"error": "Invalid portfolio return panel or covariance"}))
        return

    # ── Primary optimisation ──────────────────────────────────────────────────
    primary = run_strategy(strategy, mean_ret, cov, n, extra=params)
    if "error" in primary:
        print(json.dumps({"error": primary["error"]}))
        return

    weights_arr  = primary["weights"]
    weights_dict = {available[i]: float(weights_arr[i]) for i in range(n)}

    # ── Efficient frontier ────────────────────────────────────────────────────
    frontier = []
    try:
        frontier = build_frontier(mean_ret, cov, n)
    except Exception:
        pass

    # ── Multi-strategy comparison ─────────────────────────────────────────────
    comparison_strategies = [
        "max_sharpe", "min_volatility", "risk_parity", "hrp", "equal_weight"
    ]
    comparison = {}
    for cs in comparison_strategies:
        try:
            r = run_strategy(cs, mean_ret, cov, n)
            if "error" not in r:
                w_arr = r["weights"]
                comparison[cs] = {
                    "weights":    {available[i]: float(w_arr[i]) for i in range(n)},
                    "return":     r["return"],
                    "volatility": r["volatility"],
                    "sharpe":     r["sharpe"],
                    "methodology": r["methodology"],
                }
        except Exception:
            pass

    # ── Risk decomposition for the primary weights ────────────────────────────
    # Marginal risk contribution MRC = (Σ·w)/σ_p ; risk contribution RC = w·MRC.
    # Σ RC = σ_p, so RC%/asset = RC/σ_p. Reported as % of total portfolio risk.
    risk_contributions = {}
    marginal_risk = {}
    asset_volatility = {}
    try:
        risk = risk_decomposition(weights_arr, cov)
        for i in range(n):
            sym = available[i]
            asset_volatility[sym] = float(risk["asset_volatility"][i])
            marginal_risk[sym] = float(risk["marginal"][i])
            risk_contributions[sym] = float(risk["percentage"][i])
    except (ValueError, TypeError, np.linalg.LinAlgError):
        print(json.dumps({"error": "Invalid portfolio risk decomposition"}))
        return

    # ── Black-Litterman market-implied equilibrium returns ────────────────────
    # π = δ · Σ · w_market, using the caller's current weights as the market
    # proxy (falls back to equal weight). Lets the B-L tab show what returns the
    # market is implicitly pricing in before any investor views are applied.
    implied_returns = {}
    try:
        in_weights = params.get("weights", [])
        w_mkt = np.zeros(n)
        if isinstance(in_weights, list) and len(in_weights) == len(symbols):
            wmap = {symbols[i]: float(in_weights[i]) for i in range(len(symbols))}
            for i in range(n):
                w_mkt[i] = wmap.get(available[i], 0.0)
        if w_mkt.sum() <= 1e-9:
            w_mkt = np.ones(n) / n
        else:
            w_mkt = w_mkt / w_mkt.sum()
        delta = 2.5  # risk-aversion coefficient
        pi = delta * np.dot(cov, w_mkt)
        for i in range(n):
            implied_returns[available[i]] = float(pi[i])
    except Exception:
        pass

    output = {
        "weights":                weights_dict,
        "expected_annual_return": primary["return"],
        "annual_volatility":      primary["volatility"],
        "sharpe_ratio":           primary["sharpe"],
        "strategy":               strategy,
        "methodology":            primary["methodology"],
        "symbols":                available,
        "frontier":               frontier,
        "comparison":             comparison,
        "risk_contributions":     risk_contributions,
        "marginal_risk":          marginal_risk,
        "asset_volatility":       asset_volatility,
        "implied_returns":        implied_returns,
    }

    print(json.dumps(convert_numpy(output)))


if __name__ == "__main__":
    main()
