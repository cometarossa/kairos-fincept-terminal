# Fincept original Yahoo history: explicit adjustment choice (F2, 22 November 2026)

Scope: the **existing** `fincept-qt/scripts/yfinance_data.py` functions
`get_historical_period` (the original Qt `MarketDataService::fetch_history`
and KAIROS read-only MCP historical path) and `get_historical` (calendar range).
This does **not** change providers, create a second client, open IG sessions,
enable orders, or classify real exchange as-of.

## Observed baseline and explicit choice

The exact already-tested Fincept lab managed environment was Python 3.11.9,
`yfinance 0.2.66`, `pandas 2.3.3` and `curl_cffi 0.13.0`.
Read-only inspection of the **installed source** in the previously running
isolated Debian VM found `yfinance.scrapers.history.PriceHistory.history`
defines `auto_adjust=True, back_adjust=False`. Before this change, both
original Fincept `Ticker.history(...)` calls omitted these keywords and
therefore inherited **that exact installed version's defaults**.

The original calls now explicitly pass `auto_adjust=True,
back_adjust=False`, preserving the observed baseline behavior while preventing
a later dependency default change from silently switching between raw and
adjusted historical OHLC. The price fields are the adjusted OHLC returned by
yfinance when its adjustment succeeds; **volume remains the volume returned by
the provider, not a separately adjusted/attested volume series**. This is a
**code-defined source/adjustment convention**, not a new proof of independent
Yahoo data quality, corporate-action correctness or the specific adjustment
factors historically applied.

## Evidence and acceptance

- Added a source-backed offline test of both ORIGINAL Python history functions
  with an in-memory pandas frame and a mocked `yf.Ticker`. The test captures
  actual `Ticker.history` keyword arguments and asserts explicit
  `auto_adjust is True` and `back_adjust is False`; neither provider network
  nor any IG credentials are accessed.
- **RED before implementation**: test failed because no explicit
  `auto_adjust` keyword was passed. Green tests are recorded only after
  running the exact updated source; this change must pass full PR CI before
  any merge.
- The original call route, error handling, whole-series OHLCV integrity
  decoder, original Qt/MCP read-only client and Gate9R authority are untouched.
  KAIROS remains `market_as_of_verified=false`,
  `execution_authority=false`, `scientific_claim=false`, `broker_calls=0`.
- Comparing against independent Tiingo is **not** automatically valid merely
  because both feeds say *adjusted*: the existing KAIROS
  `config/kairos_equity_market_data_v1.json` documents
  `TIINGO_CRSP_STYLE_SPLIT_AND_DIVIDEND_ADJUSTED`, which is not proof of
  adjustment-method equality with yfinance. Align venue, session date,
  currency, adjustment rules, corporate actions, observation vintage, and
  timestamps before comparison, with any mismatch as HOLD.

Next F2 gate: an independently sourced, temporally aligned spot check with
explicit adjustment policy and immutable receipts; no automatic market-as-of
promotion, no protected dataset/credential reads, no trading.
