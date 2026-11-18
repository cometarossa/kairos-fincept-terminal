# Original Fincept Qt → PythonRunner → Yahoo → MCP → KAIROS: bounded QA

**18 November 2026. DRAFT, NOT MERGED / NOT DEPLOYED.** This is a deliberately opt-in *diagnostic test harness*, **not a claim that real public provider history works through Qt**, not verified trading data, and not a new broker capability. Source base is Fincept DRAFT #62 exact commit `c0eb021d70deff33bf1b0c86e49fe5d4486a1280`, itself stacked on #61→#58→#56→#55.

## What was built

- In the original `McpServerSelfTest.cpp` (`--selftest-mcp-server` only), after its validated **synthetic** history fixture is cleared, an extra **opt-in** isolated probe becomes eligible **only** with exact `FINCEPT_PUBLIC_MCP_HISTORY_QA=SPY_5D_PUBLIC_READ`, absolute child script and Python paths, a loopback-only `HTTPS_PROXY` setting, and a separate sandbox preflight result (`FINCEPT_PUBLIC_QA_SANDBOX_VERIFIED=EPERM_EXTERNAL`). Invalid/partial configuration records FAIL and invokes no provider. The original Qt server continues to use a random localhost port, short-lived bearer and `allow_actions=false`; no new MCP API or runtime tool is added. Original `get_history` and KAIROS `fincept.history.read` remain unchanged.
- The original `PythonRunner` skips retrieval and injection of **all** SecureStorage-managed API/broker/LLM secrets when **both** original selftest flag and exact public Yahoo QA opt-in are present. Its normal application `yfinance_data.py` **persistent daemon routing is explicitly preserved** (a separate QA-only subprocess attempt was unsuccessful and was removed rather than being presented as a runtime fix).
- `tests/fincept_original/public_yahoo_only_connect_proxy_v1.py` is a **temporary localhost-only CONNECT proxy** with explicit four-host allowlist: `query1.finance.yahoo.com`, `query2.finance.yahoo.com`, `fc.yahoo.com`, `finance.yahoo.com`, all port 443. No GET/POST/other host, broker IP, LAN host, or public listening socket. No TLS interception, response logging, cookies, quotes or tokens are recorded. It limits **all connections to 24** (including deliberately refused ones), enforces per-direction byte and duration budgets, then is terminated by the caller.
- KAIROS opt-in companion QA runs the original Qt process in macOS Seatbelt (only 127.0.0.1 outbound), first verifies that an external socket returns `EPERM`, and sends a deliberately forbidden `CONNECT demo-api.ig.com:443` to the local proxy, expecting `403`. That is **not an IG connection**. It then permits a **single top-level `SPY` 5d/1d history operation** using the original KAIROS authenticated research-only client, with no retries, optional activation only, explicit selected native binary SHA and proxy-source SHA.
- The original Python `yfinance_data.py` daemon is tested separately with fake pandas Ticker + genuine framed input/output: ready handshake, `historical_period`, two timestamped OHLCV bars, and shutdown; error object after simulated provider failure. No network in those tests.

## Observed evidence — separate passes and failures

| Gate | Result | Meaning |
| --- | --- | --- |
| Original Fincept Qt 6.8.3 build (isolated) | **PASS** | Native test-only code compiled, no production deployment |
| Native original Qt baseline without public opt-in | **PASS — 4/4 wrapper, 60/60 MCP** | Synthetic histories and native GUI/HTTP safety unaffected; outbound denied |
| Strict proxy and QA security Python tests | **PASS — 6/6** | IG/non-Yahoo destinations denied at proxy request parser |
| Original Python `yfinance_data.py` daemon with fake Ticker and real framing | **PASS — 2/2** | Protocol/dispatch works with synthetic offline bars |
| Isolated direct Python `yf.Ticker('SPY').history(period='5d', interval='1d')`, outbound only via Yahoo proxy | **PASS — 5 bars** | Public yfinance 0.2.61 source can return plausible historical bars in the protected environment |
| **Original Qt PythonRunner → provider → MCP → external KAIROS (real Yahoo)** | **FAIL / NOT READY** | Original runner received an **empty JSON array**; KAIROS correctly returned `FINCEPT_UNAVAILABLE`, with no invented bars or broker actions |

At the blocked gate, the proxy recorded **23 approved Yahoo CONNECT requests** and **1 intentionally denied IG-host CONNECT probe**, reaching its fixed connection budget. This is an **observed symptom**, not proof of the underlying cause. The same test-only setup also failed with the alternative one-shot subprocess path, so no daemon-only fix may be claimed. The normal production daemon route was preserved after that diagnostic. No further Yahoo requests were issued after the bounded failure; connection limits were not increased.

The direct Python provider check and the original Qt/MCP/KAIROS test are **separate** and must never be presented as one successful chain. Even a future green end-to-end test would not by itself attest exchange timestamps, Yahoo correctness, corporate actions, provider rights, independent corroboration, strategy alpha or IG trade suitability.

## Reproduction and controls

- All networking is **explicit opt-in**. The KAIROS harness defaults to **SKIP**, not a synthetic success; the Fincept original native selftest defaults to its established offline synthetic assertions with **no public provider request**.
- The public test must pin both executable and source SHA-256 and supply an independent temporary Python environment for the preexisting yfinance 0.2.61 dependency and scratch-only `websockets 15.0.1`. Nothing is installed into the user's personal Python or Fincept. This native code is a *test branch* only. No real broker account, Qwen/paid model token, account setup, permanent proxy, merge or deployment.
- The temporary native/public QA runner must be executed under a verified external-network-denying sandbox; proxy process does not inherit secrets. After each run the proxy is terminated. This security boundary is separate from an actual operational authenticated Fincept↔KAIROS cross-host design.

## Next specific roadmap item

Diagnose why the **original Qt-managed yfinance history** is empty while the equivalent sandboxed direct Python read works: independently inspect sanitized daemon HTTP status/cookie/crumb/retry behavior **without more Yahoo calls until a new bounded approved run**, confirm original runtime Python path/site and proxy scheme/connection reuse, and verify strict traffic/timeout budgets. A complete live-source test must be rerun on an exact SHA with independent data corroboration before any promotion. Until then **Fincept history availability is unverified and KAIROS must fail closed**.
