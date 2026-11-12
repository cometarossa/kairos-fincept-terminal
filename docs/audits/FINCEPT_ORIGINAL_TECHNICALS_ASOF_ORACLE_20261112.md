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

## 2026-11-12 — edge-case characterization & opt-in research-only input guard

The original `volatility_indicators.py` and `momentum_indicators.py` are **still byte-identical** to the fork `main` baseline. Additional tests now run the actual `ta==0.11.0` wrappers on synthetic flat, zero-volume, incomplete and short histories. The Python helper `tools/fincept_audit/technical_preflight_lab_v1.py` is an **independent, explicit opt-in laboratory prototype only**; neither Fincept production nor KAIROS uses it. It returns `{"admissible": false, "reason": "..."}` for insufficient/invalid inputs, does not issue any trading decisions or depend on a network, and inspects no rows after a specified as-of bar.

### Original observed semantics — *not* a trading PASS

| Synthetic case | Observed original result | Research-only guard |
|---|---|---|
| 5 or 13 candles, ATR(14) | `IndexError` (no graceful insufficient-history result) | `INSUFFICIENT_HISTORY` |
| 50 identical OHLC prices | ATR = 0, upper Bollinger = 100, RSI(14) = 100, Stochastic %K = `NaN` | `DEGENERATE_RANGE` |
| Flat close, positive intrabar high/low range | RSI(14) remains 100 even with no price movement | `NO_PRICE_MOVEMENT` |
| Valid moving prices, all volume zero | PVO = `NaN` | `NO_VOLUME` if volume required |
| One missing close at bar 30 of 61 | Bollinger upper stays `NaN` through bar 49; RSI at bar 31 can still be finite | `NON_FINITE_PRICE` while bad row is in requested window |
| Invalid OHLC, duplicated timestamp, infinite prices or negative volume | Upstream wrapper behavior varies; not interpreted as valid data | `INVALID_CANDLE`, `NON_MONOTONIC_INDEX`, `NON_FINITE_PRICE`, `INVALID_VOLUME` |
| Malformed request, `None` / list input | Treated as invalid, not trusted | `INVALID_REQUEST` or `INVALID_INPUT` |

Some behaviors originate in upstream `ta` conventions (not necessarily Fincept-specific bugs). **A finite indicator is not sufficient evidence of valid underlying candles.** In particular, RSI = 100 on a flat close is *not* a bullish signal. The prototype rejects these inputs only if an authorized research consumer explicitly calls it; **it is not installed or enabled inside any signal/trading pipeline**.

### Verifications

- **Combined local Python tests: 15/15 PASS** with `python3 -B -m pytest -q tests/fincept_audit/test_original_technical_indicators_v1.py tests/fincept_audit/test_original_technical_edges_v1.py` on the same isolated iMac environment above: 7 original numeric/source tests + 8 new edge/preflight tests.
- **Negative mutation (test of the guard):** change only the disposable helper's `NON_FINITE_PRICE` return to an unsafe `{"admissible": true, "reason": "OK"}`. The missing-close test **failed as expected** (`'OK' != 'NON_FINITE_PRICE'`); copied workspace deleted afterwards. Separate earlier Bollinger source mutation also produced its expected numeric FAIL.
- The laboratory helper deliberately checks required OHLC input quality, price movement, an as-of index, optional volume, and chronological uniqueness, but it **does not itself establish sufficient indicator-specific warmup, validity of outputs, missingness outside the chosen window, exchange calendar, survivorship, causal features, alpha, risk approval, or execution rights**. A later integration would need additional tests and review.

### Remaining gate

No merge or enablement based on these tests. Audit indicator outputs and all required indicator-specific lookback windows separately, then review how (or whether) KAIROS research consumers might call a guard. Pin exact Git blobs and record branch-head tests; fork Actions CI still unverified.
