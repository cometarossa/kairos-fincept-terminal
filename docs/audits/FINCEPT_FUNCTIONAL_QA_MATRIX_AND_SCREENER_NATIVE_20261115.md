# Fincept × KAIROS — 34-capability QA matrix and original native Screener Results test

**Date:** 2026-11-15 (Europe/Rome)  
**Source fork:** `cometarossa/kairos-fincept-terminal` **main** `7716ee8613249fb44c4d14036c5bc16ed6f34e97`  
**Classification:** QA ONLY / DRAFT / NO APP DEPLOYMENT / NO BROKER / NO MARKET DATA / NO SCENTIFIC OR RELEASE APPROVAL.

## Scope — full feature preservation needs real tests, not source-counting

The owner explicitly requires Fincept to keep **all its existing useful functionality** while becoming a KAIROS agent tool, before any new IG DEMO API work. This milestone merges **evidence visibility**, not source branches or runtime code, and fills a previously untested component of the Screener with an **actual native C++ functional test**.

Prior source-backed work was **reused rather than repeated**:
- [Fincept DRAFT #5](https://github.com/cometarossa/kairos-fincept-terminal/pull/5): 25 source-level entrypoints.
- [#11](https://github.com/cometarossa/kairos-fincept-terminal/pull/11): historical Debian VM evidence on C++ Algo, VectorBT, Backtesting.py and provider metadata; no full GUI certification and known dependency/financial limitations.
- [#26](https://github.com/cometarossa/kairos-fincept-terminal/pull/26): source-level invariants for **52 routes, 35 original widgets, six dashboard presets**, plus five actually executed original Python technical families (82 output columns). The 52/35/6 inventory is **NOT a runtime pass**.
- [#27](https://github.com/cometarossa/kairos-fincept-terminal/pull/27): original portfolio metrics oracles and four reproduced calendar/coverage data-quality gaps; component run, not scientific approval.
- [#41](https://github.com/cometarossa/kairos-fincept-terminal/pull/41): original multi-asset VectorBT provider with independent synthetic trade/equity oracles, known `totalFees` multi-asset reporting defect (candidate fix separately in #40).
- [#43](https://github.com/cometarossa/kairos-fincept-terminal/pull/43): actual original `StatusBadge` and `SearchBar` QtWidgets offscreen tests, not a full terminal GUI.
- [#46](https://github.com/cometarossa/kairos-fincept-terminal/pull/46), [#49](https://github.com/cometarossa/kairos-fincept-terminal/pull/49), [#50](https://github.com/cometarossa/kairos-fincept-terminal/pull/50): ADX/Supertrend numerical and input-convention changes under review, **NOT MERGED**. Do not count these draft candidates as production-corrected.

### Machine-readable capability ledger

`docs/audits/FINCEPT_FUNCTIONAL_CAPABILITY_MATRIX_V1_20261115.json` freezes **34 unique source paths** with exact original Git blob, evidence class, previously tested component/pr and the separate full-product functional verdict:

| Coverage bucket | Count | How to interpret it |
|---|---:|---|
| Previously/currently **component-tested** in a bounded environment | **11** | Original technical calculation, historical synthetic provider/portfolio work or isolated native Qt components; each claim is *narrow* and prior evidence is dated |
| Source present, **no functional run cited** for this exact entrypoint | **20** | The class/module exists; execution and service integration remain NOT VERIFIED |
| Broker mutations forbidden for KAIROS | **3** | Order placement, cancellation, leverage change — intentionally not run |
| **Full application features certified** | **0** | GUI screen composition, data-provider continuity, storage, end-to-end model calls and actual Fincept-to-KAIROS integration are **NOT VERIFIED** |

The 34 entries are the original 25 from #5 plus **nine** specifically identifiable, source-pinned tests/modules. This is **not a complete enumeration of every menu button** in Fincept. Every allowed full workflow retains `full_feature_status=NOT_VERIFIED`, regardless of its component test status; forbidden broker paths retain `FORBIDDEN_BY_KAIROS_CONSTITUTION`.

**10/10 independent Python source/matrix contract tests PASS** on the exact source checkout. They verify all 34 source files' original Git blobs byte-for-byte; assert unique identifiers, no false full-app PASS, exact evidence PR associations, three immutable broker exclusions, Qt test seam and negative-sort assertions. The matrix itself does not claim new Python functional runs today.

## NEW 2026-11-15: native original Screener Results Model

**Unmodified original C++**:
- `fincept-qt/src/screens/screener/ScreenerResultsModel.cpp` Git blob `80506006545c2e4fcb1c3f928120f218da55e406`
- `ScreenerResultsModel.h` Git blob `c4e0b39e954ceddd2d60b22ce1143070e55e969b`
- original `LiveTableModel.h` Git blob `0d91882fd6753fa5a581186eb9d0d07376302a08`
- original `ScreenerService.h` Git blob `7358f93addd4c80d7ad242c24c3a0b6a71bdfbd1`

**Toolchain:** native macOS AppleClang 16, official locally cached Qt **6.8.3 Core/Gui/Test/Sql**, CMake. No Fincept app or QtWidgets window was launched. The C++ target compiles **the actual original ScreenerResultsModel.cpp**, original model header and original service data types. Only the **theme color lookup** is replaced with a test-only stub to avoid initializing the entire installed GUI/theme system. The test does NOT stub sorting, table data, row identity, formatting or update logic.

**Actual `ctest` source-real result: 1/1 native suite PASS, 25/25 assertions PASS**, using only three deterministic synthetic rows `AAA, BBB, CCC`. Verified cases:

- ten base headers plus a changing extra column; symbol/name search role; key-index lookup;
- numeric price sorting ascending **and descending**, with invalid/missing prices **last in both cases**, not lexicographically;
- formatted prices, positive/negative percent signs, compact volumes and sub-unit prices;
- missing Price as `—` and an invalid numeric sorting key;
- a changed price on stable row keys emits `dataChanged` **without model reset**;
- a changed extra column identity resets/rebuilds the schema correctly;
- missing dynamic numeric fields stay explicitly invalid for sorting.

**Independent real C++ negative control:** in a *disposable temporary copy*, changed exactly the original `return a.toDouble() < b.toDouble();` numeric comparator to `>` and compiled the **same** test. The altered implementation returned expected **0/1 native suite FAIL**, with **2 specific failures**: ascending and descending numeric sorting. The original source was unchanged and the temporary build removed. The positive test initially used a wrong expected sign for a growth metric and was corrected **only in the test** to expect `+11.50%`; no source fix was needed.

### Reproduce in an isolated checkout; no account or GUI installation

```sh
# source tree must equal the exact original fork base SHA above.
cmake -S tools/fincept_audit/qt_screener_results_native \
  -B /tmp/fincept-screener-original-qa \
  -DFINCEPT_SOURCE_DIR="$PWD/fincept-qt/src" \
  -DCMAKE_PREFIX_PATH=/path/to/Qt/6.8.3/macos \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/fincept-screener-original-qa --parallel 2
ctest --test-dir /tmp/fincept-screener-original-qa -V --output-on-failure
python3 -B -m unittest discover -s tests/fincept_audit \
  -p test_functional_capability_matrix_v1.py -v
```

The special `-DSCREENER_CPP_SOURCE` override in this **test-only CMake harness** permits repeatable negative controls on a temporary altered source file; it is **not** an alternate production source path. Do not use it to compile shipping code.

## Significant open product and integration blockers

1. **GUI/product:** Qt full app build, 52 screens, dashboard compositions/saved presets, user PIN isolation and File Manager/Equity screen freeze **NOT VERIFIED** by this test. Native two-widget #43 and source-preservation #26 do not substitute for a complete GUI test.
2. **Screener:** sorting and row presentation **component PASS**, but Yahoo screener queries, saved filters, watchlist persistence, network failures, catalog updates and screen navigation **NOT VERIFIED**. Do not label "Screener PASS" globally.
3. **Backtesting:** VectorBT original provider may report total slippage incorrectly; multi-asset `totalFees` original defect is under separate review. Realistic costs, PIT data, walk-forward, multiple engines and entire GUI remain **NOT VERIFIED**.
4. **AI Quant Lab/LLM/MCP:** source presence and catalogues do not prove calculation, model retraining, authenticating KAIROS agent identity or prompt/model spending restrictions. No general authenticated Fincept tool server has been admitted; KAIROS draft #645 is only one synthetic fixture call.
5. **Science and broker safety:** no market dataset was used in this audit. Synthetic outputs cannot prove market edge. All KAIROS broker mutation entrypoints remain denied, no IG DEMO/LIVE activity or API session. Never give an LLM the raw Fincept MCP mutation catalog.

**Fork GitHub Actions native CI:** NO VERIFIED RUN for the new exact commit; this is **local Mac native QA**, not multi-platform CI or installed app regression certification.

## Next scoped QA

The next independent Fincept-first test should cover the **read-only ScreenerCriteriaBuilder with synthetic field catalog**, including invalid range/input handling and query serialization, then separately integrate a fully isolated screener screen lifecycle test without touching real saved screens, live providers or account keys. In parallel reconcile Fincept #25 ↔ KAIROS #641/#645/#647/#649/#650/#651 draft tool bridge and prioritize an authenticated deny-by-default read-only capability registry. No IG until Fincept tooling and functional QA are independently admitted.

**No production Fincept C++ code, installed application/profile, PIN, broker, external API, model, service, privileged runner, GitHub main/canonical branch or protected holdout modified.** 
