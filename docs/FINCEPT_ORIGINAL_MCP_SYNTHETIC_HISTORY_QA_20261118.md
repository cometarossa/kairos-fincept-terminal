# Original Fincept Qt MCP `get_history`: offline synthetic-bars QA

**18 November 2026 — draft review stacked on Fincept #58 (which stacks on #56).** No merge, deployment, broker authorization or trading.

## Why this gate exists

The original `get_history` handler calls `MarketDataService::fetch_history` unmodified, and the current service implementation normally invokes `PythonRunner::run("yfinance_data.py", ...)`. A naive "offline" test could unexpectedly contact a provider. Previous native original-server tests in Fincept #58 already prove synthetic cached `get_quote`, but they do **not** prove `get_history` functionality, truncation and validation.

This change adds an **in-memory selftest-only fixture** inside `MarketDataService`, accessible as a `private` member **only** to the trusted native `run_mcp_server_selftest()` friend function. There is no public setter, configuration key, environment switch or MCP tool for installing it. While armed, `fetch_history` checks the exact `--selftest-mcp-server` process flag, symbol, period and interval. A matching fixture asynchronously returns exactly three synthetic OHLCV rows; **every nonmatching call returns an error without ever launching PythonRunner**. After the original MCP tests complete, the fixture is cleared.

All standard/GUI runs without the fixture continue through the **unchanged** yfinance PythonRunner code. The fixture is not evidence that live history providers work or produce accurate timestamps.

## Real original handler and fail-closed checks

The selftest first creates the fixture for symbol `KAIROSHISTORYQA`, period `1mo`, interval `1d` with three synthetic daily bars on 2024-01-01 / 02 / 03. It calls the **original MCP `tools/call` handler `get_history`** (not a stub) for `limit=2` and checks `count=2`, `total_bars=3`, `truncated=true`, chronological last-bar timestamp, open/high/low/close and volume. It calls the original handler again with `period=3mo` and requires an error with no structured result. Finally the test clears the fixture. The original isolated cache-quote test and optional external KAIROS Python client remain intact and run while the original Qt server is listening on a random 127.0.0.1 port with a test-only bearer token.

This adds four native assertion markers: `synthetic history fixture armed without Python/provider access`, `original get_history MCP returns latest synthetic OHLCV bars only`, `synthetic history mismatched window fails closed without provider`, `synthetic history fixture cleared before end of selftest`. Existing Fincept #58 46-assertion native suite becomes **50 assertions without the opt-in external KAIROS client, and 51 with it**. The native Python wrapper is updated to require all 50 exact markers; older binaries cannot silently pass.

## Evidence, pending prerequisites, next gate

- Four independent Python structural/negative-boundary checks passed on the isolated review checkout, but those **do not replace native runtime acceptance**.
- **Native Qt 6.8.3 full build: 783/783 SUCCESS** with AppleClang 16 on a new isolated macOS Intel build tree, using previously available pinned third-party source trees and **no new downloads**, exact test executable SHA-256 `5e3c503c7081b9edb9905b3297106b2a8fab8dcc185928b318ebc9e23c9ae857`. An initial isolated CMake configure could not find the QtADS `Versioning` module because `FETCHCONTENT_SOURCE_DIR_QTADS` pointed to a different existing source tree. A source-only scratch build-directory symlink resolved the module path; no production repository or third-party source was modified. Final configure/build both PASS. Linker emitted only the existing md4c duplicate-library warning.
- **Four independent source-boundary tests PASS (4/4)**: fixture private/friend-only, exact process-flag + symbol/window guard, no environment/cache route, early return before `PythonRunner`, and cleanup.
- **Original native macOS Seatbelt wrapper PASS (4/4)** in 27.1 s on the exact SHA. Original Qt HTTP MCP server reports **50/50 assertions**, including all four new history markers; the wrapper also verifies the complete native suite enumeration, all headless suites, 52/52 GUI screen constructions and independent external-network denial preflight.
- **KAIROS external Python client → original Qt MCP history PASS (1/1)** using a separate isolated KAIROS review checkout and that exact binary. The original Qt server reports **51/51 native checks** with the external KAIROS child, including valid `get_history` OHLCV, chronological tail, `FINCEPT_RESEARCH_ONLY`, and refusal of forbidden `live_get_history` before I/O. No real provider/IG credentials or sessions. The test has a hardcoded exact executable SHA-256; an older binary cannot pass by reporting exit 0.
- Evidence is **local exact-binary QA**, not GitHub CI and not a merged feature. Source base is Fincept draft PR #58 commit `6b1e9407bb053d85bdd3ce0784918e1de5ddfc55`, itself stacked on #56. Its native test remains opt-in, and a missing binary is an explicit SKIP, never a native PASS.
- Dedicated KAIROS test from a separate draft branch will invoke the original history handler through the existing authenticated, research-only `fincept.history.read` facade and inspect OHLCV, nonauthority flags and refusal of unapproved tool names. No real market provider, Yahoo, IG, credentials, trading or KAIROS runtime scheduler calls.
- This tests **fixture injection, Qt/MCP response shape and cross-process KAIROS interoperability only**. It does not certify scientific alpha, true provider history, OHLCV corrections, market age, slippage or execution economics. Future research must test real provider provenance separately.

**Review order:** Fincept #56 / #58, then this stacked Fincept draft; KAIROS #655 / #665, then the separate external history test draft. Canonical branches stay unchanged; LIVE and any new IG/demo session remain unauthorized.
