# Original Fincept F2 — Minimal headless read-only NEWS MCP service candidate (2026-11-23)

**Status: SOURCE CANDIDATE, not an installed or authorized F2 deployment.** Code lives in the ORIGINAL Fincept Terminal Qt/C++ tree, not a parallel KAIROS API, broker, feed fetcher or MCP implementation.

## The actual blocker solved

Fincept's existing \`--selftest-mcp-server\` exits after finite QA, whereas normal GUI startup initializes the TerminalShell, login/authorisation paths, many read/write MCP tools, enabled external MCP server children, Python setup and GUI-only background services. Neither was an acceptable long-running unattended, broker-adjacent F2 service.

New explicit \`FinceptTerminal --serve-readonly-news\` enters \`app/ReadonlyNewsMcpService.cpp\` **before** the original GUI/bootstrap/InstanceLock paths. It constructs only \`QCoreApplication\`, an isolated original AppPaths profile, original SQLite cache, \`NewsService\` cache-only mode, and the **one exact original registered tool** \`get_news\` through the **same original McpHttpServer**. No \`McpService::initialize\`, external MCP server startup, terminal GUI, MarketDataService, broker login, IG session or order path. \`get_quote\` and \`get_history\` are deliberately NOT registered: external market-data ingress and provenance are separate gates.

The original \`get_news\` handler executes only against a currently-valid SQLite \`news:articles\` cache record. Every \`force=true\` request and empty/expired cache is rejected with \`FINCEPT_UNAVAILABLE\`. An additional one-way \`NewsService::enforce_cache_only_mode()\` gate inside \`fetch_all_news()\` refuses *network access even if a cached item expires between checks*. Publisher RSS timestamps, when provided, are still uncorroborated source claims, not verified exchange market as-of.

## Fail-closed launch requirements

All of the following are mandatory or the process exits before opening the listener:

1. Only the exact \`--serve-readonly-news\` argv, no extra flags, no root or changed effective UID.
2. \`FINCEPT_READONLY_NEWS_SERVICE_ACK=FINCEPT_RESEARCH_ONLY_NO_BROKER_V1\` exact acknowledgement.
3. \`HOME\` is an **absolute, canonical, non-symlink, UID-owned, mode 0700** isolated directory, identical to \`FINCEPT_READONLY_NEWS_SERVICE_HOME\`. No existing GUI profile is reused. The Qt profile inside it is \`f2_readonly_news\`.
4. \`HOME/.fincept-readonly-service-v1\` is a UID-owned regular file, link count 1, mode 0600, containing exactly the F2 acknowledgement.
5. \`HOME/mcp.token\` is a UID-owned regular file (no symlink), link count 1, mode 0600, with a randomly generated 64–128 ASCII base64url-character token. Neither token nor token path or contents are logged.
6. \`FINCEPT_READONLY_NEWS_MCP_PORT\` is an explicitly selected integer in 1024–65535. Existing original Qt MCP listener binds **only 127.0.0.1**, on the exact port without fallback. In-memory service override cannot enable actions, change toolset, or be replaced with finite QA overrides.

The process runs indefinitely within \`QCoreApplication::exec()\` while the operator/approved process manager owns its lifecycle. SIGTERM/SIGINT set only a signal-safe flag; Qt's 100ms timer initiates normal shutdown, closes the original MCP listener and SQLite, clears the registered tool and emits fixed, non-secret \`READY\` / \`STOPPED\` markers. The token is not written to Fincept SecureStorage or normal user settings.

## Verified original native integration (macOS Qt 6.8.3)

Original complete FinceptTerminal binary compiled from this change and run under a macOS Seatbelt sandbox prohibiting non-local outbound network access; separate Python test drives the real localhost HTTP MCP process with an ephemeral private HOME/token:

- Correct healthy startup and exact single-tool \`tools/list={get_news}\`.
- No bearer → HTTP 401; \`get_quote\` not registered.
- No cache → \`FINCEPT_UNAVAILABLE\`; \`force=true\` → \`FINCEPT_UNAVAILABLE\`.
- Locally seeded **clearly synthetic** cached NEWS article → genuine original \`get_news\` returns its fields with publisher time marked \`publisher_datetime_attested=false\`. This is a fixture, not real news or market information.
- Insecure token-file permissions, missing acknowledgement and extra command arguments refuse before service startup.
- SIGTERM exit 0, no token in logs, no broker tools.

**8/8 native source and process tests PASS** at the initial complete compilation. Exact final source/head needs independent Linux CI replay.

## Original Linux acceptance gate

The existing \`.github/workflows/build-linux-qa.yml\` is extended (not duplicated) to build its normal Linux Qt AppImage, run the existing headless original suites, then test **the exact newly built packaged AppImage**, not an older artifact, inside a disposable unprivileged Ubuntu 22.04 container with \`--network none\`, \`--read-only\`, \`--cap-drop ALL\`, \`--security-opt no-new-privileges\`, two CPU limit, no broker secrets, and separate temporary HOME/cache. This uses the same 8 source/runtime tests (including actual local HTTP and SIGTERM), with no public-source fetch or provider access. Do not mark Linux PASS until that job completes at exact source SHA.

**Still HOLD**: original Fincept persistent service on ZimaBlade; any approved shared-network-namespace IPC with existing KAIROS (whose research container uses network none); narrow independent market-data ingestion; validated product full UI/quant/backtest functionality; broker access, DEMO admission and LIVE. No deployment or existing KAIROS container changes occurred in this iteration. Installing or activating a service is a separate operator deployment gate requiring exact binary, hardware resource limits, isolated profile, secret provisioning, rollback and local-runner evidence.
