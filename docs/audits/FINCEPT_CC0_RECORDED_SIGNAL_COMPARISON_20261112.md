# Fincept — recorded CC0 adjusted OHLCV, old vs fixed ADX/Supertrend signal-only replay

**Date:** 2026-11-12. **Status:** local, read-only research diagnostic / **NOT PIT / NOT STRATEGY P&L / NOT DEPLOYED**. This branch stacks on [Fincept DRAFT #46](https://github.com/cometarossa/kairos-fincept-terminal/pull/46), the isolated signal-affecting C++ fix. No production code is modified in this replay branch.

## Source and custody (independently reverified)

The already acquired, legally public **Kaggle CC0 Huge Stock Market Dataset** archive was opened **read-only** in the Mac KAIROS research quarantine. Full archive SHA-256 matched the frozen source record: `d9317c8fb2d63b9b00db5f933b6c9639d2bf7ea3b918169bb5cec5903dce85a1` (**515,591,518 bytes**). No download, API, market subscription, browser credential, broker, service or raw data export was required.

Precommitted fixed instrument set and member CRC identities:

| Instrument | ZIP member (unique canonical member) | ZIP member CRC32 | 2014-01-02 to 2017-11-10 daily rows | Canonical filtered input SHA-256 |
|---|---|---:|---:|---|
| AAPL | `Stocks/aapl.us.txt` | 3021795949 | 974 | `fac5f8d07174dc27acb06485a71a7d9cd06909b1f6a3baa2c8d1877f1c065840` |
| IBM | `Stocks/ibm.us.txt` | 2247021503 | 974 | `ebeb652f41e3902dd8d32bbe291bccab5bf1bbdbe17dbb40fcf3cc18e90c94e5` |
| SPY | `ETFs/spy.us.txt` | 2487404040 | 974 | `012248c39533d9d6825d4601271968b97aa122193644a0660dbeaab41a5b53cc` |

The archive is frozen, but prices are **retrospectively adjusted**, do **not** certify the vintage available in each historic trading session, and include severe survivorship and selection biases. This source is permitted only as `DEVELOPMENT_DIAGNOSTICS_ONLY` under KAIROS's equity PIT roadmap. The **2022+ protected holdout was never opened**. Only three selected historical members were read; no archive files or OHLCV rows were copied to the repository or supplied to the broker/model. The report includes aggregate rule counts and hashes only.

## Exact code comparison

- **Original engine:** fork `main` `7716ee8613249fb44c4d14036c5bc16ed6f34e97`, `fincept-qt/src/algo_engine/IndicatorEngine.cpp`, Git blob `cf454fff4dc204a45248bc285f72fd38745e68b7`.
- **Correction candidate:** [DRAFT #46](https://github.com/cometarossa/kairos-fincept-terminal/pull/46), `IndicatorEngine.cpp` blob `7d3c32ca4d9f4a265a77dbbe56d59b52129ecfb5`.
- **Both binary builds link the same original, unchanged** `fincept-qt/src/algo_engine/ConditionEvaluator.cpp`, Git blob `1ae2adbd70fa143f528928338184da336ca0bc6d`. The standalone C++ CLI has **no broker, application, service, network or trading dependencies**, and only reads a verified CSV stream from Python on stdin.
- Isolated macOS development cache, CMake 4.0.1, AppleClang 16, official Qt6.8.3 Core+Gui. No installed Fincept application, user profile, PIN or daemon was touched.
- **Input**: all complete daily candles from 2014-01-02 to 2017-11-10; 2014 is warmup/history. **Evaluation**: one closed-bar candle prefix at a time, **722 source dates for each instrument from 2015-01-02 through 2017-11-10**. Each engine evaluates the same nine fixed comparisons via the original `ConditionEvaluator::evaluate_single` on `all.mid(0,n)`. Errors, malformed OHLCV, unsorted timestamps, missing fields and unexpected source/version hashes **fail closed** rather than being skipped.

## Observed differences — recorded adjusted historical data, no trades

| Instrument | Evaluated instrument-days | Old Supertrend long-state days | Fixed long-state days | Fixed short-state days | Unique dates with one or more rule changes | Rule-date changes (multiple can occur on one day) |
|---|---:|---:|---:|---:|---:|---:|
| AAPL | 722 | 722 | 356 | 366 | 567 | 1,653 |
| IBM | 722 | 722 | 299 | 423 | 608 | 1,880 |
| SPY | 722 | 722 | 436 | 286 | 561 | 1,427 |
| **Total** | **2,166** | **2,166** | **1,091** | **1,075** | **1,736** | **4,960** |

- **ADX crossings as actually evaluated by `ConditionEvaluator`: unchanged** for all three instruments. `crosses_above` counts AAPL 29 / IBM 28 / SPY 40; `crosses_below` counts 28 / 27 / 40; each old count equals the candidate count **on the exact same dates**. This is consistent with the evaluator's recomputation of previous values using an earlier candle prefix, without reading the faulty direct `IndicatorResult.previous` map.
- **Supertrend:** the old engine reported `direction=1` on all 722 days for all three instruments, while the corrected one registers substantial short-direction intervals. The recorded rule differences also affect `value rising/falling`, `direction crosses above/below zero`, and `value relative to CLOSE`. These are **condition values only**; a single row can contribute changes to multiple rules, so the figure 4,960 must never be described as trades, decisions or unique dates.
- Unique dates with one or more rule changes: **1,736 of 2,166 instrument-days (~80.1%)**. This is a *signal-behaviour regression magnitude in an ineligible historical diagnostic dataset*, **not evidence that the correction creates more trading opportunities or improves returns**. No entry/exit combinations, stops, slippage, transaction costs, position sizing or P&L were assessed.
- Machine-readable **aggregate-only** report: `docs/audits/FINCEPT_CC0_RECORDED_SIGNAL_AGGREGATES_20261112.json`. It contains no daily price or per-date signal series. Raw ZIP stays in its quarantined location.

## Positive tests and mandatory negative controls

- **Mac native Qt source-linked build PASS** for `recorded_replay_old` and `recorded_replay_candidate`. Both compiled from explicitly SHA-pinned source (the old engine retrieved from the same fork main object, candidate from DRAFT #46).
- Historical replay PASS on three selected ZIP members after independently computing the entire archive SHA-256, checking per-member CRC32, 974 rows, exact date range, exact baseline/candidate/consumer Git blobs, nine-rule output schema and strict expected instrument-level counts.
- **Offline unittest 7/7 PASS**, includes source identity check, original evaluator linking, as-of closed-bar property, mask parsing and difference arithmetic, invalid output rejection, CRC failure and **sanitized report exact-shape assertions**.
- **Negative 1 — duplicate binary:** run the old executable for both inputs. Expected **FAIL `NONVACUITY_OR_ENGINE_MISWIRE:AAPL`**, no report written. Successfully observed and temporary files cleaned.
- **Negative 2 — modified archive:** pass a temporary bogus archive. Expected **FAIL `ARCHIVE_SHA256_NOT_FROZEN_CC0`**, no report written. Successfully observed and temporary files cleaned.
- The upstream strict candidate from #46 has separate macOS CTest 6/6 and Python 18/18 local PASS. The replay tests **do not replace** those numerical/regression tests or any GitHub Actions runs.

## Reproduction (authorized local copy, no market download)

On a checkout containing this child PR and an authorized read-only CC0 archive at `$CC0_ARCHIVE`, with Qt 6.8.3 and the fork main source object locally available:

```sh
mkdir -p /tmp/fincept-cc0-replay-source
git show 7716ee8613249fb44c4d14036c5bc16ed6f34e97:fincept-qt/src/algo_engine/IndicatorEngine.cpp \
  > /tmp/fincept-cc0-replay-source/original.cpp
cmake -S tools/fincept_audit/recorded_replay -B /tmp/fincept-cc0-replay-build \
  -DCMAKE_PREFIX_PATH=/path/to/Qt/6.8.3/macos -DCMAKE_BUILD_TYPE=Release \
  -DOLD_INDICATOR_ENGINE_SOURCE=/tmp/fincept-cc0-replay-source/original.cpp
cmake --build /tmp/fincept-cc0-replay-build --parallel 2
python3 -B tools/fincept_audit/recorded_replay/run_public_cc0_replay_v1.py \
  --archive "$CC0_ARCHIVE" \
  --old-bin /tmp/fincept-cc0-replay-build/recorded_replay_old \
  --fixed-bin /tmp/fincept-cc0-replay-build/recorded_replay_candidate \
  --old-engine /tmp/fincept-cc0-replay-source/original.cpp \
  --fixed-engine fincept-qt/src/algo_engine/IndicatorEngine.cpp \
  --consumer-source fincept-qt/src/algo_engine/ConditionEvaluator.cpp \
  --report /tmp/fincept-cc0-replay-aggregate-only.json
python3 -B -m unittest discover -s tests/fincept_audit \
  -p test_recorded_cc0_replay_contract_v1.py -v
```

The actual archived price dataset is never packaged with the pull request. Missing source, wrong hash, absent Qt, unreliable binary, insufficient or malformed candle input: **BLOCKED, not PASS**.

## Strict release boundary

**No merge, no deploy, no strategy promotion.** This is a frozen-vintage, survivor-biased, retrospectively adjusted 2015–2017 replay. It does not demonstrate original point-in-time publication, independent external mathematical review, completeness of delisted securities, any actual historical portfolio or executable orders, and cannot safely estimate strategy performance. Before making the signal-affecting #46 operational, independently review exact ADX/Supertrend conventions, use authorized PIT-eligible data with the protected holdout sealed, compare full strategy entry/exit and risk gates, verify Linux/Windows and full-app CI, and obtain explicit owner approval. Existing KAIROS #632 runner-trust and `tst_order_validator` test blockers remain separate and unresolved. Fincept fork Actions has **no exact-head green CI evidence**.
