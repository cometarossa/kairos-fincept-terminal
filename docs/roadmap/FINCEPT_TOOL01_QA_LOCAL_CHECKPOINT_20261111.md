# Checkpoint — TOOL-01 backtest validation and QA-LOCAL native Qt tests (2026-11-11)

Written at the end of one Claude Code session. Every item is an OPEN DRAFT pull
request with local runs only. Fork Actions are disabled: nothing here is CI, and
none of it has had an independent review. Re-verify heads before relying on it.

## State verified at 2026-11-11 ~18:30 UTC

| Item | Value |
|---|---|
| Fork `main` | `7716ee86` |
| KAIROS canonical `feature/kairos-autonomous-bridge` | `d0b75a51` |
| #26 head (other automation) | `60db7a6c` — moved twice during the session |
| #27 / #28 / #29 / #30 / #31 heads | `60b5a747` / `5f7aeb5c` / `28325bf2` / `6eb3e0fe` / `4a3ce706` |

Compatibility check done earlier in the session, with #26 at `2f163180` merged
locally into its dependants (isolated venv: numpy 2.5.4, pandas 2.3.3, ta 0.11.0):
#26 16 passed, #28 46 passed, #31 24 passed, #30 10 passed.

Repeated against #26 `60db7a6c`: **that head does not run**. Two files end with a
pasted tool-output line (`[executed on device: iMac-3.local (...)]`), so
`pytest tests` stops with `1 error` at collection. With those two lines removed
(#38): #26 29 passed, #28 merged with it 59 passed, #31 merged with it 37 passed.

## Pull requests opened in this session

| PR | Branch | Base | Head | Content | Local result |
|---|---|---|---|---|---|
| #32 | `test/tool01-vectorbt-backtest-oracle-20261111` | `main` | `5f143d68` | Original VectorBT provider run offline vs exact `Fraction` oracle vs real vectorbt 0.28.2; six scenarios | 29 passed + 2 skipped / 31 with vectorbt |
| #33 | `test/tool01-backtest-oracle-stops-20261111` | #32 | `e4395d9d` | Stop-loss, take-profit, trailing stop; fourteen scenarios | 39 + 2 skipped / 41 |
| #34 | `test/tool01-backtest-metrics-oracle-20261111` | #33 | `2e71d8e5` | `performance` and `statistics` blocks vs metric oracle; seventeen scenarios, 365 and 252 bars/year | 51 + 2 skipped / 53 |
| #35 | `feature/tool01-backtest-evidence-envelope-v1-20261111` | #34 | `9e5aba21` | Versioned allowlisted evidence envelope `kairos_fincept_backtest_evidence_v1` | 66 + 2 skipped / 68 |
| #36 | `test/qa-local-qt-unit-harness-20261111` | `main` | `3aa74f29` | Native Qt harness (upstream test CMake unmodified) + exact reference for the C++ `IndicatorEngine` | Qt 6.8.3: 16 + 15 + 8 + 40 QtTest passed; 6 Python passed |

| #38 | `fix/pr26-stray-device-log-lines-20261111` | #26 | `29e5e757` | Removes the two stray lines that break #26's head (re-merged onto #26 `abe3839f`, still broken there) | `1 error` before, 34 passed after |
| #40 | `fix/backtest-multi-asset-total-fees-20261111` | `main` | `651237bb` | **Fix**: multi-asset VectorBT `statistics.totalFees` was always 0; 15 lines in two research scripts | 2 tests fail before, 5 passed after; single-asset output byte-identical |
| #41 | `test/tool01-backtest-multi-asset-oracle-20261112` | #35 | `52ad53f3` | Multi-asset path vs per-symbol oracles; twenty scenarios | 69 + 2 skipped / 71 |
| #37 | `docs/tool01-qa-local-checkpoint-20261111` | `main` | this file | Checkpoint | — |

No original Fincept file is modified by any of them.

## Findings (characterised by tests, nothing changed)

1. The VectorBT provider reports candles injected through `brokerCandles` as real
   broker data (`usingSyntheticData=false`). A fixture must be labelled by the
   caller; the probe and the envelope do so.
2. `statistics.totalSlippage` (and per-trade `slippage`) is hard-coded to 0 in
   every backtesting provider although slippage is applied to fills. No C++/QML
   code reads the field, so it was left alone.
3. The provider's Sharpe is CAGR-based: 0.35 % to 22.5 % away from the
   arithmetic-mean convention on the fixtures. Do not compare it with a KAIROS
   Sharpe without converting. Average win/loss and expectancy are P&L over the
   initial capital.
4. Stops are judged on the close and filled at the next open, so a "stop-loss"
   can fill above the entry and never at its own level.
5. Upstream `tst_order_validator` does not compile as declared
   (`OrderValidator.cpp` now includes the settings repository and logger).
   **Owner decision needed**: the fix is in broker order-validation code, outside
   the scope given to the agent.
6. Multi-asset backtests report `statistics.totalFees = 0` although commissions
   are charged (fixed in #40; #41 pins the original behaviour, so the two source
   pins and that expectation must be updated together when #40 lands).
7. Apart from finding 6, the simulator, the metrics and the 22 C++ indicators
   checked showed **no arithmetic error** against the exact references.

## Not done / not verified

- No build of `FinceptTerminal`, no screen or widget test, no CI.
- Backtest: Kelly / volatility / risk sizing, more than two symbols, the other strategies,
  optimisation, walk-forward, the extended analysis blocks.
- Indicators: ADX, Supertrend, edge cases.
- No KAIROS-side consumer of the evidence envelope; the bridge policy of
  #16/#17/#25 was not edited (other automation's files).
- The stack #26–#31 was not modified.

## How to resume

```bash
python -m venv .venv && .venv/bin/pip install 'numpy>=2.2.3,<3' 'pandas>=2.3.3,<3' 'ta==0.11.0' pytest
# optional third leg: a second venv with 'vectorbt==0.28.2' 'plotly<6'
git fetch origin feature/tool01-backtest-evidence-envelope-v1-20261111 && git checkout FETCH_HEAD
.venv/bin/python -m pytest -q tests/fincept_audit            # expect 66 passed, 2 skipped
# Qt: pip install aqtinstall; aqt install-qt linux desktop 6.8.3 linux_gcc_64 -O <qt>
git fetch origin test/qa-local-qt-unit-harness-20261111 && git checkout FETCH_HEAD
cmake -S tools/fincept_audit/qt_unit_harness -B <build> -G Ninja -DCMAKE_PREFIX_PATH=<qt>/6.8.3/gcc_64
cmake --build <build> --target tst_result tst_broker_modify_fields tst_indicator_engine tst_indicator_engine_reference
QT_QPA_PLATFORM=offscreen ctest --test-dir <build> -E tst_order_validator
```

Suggested next priorities, in order:

1. #26's owner takes #38 (or removes the two lines itself), then #27–#31 are
   updated onto the repaired head.
2. After #40: update `PINNED_SOURCES` and the multi-asset fee expectation in the
   probe (hashes are in #40's description). Check the other backtesting
   providers for the same missing-fees pattern.
3. ADX and Supertrend in the C++ reference suite; edge cases.
4. A KAIROS-side, offline, non-authoritative reader for the evidence envelope,
   once the owner decides where it should live.
5. Owner decision on finding 5.

`live_execution_authority=false`. No order, broker, DEMO/LIVE, credential, runner
or service was touched. No paid service or external model was called.
