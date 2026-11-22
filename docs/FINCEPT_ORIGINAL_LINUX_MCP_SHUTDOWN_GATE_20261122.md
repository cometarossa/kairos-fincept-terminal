# Original Fincept Linux AppImage — MCP headless shutdown gate

**22 November 2026. DRAFT, research QA; no broker, provider or deployment authority.**

## Reproducible baseline

Fincept original Qt AppImages on isolated Debian 13: #56 native MCP assertions 41/41 PASS but exit 124 after 50s; #58 46/46 PASS, exit 124 after 125s; #61 51/51 assertions (with actual KAIROS Python research client) PASS but exit 124 after 40s; #62 61/61 PASS but exit 124 after 20s. Exact original #62 AppImage SHA-256 b5b3392623ef036b0ef0897451b3f89d4af35d0cf44b2da6d28e1f7e40d16fc2. Native original Linux Qt build in GitHub CI exited 0; packaged suite had only checked --selftest-tools, not MCP.

## Narrow candidate fix / falsifiable gate

The original main.cpp installs shutdown_mcp, Python workers and TerminalShell cleanup exclusively via QApplication::aboutToQuit, emitted when GUI event loop quits. However headless --selftest-mcp-server returns from main() without ever invoking QApplication::exec(), so the service cleanup callback may be skipped. Reuse exactly the existing ordered cleanup lambda for the MCP selftest early-return path, leaving GUI behavior and broker paths unchanged. Only that early-return path is modified; no kill, _Exit, abort or log-marker exemption.

The Linux x64 package CI must execute the **real packaged** AppImage with --selftest-mcp-server and require BOTH native full synthetic assertions (60/60 on this base) AND true process exit 0 within 35s. Printing PASS then hanging must FAIL. A source-only Python wiring test is not sufficient evidence. Independently rerun and hash the exact AppImage on isolated Debian after CI.

**Status:** candidate PR only; unverified until native Linux package CI and Debian independent test pass. If it fails, diagnose the underlying Qt/static worker lifetime instead of weakening or bypassing the test.

**No IG session, orders, live market feeds, credential access or paid API calls.**

## Independent Debian 13 verification and headless timer isolation

The exact #71 Ubuntu-green artifact `3bb71b622387eb1107362541d42485242a6c274edb7ccde08e5049f2f1446751` was independently copied to Debian 13 and retested with an isolated HOME/XDG/TMPDIR. Original MCP assertions **60 passed, 0 failed** but the process still returned **timeout exit 124** after 35 seconds. `fincept.log` confirmed the shared shutdown lambda executed; the original terminal GUI and IG broker were not touched.

**Confirmed startup defect:** the disposable headless MCP profile logged `Pre-warmed 55 dashboard topics during login screen`. The original `main.cpp` queued zero-delay GUI market pre-warm and a three-stage deferred service chain *before* dispatching headless selftests. `McpServerSelfTest.cpp` pumps nested Qt event loops, which therefore execute those queued tasks. The deferred chain includes cloud refresh and broker session monitoring; this behavior is unnecessary and unsafe for no-provider/no-broker headless QA. Whether it fully explains the shutdown hang is **not yet proven**.

This candidate update computes the already-existing `headless_run` rule earlier and gates **dashboard market pre-warm, deferred cloud/broker/producer chain, news pruning and retention sweeper** without altering normal GUI scheduling or test assertions. Independent checks: six source-level regression tests PASS (including repair of a syntax error in the preceding CI source test); native macOS Qt `main.cpp` compiles with pinned original Qt compilation flags (syntax-only). **Exact-head Linux CI and independent Debian AppImage exit 0 remain mandatory before merge**. No paid APIs, broker logins, orders or credentials were used.

## 22 November 2026 — verified Debian 13.7 extracted-package MCP, Arena and all headless suites

Source-only original Qt code for #71 at exact commit `efd5214f14caf71d1e500c69187f7729b7ebb3b1` has GitHub Linux/AppImage CI `44972102409` and architecture ratchets `44972102347` SUCCESS. GitHub CI's packaged MCP gate checks actual code-zero exit and native `60 passed, 0 failed`.

The same artifact was downloaded using GitHub Actions artifact `14734182974`, hash checked independently on iMac and Debian 13.7: SHA-256 `5bea5735c9782b8175fd733ca1f0a55e6f00426d1fa09dc3612741cbb28007fe`. The isolated Debian guest has no `fusermount` binary: **direct AppImage mount returned exit 127** with `No suitable fusermount binary`, so that specific wrapper scenario is **not certified there**. Extraction using the AppImage's own `--appimage-extract` succeeded, and tests ran the original extracted `squashfs-root/AppRun` with clean, disposable HOME/XDG/TMPDIR and disabled guest network egress; the existing GUI process remained untouched.

Independent original extracted-package results: **12/12 selftest suites actual exit 0**, including MCP (`60 passed, 0 failed`) and Arena (`0 failure(s)`) that previously hung/returned watchdog 124 on earlier Debian artifacts. Other PASS/exit-0 suites: tools, llm-tools, feeds, dock-layout, live-table, fno-algo, universe-scan, paper, portfolio-monitor, portfolio-replication. This is objective runtime improvement, **not** full GUI, real market Yahoo, unattended 24/7 bridge, original FUSE mount portability, financial edge or broker execution certification.

CI gate added in this follow-up: packaged `--selftest-arena` must *both* terminate normally before timeout (35 s; real exit 0) *and* include literal `0 failure(s)`, in addition to existing packaged MCP gate. This commit alters only QA workflow, regression source assertions and documentation; original Qt application binary source is unchanged. New exact-head GitHub checks are required before merge. No IG accounts, credentials, external Yahoo calls, trading orders, new runtime service or paid APIs were used.
