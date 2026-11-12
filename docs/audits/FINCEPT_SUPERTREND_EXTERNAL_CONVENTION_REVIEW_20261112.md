# Fincept Supertrend — independent TradingView convention cross-check (2026-11-12)

**Classification: DIAGNOSTIC / DRAFT / NOT DEPLOYED / NOT A TRADING AUTHORIZATION.**

This PR is stacked on Fincept signal-affecting DRAFT #46 at **exact parent HEAD `3e8af2db027cee69e44c4fceb75b50bb225501a3`**, which in turn depends on DRAFT #45 and DRAFT #36. No original `fincept-qt/` file is edited. Candidate `fincept-qt/src/algo_engine/IndicatorEngine.cpp` remains Git blob **`7d3c32ca4d9f4a265a77dbbe56d59b52129ecfb5`**.

## Independent external convention, not a substitute for owner choice

The [TradingView Supertrend calculation guide](https://www.tradingview.com/support/solutions/43000634738-supertrend/) defines rolling upper and lower bands with previous-band carry/reset and chooses the trend direction using the prior active Supertrend side and current final bands. Its documented initial direction is down until the ATR is available. [TradingView's ATR guide](https://www.tradingview.com/support/solutions/43000501823-average-true-range-atr/) explicitly states that **RMA/Wilder** is the default ATR smoothing, with EMA offered as an alternate setting.

The **Fincept #46 candidate is not configured to be an exact default-TradingView clone**: it uses its original C++ `ema_series` to smooth true range with `alpha = 2/(period+1)` (rather than default RMA `alpha = 1/period`) and starts with direction `+1` (up) at first available band instead of the TradingView convention's down state. Its code expresses crossover tests against previous final bands without explicitly switching the test by previous trend. **After normalizing smoothing and initial trend, this formulation was numerically equivalent** to the TradingView-style state-machine reference in all tested synthetic scenarios; no stand-alone direction-rule defect was established by this audit.

These are *definition/configuration* differences, not evidence that a numerical bug remains in #46. Before a trading release, the owner must explicitly choose and version the indicator's ATR kernel, first-state convention, output format and test target. Changing the kernel or seed would itself be a signal-affecting strategy change requiring independent replay and approvals.

## Independently executed native C++ and exact-rational comparison

A new standalone QtCore 6.8.3 executable `supertrend_candidate_prefix_dump` compiles and links the **actual unchanged candidate `IndicatorEngine.cpp`**, not a reimplementation. It emits 190 current line/direction values for **each** of two 200-bar deterministic synthetic OHLCV fixtures, always calculating from the as-of prefix. The CLI has no broker, GUI, network, market data or account dependency.

A separate `Fraction`-arithmetic Python oracle uses the published TradingView band/state rules with three *explicit* convention settings. The final audited result:

| 200-bar synthetic fixture | Convention relative to C++ candidate | Different directions (190 bars) | Different line values (190 bars) |
|---|---|---:|---:|
| Four long/short reversals | TradingView state, **matched Fincept EMA + bullish seed** | **0** | **0** |
| Four long/short reversals | TradingView state, **Wilder/RMA + bullish seed** | 0 | **190** |
| Four long/short reversals | TradingView state, **Wilder/RMA + initially bearish** | **15** | **190** |
| Shock/ranging data | TradingView state, **matched Fincept EMA + bullish seed** | **0** | **0** |
| Shock/ranging data | TradingView state, **Wilder/RMA + bullish seed** | **43** | **167** |
| Shock/ranging data | TradingView state, **Wilder/RMA + initially bearish** | **67** | **190** |

**All 380 native C++ current-prefix outputs agree with their own Fincept-EMA `Fraction` oracle in direction**. Maximum observed line absolute discrepancy is **2.842 × 10⁻¹⁴**, floating-point rounding. A separate **32-seed × 240-bar** deterministic gap/volatility stress (7,680 bars) verified equality of the two *Python* state formulations under common EMA and bullish seed. The 32-seed stress is not an independent C++ build; only the two specified 200-bar fixtures exercised the actual C++ candidate.

Caveats: The exact-rational oracle fixes its 10-period ATR seed to the first ten true ranges; other platforms can treat first-bar TR and warmup differently. Equality of two formulations on the tested datasets is not a universal mathematical proof. Different numerical kernels or first-state conventions are *neither equivalent nor necessarily errors* unless an external contract had been specified.

## Test and non-vacuity evidence

- **Native CMake configure/compile/link PASS** against official Qt 6.8.3, AppleClang 16 on isolated iMac QA. Locale-specific numeric formatting was initially detected in the test-only CLI, then fixed with `setlocale(LC_NUMERIC, "C")` before CSV emission; production source untouched.
- **7/7 new Python tests PASS**, checking exact candidate blob, generated fixtures and drift-guarded reference counts, 32 stress seeds, RMA/initialization differences, CLI source linkage and fail-closed CSV schema, and aggregate-only report shape.
- **25/25 combined Python source/reference tests PASS** and existing **6/6 native CTest suites PASS** at the isolated candidate source; `tst_order_validator` remains an **excluded preexisting build blocker**, not a PASS.
- New audit runner pins **`IndicatorEngine.cpp` Git blob**, validates each of the 190 native rows per fixture, rejects malformed/nonfinite/locale-dependent CSV, rejects unexpected convention counts, and writes only synthetic summary statistics. No historical prices, executed trades, orders, tickers, user data or personal account state in `docs/audits/FINCEPT_SUPERTREND_EXTERNAL_CONVENTION_AGGREGATES_20261112.json`.
- **Fork CI:** NOT_VERIFIED. A green KAIROS documentation check cannot certify Fincept native builds.

## Reproduction

With this draft stacked on #46, the source blob pinned as above, and authorized Qt 6.8.3 local SDK:

```sh
cmake -S tools/fincept_audit/supertrend_external_audit \
  -B /tmp/fincept-supertrend-convention-audit \
  -DCMAKE_PREFIX_PATH=/path/to/Qt/6.8.3/macos
cmake --build /tmp/fincept-supertrend-convention-audit --parallel 2
python3 -B -m tools.fincept_audit.supertrend_external_audit.run_native_convention_audit_v1 \
  --native-binary /tmp/fincept-supertrend-convention-audit/supertrend_candidate_prefix_dump \
  --report /tmp/fincept-supertrend-convention-aggregate-only.json
python3 -B -m unittest discover -s tests/fincept_audit \
  -p test_supertrend_external_convention_v1.py -v
```

**Release gate:** no merge or enabling of #46 on this evidence alone. First agree on a versioned indicator standard (Fincept-compatible EMA vs TradingView-default Wilder and initialization), secure independent review, re-run the full strategy/risk impact on authorized point-in-time history, and complete platform/application CI. The earlier CC0 adjusted-history replay #48 is explicitly development-only and cannot settle profitability or point-in-time eligibility; sealed 2022+ holdout, installed Fincept, broker DEMO/LIVE and KAIROS autonomous authority remain untouched.
