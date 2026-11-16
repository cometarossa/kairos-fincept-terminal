# Fincept → KAIROS: conservative quote-delivery evidence (F1)

**2026-11-16. DRAFT, stacked on Fincept #55. No IG login, no market access, no broker execution.**

## Why this is necessary

Fincept's original `MarketDataService::fetch_quotes()` can return a quote from the SQLite cache, a newly completed `batch_quotes` provider request, or an unexpired cached quote when the batch request failed. Before this change, `get_quote` exposed the numeric values without a delivery-path distinction. This is unsafe as input to KAIROS's research or future decision gates.

The original `CacheManager::get()` query requires `expires_at > datetime('now')`; the existing comment claiming the fallback ignores TTL was incorrect. The quote-cache TTL is **30 seconds**, but a still-unexpired cache record is **not an independently verified market-as-of timestamp**. SQLite wall-clock expiry is **not monotonic**, and independent host clock sync/rollback protections remain unverified.

## What changed (original application source)

- A dependency-free `QuoteDeliveryOrigin` enum has only four serialized values: `provider_response`, `unexpired_cache_hit`, `provider_failure_cache_hit`, `unknown`. Default is `unknown`.
- `QuoteData` appends `delivery_origin` and `local_received_at_utc` with defaults, preserving existing eight-field aggregate initializers and source behavior in other widgets.
- A shared cache encoder writes `_fincept_local_received_at_utc` on both `batch_all` (DataHub producer) and `batch_quotes` (one-shot market service) successful provider responses. The timestamp records **local processing time** only. It does **not** come from the exchange; it is not proof of price timeliness or clock synchronization.
- Cache hits identify themselves as `unexpired_cache_hit`; provider failure followed by an available **unexpired** cache record is labeled `provider_failure_cache_hit`. Legacy cache records lack a receipt time and report JSON `null` for it. The cache expiry logic remains unchanged.
- MCP `get_quote` appends `quote_provenance` with `delivery_origin`, `local_received_at_utc` (or null), `market_as_of_utc=null`, `market_as_of_verified=false`, `market_age_seconds=null`, `freshness_verified=false`, `receipt_clock_verified=false`, `execution_eligible=false`, and `scientific_claim=false`. The eight existing quote fields remain unchanged. No model can turn a `provider_response` into exchange freshness or execution authorization.
- Neither `get_history` nor the DataHub JSON wire format is certified by this particular metadata change. They require separate as-of evidence and tests.

## Verification performed locally

The expanded Python suite verifies the native C++17 enum with a real compiler, the enum's permanent lack of market-as-of or execution eligibility, source wiring of cache receipt paths, MCP provenance fields, 30s-expiry-aware SQLite getter, legacy null behavior, and separation of helper TTL from the `MarketDataService` private constant. The parent Fincept #55's three native callback-lifetime tests are run again. A full Qt6.8.x application build or changed UI behavior is **NOT VERIFIED**; `build-cpp.yml` is manual-only.

Commands (on checked-out PR head):

```bash
python3 -m unittest discover -s tests/fincept_original -p 'test_mcp_quote_delivery_provenance.py' -v
python3 -m unittest discover -s tests/fincept_original -p 'test_mcp_market_async_lifetime.py' -v
```

## Integration and authority boundaries

Fincept [#55](https://github.com/cometarossa/kairos-fincept-terminal/pull/55) is still unmerged. This PR **must** be reviewed/merged only after #55 is handled or independently rebased and reverified; it is not based on the present default `main`. KAIROS [#653](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/653), [#654](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/654), Fincept sidecar [#25](https://github.com/cometarossa/kairos-fincept-terminal/pull/25), KAIROS capability registry [#649](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/649) and invoker [#645](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/645) remain separate draft development stacks.

**Still blocked:** independently verified provider exchange timestamp, as-of correctness, clock trust, data quality/stale age, authenticated KAIROS read-only tool interface, full original Qt build, and integration of the eventual order lane with only the frozen Gate9R DEMO authority. Trading on `get_quote` data is NOT approved. This work does not touch IG/credentials, start a broker session, modify scheduling/runner state or create any order.


## Qwen4-Max interactive design review (English; not source sign-off)

The model highlighted the risk of accidentally re-stamping a cache hit, distinguishing local receipt UTC from exchange-time, handling legacy missing fields and the stacked #55 dependency. Added **offline source tests** assert cache reads never use `currentDateTime`, legacy receipts stay absent (and produce MCP null), and the only two receipt-time stamps are on successful provider-response parsing. It also noted SQLite's existing wall-clock TTL is not monotonic and should be tested for clock rollback in a separate reviewed change. These are **design limitations**, not grounds to claim market freshness.

## 2026-11-16 — SQLite TTL replay and explicit non-freshness (follow-up)

A real Qt6.8.x build remains **BLOCKED for environment/tooling reasons**, not passed: the offline Debian 13 VM has the previously deployed Fincept AppDir but no C++ compiler, CMake or Qt6 development headers; the connected macOS and ZimaBlade hosts do not have a Qt6 development SDK either. The public Fincept GitHub fork has `actions/permissions.enabled=false` and **zero enabled workflows**; changing that setting is out of scope and was not attempted. Avoid passing isolated native-header QA as a full Qt application compile.

Five deterministic in-memory SQLite tests now extract the **literal original** `CacheManager.cpp` SELECT statement and execute it with a substituted fixed UTC clock, verifying: unexpired hit, expired miss, strict exact-expiry boundary, unchanged stored receipt value, and parameterized key isolation. They also freeze the 30-second quote TTL and explicitly document that the original SQLite `datetime('now')` uses wall time, **not a monotonic clock**. This verifies SQLite query semantics only, not the Qt C++ CacheManager runtime.

Three explicit MCP response fields are added to prevent a KAIROS LLM consumer from conflating local receipt or cache TTL with trustworthy market freshness: `market_age_seconds=null`, `freshness_verified=false`, `receipt_clock_verified=false`. No clock trust or external exchange timestamp was fabricated. The two corresponding source-contract assertions were demonstrated **RED** before the implementation, then must be verified GREEN with the full offline suite.

This incremental evidence does not create an IG session, use live market data, authorize execution or establish any scientific edge. Full Qt6 compilation and provider-as-of contracts remain blockers.

## 2026-11-16 — Original Qt6 changed translation-unit compilation (F0/F1 checkpoint)

**VERIFIED:** a disposable `debian:trixie` Docker container on the authorized ZimaBlade host was provisioned with Debian Qt **6.8.2**, GNU g++ **14**, pkg-config and Qt6 Core/Network/Widgets/Sql/Concurrent development headers. This is the same **6.8 minor line**, but **NOT exact project patch 6.8.3**. The public Git source was sparsely cloned at exact pre-amendment PR SHA `2a0533021ff42b981c5594b594f818f5100390e2` and copied to the container. The container was disconnected from its Docker bridge network **before** compilation and capped at 2 vCPU/4 GiB; it had no host/KAIROS/IG credentials or privileged mounts.

**Both original changed Qt C++20 translation units compiled to real object files (not just syntax-only):**

- `fincept-qt/src/services/markets/MarketDataService.cpp` → `MarketDataService.o` (~1.6 MiB), **GCC14 exit 0**.
- `fincept-qt/src/mcp/tools/MarketsTools.cpp` → `MarketsTools.o` (~672 KiB), **GCC14 exit 0**.

Compiler flags include `-std=c++20 -O0 -fPIC`, original `fincept-qt/src` and `fincept-qt/include` include roots, and cflags obtained through `pkg-config Qt6Core Qt6Network Qt6Widgets Qt6Sql Qt6Concurrent`. The original versioned code compiled with the Qt dev SDK. This confirms the modified quote-service and MCP implementation translation units are **Qt/C++ compileable** on that SDK, an advance over earlier standalone native-only tests.

**New reproducible opt-in smoke test:** `tests/fincept_original/test_qt6_market_original_compile.py` compiles each original translation unit to an object in a temporary directory. Run with `FINCEPT_QT_COMPILE_REQUIRED=1 python3 -m unittest discover -s tests/fincept_original -p 'test_qt6_market_original_compile.py' -v` in an isolated Qt6.8 development environment. With required mode on, an absent/incompatible SDK **fails** instead of presenting a false green; without required mode it is explicitly **SKIPPED**. On the iMac without Qt6 headers, both behaviors were directly checked.

**NOT VERIFIED / STILL BLOCKED:** complete Fincept `FinceptTerminal` CMake configure/link/build, Qt6 moc/linker and plugin packaging, runtime GUI screens with this changed binary, signal delivery/event-loop integration, provider exchange as-of, authoritative time/freshness, IG accounts, KAIROS authenticated tool integration, order/trading execution, and exact Qt 6.8.3. The QEMU Debian GUI smoke used a **different previously installed binary** and cannot be counted as a test of these source changes. Fork GitHub Actions remain disabled; no setting or runner was changed. Keep PR in DRAFT.

## 2026-11-16 — Full original Fincept 4.5.1 CMake graph: CONFIGURE PASS

**New evidence, separate from the two-file Qt object compilation:** an isolated `debian:trixie` Docker QA container was created on the authorized ZimaBlade with 2 CPU / 5 GiB memory / 256 PIDs and no KAIROS, IG, home, or credential mounts. The **full** `fincept-qt/` project source (about 60 MiB; >1,000 C++ sources) was copied from the public fork at exact draft #56 SHA `4696ecf570018f838f75cb70e74c1d4865f508cf`. Only Qt/CMake developer dependencies and public versioned third-party source trees were fetched during preparation. No Fincept runtime, provider, broker or IG API was invoked.

**VERIFIED:** CMake 3.31, GCC/G++14, Debian-packaged Qt **6.8.2** (MINOR mode; project exact release pin is 6.8.3), required Qt6 Widgets/Charts/PrintSupport/Network/Sql/Concurrent/Multimedia/LinguistTools, OpenSSL, Zlib and original dependencies QXlsx, md4c, QGeoView, Qt Advanced Docking System, ed25519. CMake returned **exit 0** with both `Configuring done` and `Generating done` and wrote the Ninja graph for the full `FinceptTerminal` executable. This is a **full-project configure PASS**, not yet an application BUILD/LINK/GUI PASS.

**Environment-only resolutions, not source changes:**
- Minimal Debian missed `ca-certificates`: first FetchContent TLS download failed safely. Installed CA certificates; TLS verification stayed on.
- Qt private GUI targets required XKB development packages and the `qt6-base-private-dev` versioned headers. Installed genuine Debian packages, rather than fabricating include paths.
- Existing original CMake specifies QGeoView pinned SHA `4b2c52c80940e1073c259ded1a57df83036ba1c9` alongside `GIT_SHALLOW TRUE`. The first shallow clone could not check out that historical SHA. A **separate exact-SHA fetch** of this public commit succeeded and the validated source directory was passed as `-DFETCHCONTENT_SOURCE_DIR_QGEOVIEW=...`; original CMake source was not edited. This is a distinct reproducibility defect to review independently before release builds.

**Lab configuration:**
```sh
cmake -S /workspace/fincept-qt -B /workspace/fincept-build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DFINCEPT_QT_PIN_MODE=MINOR \
  -DFINCEPT_DOWNLOAD_YTDLP=OFF -DFINCEPT_BUILD_TESTS=OFF \
  -DFINCEPT_BUILD_INSTALLER=OFF -DFINCEPT_ENABLE_LTO=OFF \
  -DFETCHCONTENT_SOURCE_DIR_QGEOVIEW=/workspace/fincept-build/_deps/qgeoview-src
```

Network was disconnected **before** invoking `cmake --build --target FinceptTerminal`. CMake generated 783 Ninja operations; 686 compiler nodes include Fincept and its component dependencies. A bounded full build was started under 2 CPU / 5 GiB; final compile/link disposition is recorded separately below when verified.

**Scope limitations:** Full project configuration with Qt 6.8.2 does not establish exact 6.8.3 compatibility, success of linking, platform deployment, Qt event-loop correctness or market-data provenance adequacy. `yt-dlp` auto-provisioning was disabled for offline QA and CMake warned that it was absent; this does not mean the release packaging is complete. No IG login, market fetch, order or trading authority.

## Full original FinceptTerminal build disposition — bounded QA

The full Ninja build was **started after network disconnection** with
`cmake --build /workspace/fincept-build --target FinceptTerminal --parallel 2`,
protected by `timeout 420s` and a 5 GiB container memory limit.

**VERIFIED outcome:** `timeout` exit **124**, the Ninja log reached **[94/783]**
operations, then recorded `ninja: build stopped: interrupted by user` when
the watchdog terminated the process. That diagnostic is the Ninja wording for
the watchdog signal, **not** evidence the operator manually interrupted it.

Successful intermediate artifacts included the original versioned QXlsx
static library (`libQXlsxQt6.a`), md4c HTML static library, QGeoView shared
library (`libqgeoview.so`) and Qt Advanced Docking System static library
(`libqtadvanceddocking-qt6_static.a`). Qt MOC/UIC generation, multiple
translation files and the 1183-file Python-script sync also ran. No C++
`error:` or `FAILED:` marker was found in the bounded build log before
termination, **but most original Fincept application source files were not yet
compiled**. No `FinceptTerminal` executable exists from this trial.

**Therefore: full Qt CMake CONFIGURE/GENERATE = PASS; external dependency
builds = partial PASS; complete original FinceptTerminal COMPILE/LINK/RUNTIME
= NOT VERIFIED**. No profitability, market freshness, authenticated read-only
MCP transport or broker trade functionality was tested.

A separate standalone [QGeoView pin checkout fix, Fincept DRAFT #57](https://github.com/cometarossa/kairos-fincept-terminal/pull/57)
addresses the reproducible historical-SHA/shallow-clone issue at
`9d8d2a17529830af3cbbd784f33658f7a6a7ba28`. It has 2/2 offline
synthetic Git regressions PASS but has **not** been merged, and no fresh full
CMake run with that new pin fix alone has been certified yet. Fincept DRAFT
#55/#56 remain a distinct stack.

**Next QA gate:** use a bounded, higher-throughput isolated C++ builder to
finish the 783-operation original application build and link, then headless
Qt startup/selftests on that **changed binary**, without broker credentials
or any external market connection. Exact Qt 6.8.3 remains required for
release certification.
