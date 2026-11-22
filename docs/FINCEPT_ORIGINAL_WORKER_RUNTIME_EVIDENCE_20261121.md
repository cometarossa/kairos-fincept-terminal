# Fincept original Yahoo worker: exact runtime provenance in opt-in native QA

**2026-11-21 — RESEARCH/QA ONLY.** Source branch stacked on [Fincept DRAFT #65](https://github.com/cometarossa/kairos-fincept-terminal/pull/65), head 5f019559be6a10c0d496f44b59702fae3c06d024, with original KAIROS opt-in handoff in DRAFT #668. Does not certify real market availability.

## Why

An earlier direct Python public Yahoo SPY/5d/1d read returned five bars, but the *original Qt PythonRunner → PythonWorker → Yahoo → authenticated MCP → KAIROS* path produced no usable history and KAIROS returned FINCEPT_UNAVAILABLE. Separate DRAFT #65 already classifies that *symptom* without exposing raw provider errors, yet did not capture the exact Python environment loaded by the original Qt-managed daemon.

PythonWorker::launch_process() prefers the installed venv-numpy2, but can fall back to PythonRunner::python_path(). The repo's declared NumPy2 requirements pin yfinance==0.2.66 and curl_cffi==0.13.0; a prior separate direct read used yfinance 0.2.61. Those are **declared/test-lane** versions, NOT proof of what the failing Qt daemon loaded.

## Change (normal GUI/runtime remains unchanged)

Only for the exact opt-in FINCEPT_PUBLIC_MCP_HISTORY_QA=SPY_5D_PUBLIC_READ with FINCEPT_PUBLIC_QA_SANDBOX_VERIFIED=EPERM_EXTERNAL, the original yfinance_data.py --daemon readiness frame adds qa_runtime containing **only numeric dotted version fields**:

- python: actual interpreter major/minor from sys.version_info.
- yfinance_loaded: yf.__version__ of the module the daemon really imported.
- pandas_loaded: pd.__version__ of the loaded pandas module.
- curl_cffi_distribution: the installed distribution version via local importlib.metadata, **not proof of a loaded curl_cffi module**.

Absent/malformed/untrusted versions become UNKNOWN. No paths, proxy configuration, environment dumps, cookies, token values, provider responses, HTTP codes or prices are emitted. No new request/daemon action/MCP tool, and no package installation or network access is added.

The *original* Qt PythonWorker also prints a fixed interpreter-selection enum MANAGED_NUMPY2 or RUNNER_FALLBACK and sanitizes the four readiness values again before writing QA_YAHOO_WORKER_VERSION_<fixed key>=<numeric/UNKNOWN> **only inside** --selftest-mcp-server with both exact QA environment sentinels. The normal framed handshake, ready/dispatch semantics, timeout/restart rules and broker authority remain unchanged.

## Verification at exact source worktree (independent test)

- The new regression failed before implementation (**4 failures, 1 pass**); after implementation, the full selected no-network Python regression set **26/26 PASS**, including normal ready-frame preservation, exact opt-in, secret-string redaction and missing-distribution behavior, original framed daemon tests, existing Yahoo classification and bounded localhost proxy/security suites.
- python3 -m py_compile for both Python files: **PASS**.
- git diff --check: **PASS**.
- Original Qt 6.8.3 macOS native project compilation flags reused from fincept-full-qt-build-20261116, compiling **the changed original PythonWorker.cpp source** with clang++ -fsyntax-only: **PASS**. The original project was not fully rebuilt or repackaged for this worktree; full Qt integration/CI is **NOT CHECKED**.
- The test environment had an unrelated user-site tests package shadowing this repository's namespace: a disposable, per-invocation import root was used to execute unchanged offline suites; no permanent PYTHONPATH or global Python installation was modified.

## Next gate

Use the existing explicit single-run, Yahoo-only and Seatbelt-denied original Qt↔MCP↔KAIROS QA harness **only after exact-head native build, source pin, credential isolation and normal approval prerequisites**. Capture sanitized environment/version markers, fixed source failure category and bounded proxy host-family counts, then compare the actual Qt worker versions with the direct-read versions. That evidence can test the environment-mismatch hypothesis but must not be presented as causal proof or successful market data. No additional Yahoo attempts, IG session, broker mutation, trading, auto-merge or deploy are authorized by this source change.

## 22 November 2026 — Integration candidate, original Fincept #71 already merged

This diagnostic stack (original #63 + batch integrity #64 + failure taxonomy #65 + worker metadata #68) is now integrated in a single **existing** QA PR #68 against verified Fincept main after #71, avoiding additional independent runtime bridges or duplicate PRs. This is an integration candidate **only**: there has been no repeated Yahoo/provider network request. Original live Qt→Yahoo→MCP→KAIROS history previously returned empty; no source data/provenance may be certified until a separately authorized bounded replay and independent corroboration.

Offline tests on the integrated original-source tree: 38/38 PASS, including Yahoo-only proxy's deterministic denial of IG/LAN, atomic connection limit, opt-in secret redaction, framed daemon fake history, batch OHLCV integrity, sanitized failure taxonomy, and worker version metadata. Two obsolete `tests.fincept_original` imports were updated to direct local fixture imports because a third-party `tests` package shadows the repository namespace on the macOS QA interpreter. Qt native build, Linux AppImage, MCP/Arena packaged exit and architecture checks on the **integration exact commit** remain required; earlier CI on #71 is evidence for #71, not for the combined changes. No live brokers, provider network, credentials or paid API.
