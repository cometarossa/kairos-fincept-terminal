# Fincept original public RSS to KAIROS real MCP QA — 23 November 2026

Status: SOURCE CANDIDATE. Real cross-process positive result not yet attested.

Existing Fincept #77/#78 already passed original packaged Linux RSS parsing of real CNBC feed (30/30 source dates, 17 recent). Existing KAIROS #684 already merged its read-only, authenticated localhost Fincept client. The missing product milestone is actual delivery through original get_news MCP into that same KAIROS client, without fabricating a feed or constructing a second adapter.

The optional ORIGINAL --selftest-mcp-server test arm runs only when all FOUR explicit variables are valid:
- FINCEPT_PUBLIC_MCP_NEWS_QA=SAVED_PUBLIC_RSS_LOCAL_READ_V1
- FINCEPT_PUBLIC_MCP_NEWS_RSS_FILE=absolute local public RSS XML file (1–200000 bytes)
- FINCEPT_PUBLIC_MCP_NEWS_CLIENT_SCRIPT=absolute path to canonical KAIROS QA caller
- FINCEPT_PUBLIC_MCP_NEWS_PYTHON=absolute executable Python interpreter

External capture of one real public RSS via bounded HTTPS is performed BEFORE Fincept starts. Fincept does NOT request provider network data. The original NewsService parses the saved XML; original CacheManager is populated only if originally empty, TTL 90 seconds; the original get_news tool is invoked over actual authenticated localhost MCP with force=false and include_publisher_datetime=true. KAIROS is a separate Python child using its original research facade and exactly the ephemeral server bearer token. Expected positive outcome: FINCEPT_RESEARCH_ONLY, source claimed time, never attested market as-of, broker_calls=0.

A second clearly synthetic 2025 RSS test uses the same source/parser/cache and original MCP route. The existing KAIROS facade MUST return FINCEPT_UNAVAILABLE (stale refusal), not invent an arrival timestamp. QA cache is removed at the end. No broker, account, trading session, external-facing MCP port, service deployment or new capability is introduced.

Pending: actual full native Qt binary integration success, independent Linux packaged AppImage plus genuine external KAIROS script, and review/CI. The previously tool-blocked Debian/QEMU executable transfer is NOT an allowed workaround. None of these QA receipts certify news truth, exchange-time as-of or trading authority.
