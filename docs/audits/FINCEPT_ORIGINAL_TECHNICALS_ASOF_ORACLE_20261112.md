# Original Fincept Python technical indicators — synthetic as-of-T oracle

**Date:** 2026-11-12. **Scope:** independent, offline numeric verification of a small subset of Fincept's unchanged Python technical-analysis wrappers. This is neither broker code nor strategy evaluation.

## Pinned exact upstream source

Fork `main` at `7716ee8613249fb44c4d14036c5bc16ed6f34e97`. The test imports original files directly, without copying indicator logic into production:

- `fincept-qt/scripts/technicals/volatility_indicators.py`, Git blob `d991f5448be1e16675f511993896b3f8edea1059`.
- `fincept-qt/scripts/technicals/momentum_indicators.py`, Git blob `6af1b869f7b7f1f94fca829d8ce704a78a81bef6`.

Run environment: isolated file export in a private iMac QA cache, Python 3.9.9, `ta==0.11.0`, `pandas==2.2.3`, `numpy==1.26.4`, `pytest==8.4.2`. No new Python dependencies or package installation was needed; these versions were **observed**, not inferred from repository manifests.

## Positive test result (local)

**7/7 `unittest` checks PASS** with a deterministic synthetic fixture of 83 timestamped OHLCV bars (UTC dates):

1. Git blob SHA of original source files is exactly pinned, rejecting source drift.
2. **ATR(14)**: manual independent true-range calculation and Wilder-smoothed ATR; warmup zeros and multiple selected bars checked.
3. **Bollinger(20, 2)**: independent trailing arithmetic mean and population standard deviation; warmup NaNs and upper/mid/lower values checked.
4. **Stochastic(14,3)**: independent rolling high/low range, %K and 3-bar mean %D; warmup and selected bars checked.
5. **RSI(14)**: independent scalar Wilder-EMA recurrence with initial zero delta, matching `ta`'s `adjust=False` convention; warmup NaN and selected bars checked.
6. **As-of-T prefix nonleakage**: modifying all OHLC values after synthetic bar 49 does not change its ATR, Bollinger upper band, RSI or Stochastic %K; the 50-bar prefix matches the full 83-bar series at the same timestamp.
7. **Oracle internal negative probe**: a deliberately substituted lower Bollinger band cannot pass the independent upper-band comparison.

Numerical comparisons use explicit tolerances, not string matches, and use the original `calculate_*` functions from both modules. This is a narrow numeric cross-check, not broad library/API verification.

## Separate real source-mutation negative control

In an ephemeral copied *production* `volatility_indicators.py`, changed only `'bb_hband': indicator.bollinger_hband()` to `indicator.bollinger_lband()`. Re-ran the same `test_bollinger_independent_population_reference` against the mutated original module. **EXPECTED FAIL (1 selected test, 4 failing bar subcases)**; the harness identified `bb_hband` mismatches at bars 19, 35, 49 and 82. Mutation occurred only in a temporary directory; it was removed. This proves the comparison can detect a broken real wrapper.

## Reproduction

From an isolated checkout with the exact original source blobs and `ta==0.11.0`, `pandas`, `numpy` available:

```sh
python3 -B -m unittest discover -s tests/fincept_audit \
  -p test_original_technical_indicators_v1.py -v
```

**Boundaries:** no market prices (all OHLCV data synthetic); no retrospective alpha, protected holdout, real returns or prediction quality evaluated. This does **not** establish that Fincept's 24+ indicators, C++ IndicatorEngine, Backtesting, full GUI, bridge integration or trading execution work correctly. The four selected indicators also do not validate network feeds or corporate-action adjustments. No live/demo access, secrets, orders, cash movement, daemon restart, native app profile or runner modification. Fork GitHub Actions CI remains separately unverified; local PASS does not equal CI success. DRAFT only, independent review required before integration.
