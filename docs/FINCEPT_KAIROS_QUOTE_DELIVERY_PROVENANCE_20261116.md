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
