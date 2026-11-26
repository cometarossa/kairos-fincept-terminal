# Original Fincept F2 Screener inbox candidate (2026-11-26)

**Candidate only, not deployed or admitted.** Depends on draft #97 at
`efdc558bc78f7cd2c8b9e7683beeafd9df541df5`; no change to the original
provider transport, no Python dispatch tool, broker access or autonomous
provider capture. The default F2 tool catalogue is unchanged.

With the explicit `FINCEPT_READONLY_SCREENER_INGRESS_ACK=FINCEPT_SCREENER_INBOX_V1`
opt-in and private service-home inbox, register one synchronous read-only
`get_screener` handler through the original Qt MCP registry. It accepts only
`screen_id=day_gainers, limit=20`. No refresh, user-controlled file, URL,
paging or generic execution. Read a fixed private file using openat,
no symlink, same nonroot owner, single link, 0600 mode, bounded size.
Validate an ASCII Base64/SHA256 envelope and exact schema, no duplicate
keys, positive USD prices, unique symbols, positive integral quote clocks,
nonnegative delays, a 600-second local TTL and all research-only flags.
No inference of actual market freshness or provider truth from local TTL
or digest; market_as_of_verified=false, scientific_claim=false,
execution_authority=false, broker_calls=0. Hash is corruption detection,
not publisher authentication. No stale fallback. File writer admission and
atomic publication belong to a separate operator-gated capture lane.

Pure Python projection preserves order and only selects quote fields from
the original Screener result; refuses any original warning, empty or
inconsistent results, wrong page/screen/currency, invalid clocks/identity.
This deliberately narrow prototype is not a full screener, and may deny
real cross-ticker screens with heterogeneous clocks. No actual provider
compatibility or market freshness established.

## Reproduced evidence (macOS, existing Qt 6.8.3)

- Native inbox executable 23/23 checks passed; same source compiled under
  repository-shaped CMake and CTest 1/1 (PID82853).
- Source integration syntax check of ReadonlyNewsMcpService.cpp and
  EssentialTools.cpp passed (PID82059) using exact current NewsService,
  MarketDataService, McpTypes and quote inbox headers over existing
  November 23 build headers. This was not a full exact-source app link.
  Initial mixed-header/duplicate include failure was corrected; full
  source build remains pending.
- Original #97 Python backend with synthetic provider transport ->
  projection -> sealed file -> native Qt reader -> existing KAIROS
  candidate response validator (PID82313) passed two rows without change;
  unsafe permissions and expiry denied 2/2. This was not a real MCP
  process test or real market acquisition.
- New actual original F2 authenticated cross-process regression is
  included in the existing Linux network-none AppImage test suite.
  Test source parsed successfully, execution NOT VERIFIED until native
  package exists. Native reader CTest also added to the existing build
  job, no new job. Existing #97 CI still pending at checkpoint.
- Candidate KAIROS client remains local and not registered in production.

Next: exact-head Linux compile/package plus actual MCP tool test, then
review capture policy against existing Yahoo shared budget, actual
market evidence with explicit authorization and end-to-end KAIROS
client. No runtime change or IG. Keep #632 separate.
