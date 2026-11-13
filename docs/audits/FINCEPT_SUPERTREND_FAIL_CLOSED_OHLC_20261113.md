# Fincept Supertrend — fail-closed OHLC input contract (draft proposal)

**Date:** 2026-11-13. **Status:** DRAFT / ISOLATED / NOT_DEPLOYED / NO_TRADING_AUTHORITY. This narrow source-changing child branch is stacked on [Fincept DRAFT #46](https://github.com/cometarossa/kairos-fincept-terminal/pull/46) exact head `3e8af2db027cee69e44c4fceb75b50bb225501a3`. It neither changes the ATR kernel nor chooses the external Supertrend convention under review in sibling [DRAFT #49](https://github.com/cometarossa/kairos-fincept-terminal/pull/49).

## Confirmed original candidate hazard

On the actual `IndicatorEngine.cpp` of #46 (Git blob **`7d3c32ca4d9f4a265a77dbbe56d59b52129ecfb5`**, Qt6.8.3/AppleClang16 native build), synthetic 60-bar OHLCV test inputs returned **`valid=true`, empty error and finite line/direction** despite:
- last or earlier Close = `NaN`, or last Close = `+Inf`;
- last bar High below Low, or Close outside the High/Low range;
- negative or zero Supertrend multiplier, or period zero silently clamped to one.

A nonfinite High was independently observed to produce an error in the original engine; **some** malformed input types were thus rejected while others were falsely admitted. Flat OHLCV returned a defined numeric output. These are **input-validation observations**, not live incidents or realized trading signals. This native probe was run only on a synthetic isolated copy; no broker/account is attached.

## Proposed small C++ correction — only Supertrend branch

Candidate source blob **`e33cf1a6151012adb126ab05846b035d8efa16b0`** changes `fincept-qt/src/algo_engine/IndicatorEngine.cpp` only inside the `if (name == "SUPERTREND")` dispatch:

1. Fail closed if explicit period is not a JSON number or cannot be represented as integer at least 2; absent period still uses the previous default 14. Period below 2 is rejected rather than silently clamped.
2. Fail closed if multiplier is explicitly nonnumeric, nonfinite, zero or negative; absent multiplier retains the previous default 3.0.
3. On **all as-of input bars**, reject nonfinite Open/High/Low/Close or OHLC inconsistencies: High below Low, Open outside the range, or Close outside the range. The function returns an invalid `IndicatorResult` with an explanatory error. This is deliberately a stricter eligibility change than the old implementation; reviewers must assess downstream behavior.
4. The existing `compute_supertrend(...)` formula and the entire ADX path are **byte-identical** within the file outside the new guarded branch. The gate does not inspect any bars beyond the supplied as-of prefix.

**Explicit limitations:** Volume=0 and exactly flat prices are not necessarily malformed OHLC, so this narrow guard **does not assert signal eligibility** in such markets. The separate research preflight in DRAFT #44 addresses flat/zero-volume windows. The C++ guard also does **not validate timestamp uniqueness, session calendars, stale data, upstream adjustments, price provenance, historical PIT, strategy suitability, risk budgets, or any trading permission**. It is not wired into any deployed process.

## Exact local native and source QA

On isolated macOS 14.5, AppleClang16, official Qt6.8.3 Core/Test/Gui SDK, standalone existing Fincept Qt unit harness:

- **7/7 native CTest suites PASS**: original indicator units, strict 40-row mathematical reference, ADX/Supertrend temporal/reversal contracts, original ConditionEvaluator integration, new `tst_supertrend_input_guard`, Result units and pure broker modify-field units. New strict guard QtTest **8/8 PASS** (setup/cleanup + six actual test cases), **no XFAIL**. The upstream `tst_order_validator` remains excluded because of the separate pre-existing compile blocker, not counted PASS.
- **22/22 Python source/reference/provenance tests PASS**: original 18 on the PR #46 branch, including the updated exact engine SHA pin in `test_indicator_temporal_contract_v1.py`, plus four new source/broker-boundary checks. The unrelated sibling #49 external-convention tests are **not** part of this branch and were excluded from the isolated source checkout after an initially overinclusive test workspace.
- In a disposable second build, the **same strict guard QtTest compiled against the unchanged #46 candidate source** (old blob `7d3c32ca...`) returned **4 failing named methods**: nonfinite OHLC, inconsistent candles, invalid parameters and as-of prefix containing a later corruption. The harness asserted those four names, then deleted the temporary build. This demonstrates the new test is not vacuous.
- Every modified or added source/test Git blob matched the published draft branch: engine `e33cf1a6151012adb126ab05846b035d8efa16b0`, Qt CMake `57be236a897fc939c6fc34ece6e021a960ba4f85`, native QtTest `26131d0c59800c24cb9173419ffd29409ba0ba90`, existing Python source SHA pin `7a00515c60957ad8f3a274bcf2039fdeac21f0e6`, new Python tests `1d8fe6f29946f68cf5b583e130acbbe97c089713`. Native builds were executed against the exact C++ engine blob.

## Reproduce in an authorized isolated Qt 6.8.3 lab

```sh
cmake -S tools/fincept_audit/qt_unit_harness -B /tmp/fincept-supertrend-guard \
  -DCMAKE_PREFIX_PATH=/path/to/Qt/6.8.3/macos -DCMAKE_BUILD_TYPE=Debug
cmake --build /tmp/fincept-supertrend-guard --parallel 2 \
  --target tst_supertrend_input_guard tst_indicator_engine_reference \
  tst_indicator_temporal_contracts tst_indicator_consumer_fix
ctest --test-dir /tmp/fincept-supertrend-guard \
  -R '^(tst_supertrend_input_guard|tst_indicator_engine_reference|tst_indicator_temporal_contracts|tst_indicator_consumer_fix)$' \
  --output-on-failure
python3 -B -m unittest discover -s tests/fincept_audit -p 'test_*.py' -v
```

## Release decision: BLOCKED pending owner review

The input guard is a **proposed signal-affecting strictness change**; it must not be merged or deployed autonomously. Review compatibility with historical data and every `ConditionEvaluator` consumer, decide the ATR EMA/Wilder + first-direction reference separately (sibling #49), inspect rejected-input propagation into fail-closed strategy gates, and run authorized point-in-time full strategy/risk replay and cross-platform/full-app CI before any owner approval.

No actual trading order, demo/live IG operation, credential/PIN access, Fincept installed app/profile, original repo main/canonical branch, privileged runner, paid API, or runtime service was touched. The protected 2022+ holdout remains sealed. **Fincept fork GitHub Actions native CI has not run; a green KAIROS docs check is not equivalent.**
