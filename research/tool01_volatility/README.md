# TOOL-01 V1 — Fincept volatility tool executed headless in Debian VM

**2026-11-08 · research-only, fixture-only · no production gateway.**

## Evidence

One small isolated work item after DATA-01 V2 PR #14. This is the **actual installed Fincept** `scripts/technicals/volatility_indicators.py` called via the existing VM `venv-numpy2` (pandas 2.3.3 + ta). It is not a reimplementation of its formulae. No Qt GUI was required; this establishes *single-call headless feasibility*, NOT a persistent service.

The fixture harness `research/tool01_volatility/fincept_volatility_fixture.py` generates exactly 120 deterministic synthetic OHLC bars, imports the existing Fincept module from an explicit file path, calls `calculate_all_volatility_indicators`, checks eight indicator outputs are finite and attaches input/source SHA-256, dataset class, rights, cost and explicit scientific/authority status. There is **no real market feed, broker, credential, provider call, model or independent evaluator**.

### VM run and tests

- Installed Fincept source module SHA256 observed: `76c8a2329c3109d801222ecc987f57005041533e8264c90f1d8b46a4c0109897`; this is an installed-file hash, not a guarantee of release-source parity.
- Fixture input SHA256: `db72401cbb2ee11527be55c95949060ccb5841ecba58ba8d2e8dd3e4309c877b`.
- CLI executed with existing `/home/lab/.local/share/com.fincept.terminal/venv-numpy2/bin/python` and installed module path under `/home/lab/fincept-app/usr/share/fincept-terminal/scripts/technicals/`.
- Eight output fields finite: ATR, BB middle/high/low, Keltner middle, Donchian high/low, Ulcer Index. Example: ATR=2.5, UI≈1.1386454094698457. **These values come from fabricated prices and have zero predictive meaning.**
- VM tests: **3/3 PASS**, including deterministic two-run equality, nonexistent source fail-closed, nonallowlisted module name fail-closed. No GUI interaction, no background service, no network listener, no broker action. GitHub Actions were not run.
- All evidence fields are fixture-declared. In particular `observed_at`/`available_at` are fixture timestamps, NOT independently verified PIT availability. `scientific_status=NOT_EVALUATED`, `broker_authority=false`, and `cost.external_api_calls=0` explicitly label scope. No claim of real data, alpha, scientific admission or safety approval.

### Integration / limitations

This is a **new TOOL-01 research harness**, not a merge or modification of API-01 PR #9, API-SCI-00 PR #12, DATA-01 PR #13 or DATA-01 V2 PR #14. It does not grant LLM tool capability; it does not connect to the API-01 gateway, which currently accepts caller-supplied grants and must be hardened before a real agent is allowed to call it. It does not pass KAIROS Gate9R, nor does it call canonical scientific evaluators. No process persists after the CLI exits.

Potential adapter next: map this fixture-only numeric result to the typed research.compute gateway, with a **server-side** grant and independently mocked gate that can reject proposals. Preserve source identity, result digest, quality and cost; reject any attempt to claim MARKET_OBSERVED or broker authority. The KAIROS canonical evaluator and security gates are separate and still blocked from deployment.

## Blockers and next task

KAIROS P0 issue [#619](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/issues/619) OPEN; CI quarantine [PR #618](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/618) OPEN/DRAFT; fork Actions disabled; legal ambiguity LEG-01 unresolved. No merge or deploy. The source file is imported in an isolated test harness; this is not a whole-OS sandbox. **Next: API-01 grant hardening or TOOL-01 V2 mock gateway**, whichever is unblocked and not concurrently owned. See [master roadmap PR #3](https://github.com/cometarossa/kairos-fincept-terminal/pull/3), [LLM autonomy contract PR #8](https://github.com/cometarossa/kairos-fincept-terminal/pull/8), and [Fincept audit PR #11](https://github.com/cometarossa/kairos-fincept-terminal/pull/11).
