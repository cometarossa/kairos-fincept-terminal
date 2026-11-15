# Source-real Screener Criteria Builder QA (2026-11-15)

**Status: DRAFT / NATIVE EXECUTION PENDING.** This is a QA-only harness. It
compiles the **unmodified original** Qt Widgets implementation, not a Python
rewrite or mock of the query logic. No Fincept product code is edited.

## Pinned original inputs

- Fork original `main` commit: `7716ee8613249fb44c4d14036c5bc16ed6f34e97`
- `fincept-qt/src/screens/screener/ScreenerCriteriaBuilder.cpp`: blob
  `0bd59d3911b32f3758de04e2b6b6b20eebd4be0c`
- `ScreenerCriteriaBuilder.h`: blob `e9eb9c7eb1c268b0265f8ac22b7cb889964c1999`
- `fincept-qt/src/services/screener/ScreenerService.h`: blob
  `7358f93addd4c80d7ad242c24c3a0b6a71bdfbd1`

**Compile the QA branch against its untouched original source tree; verify the source blobs against the exact pinned original commit.**
Do not run on the installed Fincept application/profile or fetch market data.

## Reproduction once Qt is available

```sh
# Run from this isolated QA branch checkout; independently verify its original
# fincept-qt/src file blobs against fork main 7716ee8613249fb44c4d14036c5bc16ed6f34e97.
cmake -S tools/fincept_audit/qt_screener_criteria_native \
  -B /tmp/fincept-original-criteria-qa \
  -DFINCEPT_SOURCE_DIR="$PWD/fincept-qt/src" \
  -DCMAKE_PREFIX_PATH="/path/to/Qt/6.8.3/macos" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/fincept-original-criteria-qa --parallel 2
QT_QPA_PLATFORM=offscreen \
  ctest --test-dir /tmp/fincept-original-criteria-qa -V --output-on-failure
# Run separately, report actual failures rather than hiding as a passing suite:
QT_QPA_PLATFORM=offscreen \
  /tmp/fincept-original-criteria-qa/tst_original_screener_criteria --probe-defects
```

Minimum tested-in-CMake dependency declaration is Qt 6.4 (Widgets, Core,
Gui, Test, Sql); the **exact Qt build/version actually run must be reported**.
No claim of Qt 6.8.3 success is made by the mere presence of this harness.

## Coverage in the baseline executable

- No catalog/no criteria refuse a request.
- Synthetic catalog produces default US-major-exchange, market-cap >= 2B,
  descending query, without touching Yahoo.
- Catalog field labels, count/offset preserved (builder does not change paging).
- Explicit custom region, sector, industry, exchange group, two filters and
  ascending sort round-trip through `load_query -> build_query`.
- Invalid text and missing BETWEEN upper bound fail with an error and visible
  invalid-cell state; output is not partially overwritten.
- Corrected value can be built; empty unfiltered query refused; predefined
  input is not silently converted to a custom query.
- Programmatic loads do not emit user-edit events.

All of these are **test expectations**, not observed PASSes, until native
build/CTest output is attached for the exact source and QA commit.

## Deliberately separate strict probes / potential bugs

The optional `--probe-defects` mode makes two explicit fail-closed assertions.
They are source-informed *hypotheses to verify*, not yet reproduced runtime
defects:

1. `parse_value` checks finite numeric input **before** multiplying a
   `K/M/B/T` suffix, with no apparent post-multiplication finite check.
   Extremely large numeric input such as `1e308T` could become Infinity and
   be accepted into a structured filter.
2. `set_catalog` clears `fields_by_id_`, but if the replacement catalog
   has no fields then `reset_to_default` returns immediately; old criteria
   rows may remain and `build_query` does not explicitly require
   `has_catalog()`, possibly allowing a stale field to be sent.

The original builder also **sorts** reversed BETWEEN bounds instead of rejecting
them; this is observable source semantics, not a separately verified GUI policy
decision. Establish the intended product behavior before classifying it a bug.

Do not convert any of these into an asserted PASS, CI success, or product
certification without an exact-source native test run. A code fix, if needed,
should be independent of this QA-only draft and have its own regression tests.

## Safety and completeness

No original code under `fincept-qt/` changed. The fixture is synthetic and
never creates a provider, saved screen, watchlist, QSettings, service, socket,
broker connection, order, account session, persistent app profile, or remote
model call. `QT_QPA_PLATFORM=offscreen` avoids showing a screen. The complete
Screener GUI, real Yahoo queries, persistence, provider error path, user PIN,
full terminal launch and KAIROS tool registration remain **NOT VERIFIED**.

This draft intentionally **does not add a GitHub Actions workflow**, modify
the installed application, or merge itself. The 25/25 ScreenerResultsModel
evidence in draft #51 is separate and is **not rerun or recounted** here.
