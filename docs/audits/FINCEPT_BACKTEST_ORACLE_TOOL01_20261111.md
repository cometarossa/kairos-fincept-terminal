# TOOL-01 — original VectorBT backtest provider against an exact oracle (2026-11-11)

**Status: local synthetic verification only. `scientific_status=NOT_EVALUATED`,
`broker_authority=false`, `promotion_eligible=false`.** Nothing here is market
evidence, an edge estimate or a trading signal. No original Fincept file is
modified.

## What was run

| Leg | What it is |
|---|---|
| Original provider | `fincept-qt/scripts/Analytics/backtesting/vectorbt/vectorbt_provider.py`, unmodified, through the host's own CLI contract `run_backtest --stdin`, in a child interpreter |
| Exact oracle | `tools/fincept_audit/backtest_oracle_v1.py`: standard library only, `Fraction` arithmetic, written from the provider's stated execution model (signal on the close of bar *t*, fill at the open of *t+1*) |
| Real VectorBT | `vectorbt==0.28.2` `Portfolio.from_signals`, as a third independent implementation |

The provider's "VectorBT" engine does not call vectorbt for the simulation: it
runs its own numpy loop (`vbt_portfolio._simulate_signals`). That is why a
separate comparison with the real library is included.

Input: deterministic synthetic daily candles (two-decimal prices, sha256-pinned)
passed through the provider's existing `brokerCandles` input. Fourteen
scenarios. Six without stops: no costs; commission + slippage; 40 % sizing;
fixed-amount sizing; `same_close` execution; a position still open on the last
bar. Eight with stops: stop-loss after a 5.00 downward step (both execution
modes), take-profit (two sizings), trailing stop (both execution modes), all
three together, and a stop-loss that ties with the crossover exit.

## Result

- Provider vs oracle: every equity point, every trade (dates, prices, size, P&L,
  fees, exit reason), final capital, total fees and total return agree within
  relative 1e-9 in all fourteen scenarios, including the exit reason
  (`signal`, `stop_loss`, `take_profit`, `trailing_stop`, `end_of_data`).
- Real VectorBT vs oracle: the equity curve agrees within relative 1e-9 in the
  four scenarios vectorbt can express the same way (all-in sizing, flat at the
  end).
- The oracle itself is checked against numbers worked out by hand in the tests.
- The comparison is shown to fail on a wrong commission, slippage, sizing,
  execution model, a missing or wrong stop, and on tampered provider output.

Stop semantics confirmed in the original simulator: stops are judged on each
bar's close from the fill bar onwards against the actual entry fill (slippage
included) and exit at the next open; the trailing peak starts at the entry
fill; precedence is stop-loss, take-profit, trailing stop, and any stop
outranks a signal exit on the same bar. Consequence worth knowing: because the
check uses the close and the fill is the next open, a "stop-loss" exit can
fill above the entry price, and a stop is never filled at its own level.

## Two findings about the original provider (characterised, not changed)

1. **Injected candles are reported as real broker data.** With `brokerCandles`
   the provider returns `usingSyntheticData=false` and
   `dataSource=<brokerDataSource>`. A caller cannot use that flag to tell a
   fixture from market data. The probe stamps its own
   `SYNTHETIC_FIXTURE_NOT_MARKET_DATA` label and never forwards the provider's.
   Any KAIROS-side consumer must do the same.
2. **`statistics.totalSlippage` is 0 although slippage is applied.** Fills do
   include slippage (the equity matches the oracle only with it), but the
   statistic is not populated. Fees are reported correctly.

## Isolation actually enforced

- Nine original files are sha256-pinned to fork `main` `7716ee86`; the child
  reports every repository module it imported and the run fails if one is not
  pinned. Hashes are checked before and after.
- The child runs with `-I -B` and an empty `pycache_prefix`: a stale `.pyc`
  beside a source is not executed and nothing is written back (tested).
- Python socket connections are denied and counted in the child; the six runs
  made none (fourteen runs). The child gets a minimal environment (tested with a canary).

This is a Python-level harness, not an OS sandbox.

## Reproduce

```bash
python -m venv .venv && .venv/bin/pip install 'numpy>=2.2.3,<3' 'pandas>=2.3.3,<3' pytest
.venv/bin/python -m pytest -q tests/fincept_audit/test_backtest_oracle_v1.py \
    tests/fincept_audit/test_backtest_provider_probe_v1.py \
    tests/fincept_audit/test_backtest_vectorbt_reference_v1.py
# third leg (optional): pip install 'vectorbt==0.28.2' 'plotly<6'
.venv/bin/python tools/fincept_audit/backtest_provider_probe_v1.py \
    --backtesting-dir fincept-qt/scripts/Analytics/backtesting
```

Observed on 2026-11-11 (Linux, Python 3.13):

| Interpreter | Result |
|---|---|
| numpy 2.5.4, pandas 2.3.3 (Fincept numpy2 pins), no vectorbt | 39 passed, 2 skipped |
| numpy 2.5.4, pandas 3.1.1, vectorbt 0.28.2, plotly 5.24.1 | 41 passed |

## Not covered

Kelly / volatility / risk sizing, intrabar stop fills, multi-asset, the other
strategies, optimisation, walk-forward, the metrics block (Sharpe, drawdown…),
the yfinance path, the Qt screen, and anything about real markets. The second
interpreter is not Fincept's pinned pandas. Fork Actions are disabled: these are
local runs, not CI.
