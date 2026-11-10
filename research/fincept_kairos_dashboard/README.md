# KAIROS Research dashboard — source-only / offline proof boundary

**Status (2026-11-10):** proposed Qt code, **not built or deployed**.
Fincept `main` is unchanged until PR review and merge. This is NOT a broker,
KAIROS scientific gate, data feed, or authenticated API. Existing Fincept screens
and features remain intact.

## What appears in Fincept

The existing **Dashboard > Reset layout / Choose template** selector gains a
seventh preset, **KAIROS Research**. It composes the existing News, Risk Metrics,
Screener widgets and one new **KAIROS Research Status** tile. It does not alter
the user's current dashboard layout automatically. The new tile is also
available through **Add Widget** in the Research category.

The tile always displays: **RESEARCH ONLY · SCIENCE NOT EVALUATED · NO BROKER
AUTHORITY**. With no valid local file it shows NO LOCAL REPORT and every stage
NOT VERIFIED. A valid, current, synthetic-only local report may change the first
stage to **SYNTHETIC TEST**; the gateway, scientific and portfolio stages stay
blocked/not verified. It never displays scientific acceptance or a trading signal.

## Local report file contract

The Qt tile reads only this exact local location, without network or API calls:

```text
QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)
  / kairos / research_status_v1.json
```

This is app-name and operating-system dependent. To find the precise path on
your installation, open the tile and hover its **RESEARCH ONLY** footer
(tooltip shows full expected path). Create its parent directory on your own
machine, then pass that path to the exporter. No automatic file discovery,
external address, broker credential, login or daemon is required.

A report has `schema=fincept_kairos_research_status_v1`,
`mode=SYNTHETIC_FIXTURE`, `scientific_status=NOT_EVALUATED`,
`broker_authority=false`, `external_api_calls=0`, one UTC timestamp
no older than 24 hours, a SHA-256 source identifier, and four fixed stage
fields. The widget rejects malformed, oversize, stale and authority-inflating
reports and labels even a valid report **LOCAL / UNATTESTED**. The payload
is untrusted display material, not a security or risk authorization.

## Data producer — reuse of existing TOOL-01 work, not a substitute

An actual *headless Fincept volatility function* was exercised offline with
120 synthetic OHLC bars in the **still-open** fork PR
[#15](https://github.com/cometarossa/kairos-fincept-terminal/pull/15).
That code is **not merged**, and its result is not live market data.
The new exporter consumes exactly its V1 JSON evidence envelope (not a
random market feed or a broker response). Once obtained independently from
the existing PR #15 harness in a licensed local Fincept environment:

```sh
python3 -m unittest discover -s research/fincept_kairos_dashboard -p 'test_*.py' -v
# If you already have a valid TOOL-01 synthetic fixture envelope:
mkdir -p "PARENT_DIRECTORY_FROM_WIDGET_TOOLTIP"
python3 research/fincept_kairos_dashboard/status_report.py \
  --evidence /path/to/tool01_synthetic_evidence.json \
  --out "FULL_PATH_FROM_WIDGET_TOOLTIP"
```

The exporter only writes a 0600 local, atomic JSON checkpoint. It checks
indicator keys/finite values, original fixture flags/timestamps, source
identities, zero API calls and no broker authority. It does **not**
independently recompute SHA-256 from trusted Fincept source bytes or the
original 120 input rows; therefore a malicious/forged local envelope can
still be constructed. **Never treat this UI as proof of an integrated,
authenticated gateway or scientific certification.**

The remaining real integration path is:
`TOOL-01 (PR #15) → API-01 server-side capability policy (PR #16/17) →
API-SCI-00/DATA-01 temporal provenance (PR #12-14) → canonical KAIROS
scientific evaluator → theoretical portfolio only`.

## Checkpoint / test limitations

- Python exporter unit tests are stdlib-only, offline, no Qt dependency.
- Native Qt compile, launch and visual test: **NOT VERIFIED** until the
  appropriate isolated Fincept build environment is available.
- Fincept fork GitHub Actions is disabled; no hosted CI result claimed.
- Prior PRs #3, #8, #9, #12–17, #23 remain independent drafts, unmerged.
- Never enable the historical privileged KAIROS runner to validate this PR.
- No host deployment, trader order, provider spend, secret or auto-merge.

## Follow-up

1. Independent Qt C++ build and UI smoke of the new preset/tile (permission
   needed only if software must be installed or host mutated).
2. Reconcile/merge or rebase overlapping draft PRs in dependency order with
   exact-blob tests; avoid replacing existing Fincept tools.
3. Build a real **authenticated read-only** source-of-truth/status adapter
   between a KAIROS service and Fincept, with staleness/provenance gates.
4. Show real scientific verdicts only when the KAIROS canonical evaluator
   provides verifiable, scoped evidence and Gate9R authority is still isolated.

## 2026-11-10 Mac offline verification (actual source, no broker)

Verified on authorized iMac, in a separate temporary test directory:

- Source: **actual** `fincept-qt/scripts/technicals/volatility_indicators.py` from fork `main` at blob `d991f5448be1e16675f511993896b3f8edea1059`, SHA-256 `76c8a2329c3109d801222ecc987f57005041533e8264c90f1d8b46a4c0109897`.
- Reused existing **unmerged** PR #15 fixture harness code, exact blob `3eab179dc6b6617c62fc15d77e61ce647a9b3e7d`, with 120 synthetic OHLC bars. Real Fincept calculation returned **8 finite indicator fields**, no Qt, no market-feed request.
- The new `status_report.py` consumed that result and atomically emitted `fincept_kairos_research_status_v1` with `fincept_tool=MOCK_PASS`, `tool_gateway=BLOCKED`, `kairos_science=NOT_VERIFIED`, `theoretical_portfolio=BLOCKED`. No API calls, no credentials, no trades.
- New exporter and static Qt registration tests: **10/10 unittest PASS**, `compileall` PASS. The standalone exporter and fixture calculation both executed successfully on Mac.
- These tests were against locally copied exact GitHub sources. **A native Qt C++ compile, screen launch, screenshot and deployed app integration remain NOT VERIFIED.** The report was written into the isolated temporary test directory, **not** the user's live Fincept AppDataLocation.
