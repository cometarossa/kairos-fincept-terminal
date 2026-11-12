# Fincept ADX / Supertrend — strict numerical fix candidate

**Date:** 2026-11-12. **Status:** ISOLATED DRAFT / NOT_DEPLOYED / NOT_APPROVED_FOR_TRADING. This is a signal-affecting C++ change and must not be automatically merged or enabled. The branch is stacked on existing [diagnostic DRAFT #45](https://github.com/cometarossa/kairos-fincept-terminal/pull/45), which itself is stacked on [Qt reference DRAFT #36](https://github.com/cometarossa/kairos-fincept-terminal/pull/36). Main remained at `7716ee8613249fb44c4d14036c5bc16ed6f34e97` during this QA.

## What changed (only in the isolated branch)

- `fincept-qt/src/algo_engine/IndicatorEngine.cpp`: **ADX(14)** now captures the Wilder-smoothed TR, +DM, and -DM sums at the immediately prior candle, and uses them to populate `previous.plus_di` and `previous.minus_di`. The existing current +DI/-DI, ADX current and previous remain computed as before. The original C++ blob was `cf454fff4dc204a45248bc285f72fd38745e68b7`; the candidate C++ blob is `7d3c32ca4d9f4a265a77dbbe56d59b52129ecfb5`.
- Same C++ file: **Supertrend(10,3)** computes the final lower/upper bands against their own previous final values, tests reversal direction against **previous** final bands, and initializes the first valid trend line at `period-1`, so the prior value for a short series is not an uninitialized zero.
- **Reference tests promoted from known-defect exceptions to strict agreement.** `tools/fincept_audit/indicator_reference_v1.py` uses `CHECKS = {}` and all 40 generated current/previous reference rows now require equality. The native Qt test removed allowances for `current_only` and `diverges` and fails on either mismatched bar.
- **Temporal tests promoted from two XFAILs to strict passes:** for 81 synthetic prefixes, prior ADX +DI/-DI must equal previous-prefix current +DI/-DI; crossovers must not be suppressed; the Supertrend long line must not decrease in consecutive-long intervals.
- Added a **second, independent, 200-bar bullish/bearish reversal fixture** generated from integer cents and `Fraction` arithmetic by `tools/fincept_audit/supertrend_reversal_reference_v1.py`. New native test checks 16 predetermined sample rows including current/previous line and direction, strict as-of prefix consistency through bar 200, and exactly **four direction reversals** (bars with zero-based indices 43, 82, 123, 165). A Python source-contract test verifies that every embedded native expected row is generated from the separate reference implementation.

## Executed local results (iMac, exact Git blob-matched sources)

Using **official Qt 6.8.3 Core/Test**, AppleClang 16 and CMake 4.0.1 on an isolated QA copy:

- **Native CMake configure/compile/link PASS** with actual production `IndicatorEngine.cpp`, original upstream `tst_indicator_engine` and the strictly modified independent test suite.
- **CTest 3/3 PASS**, with **zero XFAIL**: original native indicator unit **8/8**, exact numeric reference **44/44** including 40 data rows, and temporal/reversal suite **5/5**. All 40 current/previous row-pairs match the exact mathematical reference on the pinned 120-candle synthetic fixture.
- ADX prefixes: **162/162 previous-DI values correct**, previously 162/162 mismatched. The 20 independently detected DI-order crossings are now all visible through the engine's `previous` map (**0 masked**, previously 20).
- Supertrend first fixture: **0 declines** across 106 successive same-direction long transitions (previously 65). Second fixture: all 16 sample line/direction values match exact rational reference; **4/4 reversals** and all tested previous-prefix relationships match.
- **15/15 Python reference/provenance tests PASS** (8 base reference, 4 temporal source contracts, 3 independent reversal-oracle tests). The modified and new code blobs were checked against their published GitHub file blobs, not inferred from an old build.

### Negative control on the unchanged old engine

Copied the same strict tests into another temporary QA directory, replaced only the candidate C++ implementation with unmodified fork `main` blob `cf454fff4dc204a45248bc285f72fd38745e68b7`, and rebuilt. The strict numeric reference suite **FAILED 3 rows**: ADX prior +DI, ADX prior −DI, Supertrend current. The strict temporal suite **FAILED 3 properties**: ADX prior DI, Supertrend long ratcheting, and bidirectional reversal reference. The negative runner independently asserted all five named failure categories and removed the temporary copy. This confirms the strict tests distinguish the source fix.

## Reproduction

With this branch and official Qt 6.8.3 native development package:

```sh
cmake -S tools/fincept_audit/qt_unit_harness -B /tmp/fincept-indicator-fix-build \
  -DCMAKE_PREFIX_PATH=/path/to/Qt/6.8.3/macos -DCMAKE_BUILD_TYPE=Debug
cmake --build /tmp/fincept-indicator-fix-build \
  --target tst_indicator_engine tst_indicator_engine_reference tst_indicator_temporal_contracts
ctest --test-dir /tmp/fincept-indicator-fix-build \
  -R '^(tst_indicator_engine|tst_indicator_engine_reference|tst_indicator_temporal_contracts)$' \
  -V --output-on-failure
python3 -B -m unittest discover -s tests/fincept_audit -p 'test_indicator_*.py' -v
```

## Hard boundaries and follow-ups

**NOT_VERIFIED:** real market OHLCV, anomalous/missing live feeds, flat/short/zero-volume edge cases in C++ beyond existing upstream suite, all strategy consumers or backtest P&L changes, trade risk gates, the full Fincept application/GUI, the KAIROS hybrid, a second developer's code review, cross-platform QA, or GitHub Actions on the fork. No actual IG/demo/live order, account, authentication, user PIN/profile, installed Fincept app, server, runner, secret, privileged process, or budget was changed.

**Next release gate** (separate decision): audit every condition evaluator / strategy rule that uses ADX +DI/−DI crossovers or Supertrend direction, run old/new side-by-side strategy replays on authorized recorded data, review risk and permissions, run applicable CI and independent QA, and only then request owner approval for any merge. This draft is intentionally NOT a trading authorization or proof of profitable signals.

## 2026-11-12 — expanded upstream regression suites, exact-code-head rerun

In the unchanged isolated QA source tree, recovered **only two original header-only dependencies** of the upstream unit targets from fork `main` `7716ee86`: `fincept-qt/src/core/result/Result.h` and `fincept-qt/src/trading/brokers/BrokerModifyFields.h`. The first configure/build attempt for the extra targets had failed due to the absent `Result.h` in the incomplete QA export; adding these source headers resolved the *test environment* setup issue, not a production bug.

Rebuilt both extra upstream targets with Qt6.8.3 AppleClang and ran all buildable local unit suites:

- `tst_indicator_engine_reference` — PASS, strict 40-row current+previous numerical reference, no XFAIL.
- `tst_indicator_temporal_contracts` — PASS, strict ADX/long Supertrend/bidirectional 4-reversal oracle, no XFAIL.
- `tst_broker_modify_fields` — PASS, upstream **pure key/alias tests only**, no broker instantiated.
- `tst_result` — PASS, upstream Result contract unit tests.
- `tst_indicator_engine` — PASS, upstream indicator unit tests.

**Native CTest 5/5 PASS; Python source/reference suite 15/15 PASS** in the same local QA run, with eight modified/new file blob identities rechecked against the GitHub branch contents before the run. The actual `tst_order_validator` C++ target remains a pre-existing upstream compile blocker and was **not built or run**; no broker risk-gate modification or bypass was attempted. No full FinceptTerminal binary, full GUI, broker runtime, strategy P&L, cross-platform Linux CI, or KAIROS hybrid was validated. Fork Actions remained disabled/not verified. DRAFT / NO MERGE.
