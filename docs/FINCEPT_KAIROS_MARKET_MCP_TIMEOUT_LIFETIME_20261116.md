# Fincept original MCP market-data lifetime — 2026-11-16

**Status: source fix + native helper test, DRAFT. Not a full Qt app build, read-only broker integration or scientific admission.**

## Why this is a KAIROS blocker

The operator requires KAIROS to use Fincept as a **functioning advanced financial terminal**, with all broker session access centralized to prevent the recurring IG account lockouts. The first F1 tools must therefore be reliable, bounded **read-only market access** rather than order entry.

Original `fincept-qt/src/mcp/tools/MarketsTools.cpp` had two callbacks that captured handler-stack data by reference:

- `get_quote`: queued `fetch_quotes` callback captured `&ok` and `&q`.
- `get_history`: queued `fetch_history` callback captured `&ok` and `&points`.

The shared `detail::run_async_wait` gives up after 120 seconds, but it **does not cancel an already scheduled callback**. A late reply could write to a destroyed stack frame (undefined behavior, potential crash). The helper's existing documentation explicitly warns about this residual hazard. It is unrelated to whether an individual yfinance fetch succeeds.

## Narrow fix

- Introduce a Qt-free original-source `detail::BoundedAsyncResult<T>` at `fincept-qt/src/mcp/tools/BoundedAsyncResult.h`.
- Both handlers capture a `shared_ptr` to the state **by value** at each asynchronous step; there are no stack-result references retained in service callbacks.
- Callback `complete(success, payload)` updates status and payload atomically under `std::mutex`, then releases the mutex **before** notifying `signal_done()`.
- The worker calls `take()` only after `run_async_wait` returns. This seals the state, yields the first result or a default failure, and ensures any later/duplicate `complete` cannot change a completed handler response.
- No change to the original MarketDataService, its networking or caching policy, ticker mapping, the data/response schema, original GUI, order handling, IG credentials, login frequency, broker API or Gate9R.

## Evidence on the isolated iMac

The new source header is compiled by the **native Apple Clang++** compiler, not replaced with a test mock, in an offline C++17 test harness. Test scenarios include:

1. Complete-before-consume: consistent quote and history result.
2. Missing callback: fail closed with a default result.
3. Delayed callback after `take()`: ignored safely.
4. Duplicate callback: first completion wins.
5. Handler stack released while callback remains: shared lifetime retained and freed afterward.
6. 500 concurrent race iterations: matching sequence and payload whenever a result is accepted.
7. Original source wiring checks confirm both `get_quote` and `get_history` use shared state and no `&ok`, `&q`, `&points` capture.

Run from the fork root:

```bash
python3 -m unittest discover -s tests/fincept_original -p 'test_mcp_market_async_lifetime.py' -v
```

Verified locally: **3/3 unittest PASS**; standalone `mcp_async_lifetime_native.cpp` compiled/run also with **AddressSanitizer PASS**. No network, account, quote provider, broker, or order operations. A Qwen4-Max **English design review** checked shared lifetime, mutex ordering, Qt thread affinity, late/double signaling and the limitations of the wait primitive; this was a proposal review, **not** a compilation of the complete Qt app.

## Explicit limitations / next gates

- **Original Qt6 application and full tool handler were NOT recompiled/tested at this PR head**. The prior Debian VM screenshot showing the original main window proves startup of a different installed binary, not this patch.
- `ThreadHelper.h` still contains a *separate same-thread nested-loop pointer lifetime path*; its callback/waiter behavior needs an independent exact-source review before claiming all async safety issues solved. This patch does not modify that helper or other tools.
- A race at the boundary of `run_async_wait` timeout can yield a callback completion before `take()` seals the state; this is a safe and coherent value, **not a guaranteed categorical timeout rejection**. No deadline/result status was added to the public API.
- `MarketDataService` can serve cached or stale quotes and `QuoteData` does not carry market-as-of provenance. Therefore **KAIROS MUST NOT interpret these read-only tool responses as certified fresh or execution-safe**; as-of/source/TTL and explicit stale status require a separate F1 contract + offline tests.
- Original Fincept app CMake is C++20 with Qt 6.8.x; the new helper is C++17-compatible but the full original C++/Qt build remains **NOT_VERIFIED** here. Fincept `.github/workflows/build-cpp.yml` is `workflow_dispatch` only: a green Python test does not imply a full Qt build.
- PR stays DRAFT/PENDING; admission requires independent exact-source review, original Qt build, and existing KAIROS/Fincept capability+authentication design reconciliation. No second IG session, broker mutation or LIVE authorization is introduced.
