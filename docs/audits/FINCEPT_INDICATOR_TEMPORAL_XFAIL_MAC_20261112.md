# Fincept original IndicatorEngine: temporal ADX/Supertrend regression evidence

**Date:** 2026-11-12. **Status:** independent local native macOS diagnostic (not CI and not a fix). This child branch is stacked on Fincept DRAFT #36 at `1a23f7b837d8b6326b5b202a2c3c3ae5a242f2ba` and does not modify original Fincept code.

## Test design

`tools/fincept_audit/qt_unit_harness/tst_indicator_temporal_contracts.cpp` compiles the actual `fincept-qt/src/algo_engine/IndicatorEngine.cpp` (Git blob `cf454fff4dc204a45248bc285f72fd38745e68b7`) through the isolated CMake/Qt6 unit harness. Uses the same 120-bar synthetic integer-cents OHLCV fixture as the independent reference in #36, but checks **temporal properties**, not only one expected final value:

- **ADX(14) previous-vs-prefix:** for each last bar of 81 prefixes (lengths 40–120), compare each returned `previous.plus_di` and `previous.minus_di` against the corresponding `current` value computed on the one-bar-shorter prefix. Independently compare actual DI crossovers (shorter-prefix values) to crossovers visible via the engine's erroneous `previous`.
- **Supertrend(10,3) long ratchet:** compute the source engine on each prefix; whenever the last two prefixes both report `direction=1`, the trailing `value` must **not decrease** under the ratcheting interpretation defined by the independent reference. This counts same-direction transitions, not profitable positions or live execution.

Both temporal properties are represented by **`QEXPECT_FAIL`**, because the original source is known to violate them. A QTest/CTest PASS here **means the defects were reproduced as expected**, not that ADX/Supertrend are correct. Unexpected passes after a future engine fix must trigger a review and retirement of the XFAIL markers, not silent promotion.

## Exact observed local results (Mac, original source)

Official Qt 6.8.3 `qtbase` clang_64 SDK in an isolated development cache, macOS 14.5, CMake 4.0.1, AppleClang 16:

| Property | Tested | Observed |
|---|---:|---:|
| ADX previous +DI / −DI | 162 values (81 prefixes × 2) | **162 mismatches** to true previous prefix |
| ADX DI crossovers | 20 true changes of DI ordering | **20 masked** by original `previous` fields |
| Supertrend same-direction long transitions | 106 | **65 decreases** of the long-side line |

- **Native CTest 3/3 PASS:** original `tst_indicator_engine`, DRAFT #36's `tst_indicator_engine_reference`, and new `tst_indicator_temporal_contracts`. The new native QtTest run reports **two XFAIL** with the numerical counts above, plus ordinary PASS setup/cleanup.
- **Python contract tests 12/12 PASS:** eight inherited reference/provenance tests from DRAFT #36 and four new source/cmake/fixture checks.
- Published input blob identities were checked locally before the repeat test: modified CMake `a718b1edce0db34b5697e20f07fc7cc0059a6c3d`; native C++ test `a7745c0fb9f2ef8b762a1255f9de02fcb4e4abeb`; Python test `ca6ac17e4aa200080e3c328374b0c682fb9b56a7`, plus unchanged original engine `cf454fff4dc204a45248bc285f72fd38745e68b7`.
- **Non-vacuity negative control:** in a separate disposable compilation, removed the two `QEXPECT_FAIL` lines from the *test only* and compiled it again against the unchanged engine. Native QtTest **FAILED exactly twice** (the ADX prior-value contract and Supertrend long-ratchet contract). The negative runner checked both failure names and deleted the temporary build. No source was fixed or patched.

## Reproduction

On a checkout with this draft atop DRAFT #36, original Fincept `main` source and Qt6.8.3 development libraries:

```sh
cmake -S tools/fincept_audit/qt_unit_harness -B /tmp/fincept-temporal-test \
  -DCMAKE_PREFIX_PATH=/path/to/Qt/6.8.3/macos -DCMAKE_BUILD_TYPE=Debug
cmake --build /tmp/fincept-temporal-test \
  --target tst_indicator_engine tst_indicator_engine_reference tst_indicator_temporal_contracts
ctest --test-dir /tmp/fincept-temporal-test \
  -R '^(tst_indicator_engine|tst_indicator_engine_reference|tst_indicator_temporal_contracts)$' \
  -V --output-on-failure
python3 -B -m unittest discover -s tests/fincept_audit -p 'test_indicator_*.py' -v
```

**Scope / limitations:** These are synthetic prices, not a backtest, not market observations, not evidence of market edge, and not a fix to signal-producing source. ADX DI crossovers relying on the `previous` map are not trustworthy as implemented; Supertrend ratchet/direction require a separately authorized patch and independent retesting. No claim about any particular strategy having executed or lost money. The order-validator native target remains unbuildable independently (see #36), and was **not** included in the three-test run. No broker connection, PIN action, existing Fincept installation, personal profile, privileged runner, paid service or runtime process changed. The Fincept fork GitHub Actions did not run. Keep DRAFT/NO MERGE pending owner review of signal-affecting changes.
