# Fincept × KAIROS — Original Function Preservation Baseline V1

**Date:** 2026-11-11 Europe/Rome. **Owner requirement:** retain the **working majority of native Fincept Terminal functions**, not just its look-and-feel. KAIROS must be additive, optional and incapable of breaking Fincept's existing work. This baseline provides a measurable **source-regression guard plus selected real functional probes**, not a full Qt GUI functional certification.

**Canonical pinned fork baseline:** `cometarossa/kairos-fincept-terminal` `main` @ `7716ee8613249fb44c4d14036c5bc16ed6f34e97`. No Fincept application source changed in this PR. Fincept fork GitHub Actions remain disabled; results below are local Mac tests, not CI. Prior VM findings below are quoted as **dated historical evidence**, not freshly repeated VM GUI tests.

## Concrete tests completed today

### Source-protection gate

The new `tools/fincept_audit/functional_preservation_baseline_v1.py` reads three original C++ source files WITHOUT executing Fincept:

- `src/app/WindowFrame_Setup.cpp`: **52 existing dock screen factories** and their original class targets.
- `src/screens/dashboard/canvas/WidgetRegistry.cpp`: **35 existing widget factory definitions**, each hashed separately.
- `src/screens/dashboard/canvas/DashboardTemplates.cpp`: the **six original dashboard presets**, each original definition / geometry hashed; each referenced widget ID must exist.

The baseline JSON `tools/fincept_audit/fincept_source_baseline_v1.json` pins all identifiers and per-definition fingerprints. New opt-in factories/widgets/presets are permitted; deletion, reuse or modification of any existing factory definition or dashboard preset fails, as does unknown widget reference or duplicate factory ID. **9/9 regression unit tests PASS on Mac**, including deliberate removal, class substitution, widget tamper, preset geometry mutation and bad reference negatives.

**Actual DRAFT PR #24 source check today:** same original **52 route factories**, **36 widgets** (original 35 plus new KAIROS tile), **7 presets** (original six plus new KAIROS Research); **PASS_STATIC_INVARIANTS** against original pinned baseline. This does **NOT** prove that the Qt application compiles, that these screens open or that user-saved layouts survive. PR #24 stays DRAFT/HOLD until native Qt build and before/after GUI smoke; do not merge on this static result.

### Functional calculations — five ORIGINAL headless Python modules

Using actual, independently fetched original Fincept Python source (hash-pinned) and local `pandas`/`ta`, **180 deterministic synthetic OHLCV rows** were passed to each original `calculate_all_...` function. No original source was edited, no broker or market network/feed used, no model/provider credits spent.

| Original Fincept module | Computed output columns | End-of-fixture state |
|---|---:|---|
| Volatility | 21 | All 21 last-bar outputs finite |
| Momentum | 18 | All 18 last-bar outputs finite |
| Trend | 30 | 29 finite last-bar values; `psar_down` *conditionally inactive* (NaN latest, **69 finite historical** observations, `psar_up` current and finite). **Normal sparse trend branch, not a failing module.** |
| Volume | 10 | All 10 last-bar outputs finite |
| Others / Returns | 3 | All 3 last-bar outputs finite |
| **Total** | **82** | **5/5 module calculations completed correctly** on synthetic input |

The source of this repeatable probe is `tools/fincept_audit/technical_family_probe_v1.py`. It pins all five SHA-256s, refuses unexpected source changes, checks output field counts, verifies sparse PSAR semantics and blocks common Python socket-connect methods during execution (not a true OS network sandbox). It does not claim security of installed Python packages or scientific predictivity. In total **13/13 local unit+functional tests PASS** (9 static source + 4 new technical family tests), Python `compileall` PASS. **These are five original technical modules, not five entire Fincept application sections.**

## Functional coverage register — honest status

| Product area | What is actually known today | Coverage status | Safe next test |
|---|---|---|---|
| Qt navigation / window docking | 52 original factory IDs + class targets preserved in code | **SOURCE PRESERVED; GUI NOT RETESTED** | Native Qt build & isolated pinned GUI smoke, including PIN/logout |
| Dashboard widget registry | 35 original factory definitions preserved; PR #24 adds 1 without overwriting originals | **SOURCE PRESERVED; GUI NOT RETESTED** | Create, refresh, resize, close/reopen old and new widgets |
| Six original dashboard presets | Exact preset definitions and widget references preserved; PR #24 seventh is additive | **SOURCE PRESERVED; GUI NOT RETESTED** | Render all original presets, preserve saved layout, theme and state |
| Market quotes, DataHub, provider fallbacks | Internal services/reads exist; previous VM logs showed occasional Yahoo symbol errors | **NOT RUNTIME VERIFIED TODAY** | Test per-provider errors/staleness and rights, no production-feed substitution |
| Technical analysis: volatility, momentum, trend, volume, others | Actual original functions ran on synthetic OHLCV; 82 outputs | **5/5 MODULE FUNCTIONAL SMOKE PASS** | Verify selected named indicators against independent numeric reference |
| Algo Builder / Backtest | [2026-11-08 audit](https://github.com/cometarossa/kairos-fincept-terminal/blob/audit/fincept-algo-backtesting-functional-20261108/docs/audits/FINCEPT_FUNCTIONAL_AUDIT_ALGO_BACKTEST_VM_20261108.md): historical VM run 2927 bars, 1439 trades | **HISTORIC VM PASS; ECONOMICALLY UNVALIDATED** | Independent GUI smoke + cost/slippage provenance; never deploy |
| Backtesting / VectorBT | [2026-11-08 addendum](https://github.com/cometarossa/kairos-fincept-terminal/blob/audit/fincept-algo-backtesting-functional-20261108/docs/audits/FINCEPT_BACKTESTING_VM_RUNTIME_V1_1_20261108.md): synthetic 320-bar backtest PASS | **HISTORIC VM SYNTHETIC PASS** | Recheck exact installed runtime and external-data delivery |
| Backtesting / Backtesting.py | [2026-11-08 addendum](https://github.com/cometarossa/kairos-fincept-terminal/blob/audit/fincept-algo-backtesting-functional-20261108/docs/audits/FINCEPT_BACKTESTING_VM_RUNTIME_V1_1_20261108.md): synthetic 260-bar fixture PASS with test-only loader | **HISTORIC VM SYNTHETIC PASS** | No production external-data seam proven; fees + final position check |
| FastTrade, Zipline, BT, Fincept backtest providers | Historical metadata queries 18/18 across six providers; no end-to-end calculations for these four | **METADATA ONLY; NOT CALCULATION-VERIFIED** | Run isolated, bounded synthetic backtests for each |
| Backtesting default data path | Historical PythonRunner NumPy1/NumPy2 dependency mismatch (missing yfinance in venv1) | **KNOWN BROKEN/AT RISK** | Fix data adapter in separate opt-in path; do not blind-install libs |
| AI Quant Lab / Qlib | Command catalog and source exist | **SOURCE PRESENT; RUNTIME NOT VERIFIED** | Read-only module status / minimal synthetic computation; no heavy training |
| Screener & Watchlist | Qt routes and old widget factories preserved | **SOURCE PRESERVED; GUI NOT RETESTED** | Open, search, save/reload without changing real user data |
| Portfolio / Risk | Qt routes and original tools present, including write-capable tools | **SOURCE PRESENT; KAIROS WRITE ACCESS DENIED** | Read-only holdings mock/projection & UI persistence in isolated profile |
| News, Economics, Crypto, Geo, Maritime, Equity, Agent Workbench | Routes present, but data feeds/paid providers/transitive dependencies vary; Equity earlier freeze not diagnosed | **FUNCTIONAL COVERAGE UNKNOWN** | Isolated screen-per-screen opening probe and feed/error diagnostics |
| MCP | Fincept server and tool registry available; contains order/account/portfolio mutations | **DO NOT PASS RAW CATALOG TO KAIROS** | Authenticated service-side read-only allowlist + negative tool-call tests |
| Trading / deployment | Original Fincept can issue real orders and auto-resume bots | **ORIGINAL BEHAVIOR NOT ALTERED; KAIROS ACCESS BLOCKED** | Only static/permission-denial tests; no broker/live trade smoke |

**Registered screens ≠ screens that work; metadata ≠ executed backtest; 82 calculated indicator outputs ≠ independently verified financial signals.** No source-level count can prove the majority of the entire Fincept application works. Quantifying that requires an isolated native GUI/test VM baseline and an explicit feature-level runtime pass/fail ledger.

## Reproduction from this source-only PR (local environment)

```sh
python3 -m unittest discover -s tests/fincept_audit -p 'test_*.py' -v

python3 tools/fincept_audit/functional_preservation_baseline_v1.py \
    --source-root . \
    --baseline tools/fincept_audit/fincept_source_baseline_v1.json

python3 tools/fincept_audit/technical_family_probe_v1.py \
    --original-technicals-dir fincept-qt/scripts/technicals
```

The independent PR #24 before/after regression check points `--source-root` to an **isolated snapshot of its sources** while using the **original** manifest. Any future approved edit to an original widget, preset or class must be justified, independently tested, and baseline update reviewed; the snapshot is intentionally strict.

For runtime GUI coverage, leverage Fincept's existing `src/app/ScreenSmokeTest.cpp`, which enumerates dock IDs and attempts construction. It refuses navigation while PIN-locked. **Do not use the running user's desktop profile, reset credentials, deploy bots, or restart the installed Fincept session** merely to obtain a green score; first clone an isolated testing profile, capture exact binary/source provenance, and run before/after on the same build environment. A screen-construction smoke alone still does not test data/provider features.

## No-destruction acceptance gates for subsequent KAIROS hybrid releases

1. **Original source inventory unchanged** or consciously reviewed with full before/after tests: 52 routes / 35 widgets / 6 presets are a **floor**, not an assertion that every source item is functional.
2. **Original executable GUI compatibility:** main and hybrid both build on the same native Qt/toolchain; same test profile/screens are exercised and compared, including layout persistence, error recovery, and no unexpected permissions or provider calls.
3. **Functional category expansion:** each original useful Fincept module gets an owned runtime test. Keep a coverage matrix with last verified SHA, platform, fixture, dependency set, status and unresolved issue; target a majority of **operational feature families actually proven**, not just code count.
4. **KAIROS independent:** when absent/crashed/offline, all original Fincept functions remain usable. Sidecar research tools must be additive, offline/read-only and explicitly enabled.
5. **Financial safety and scientific truth:** Fincept may compute preliminary statistics, but KAIROS independently validates provenance/as-of, costs, null control and risk. No existing Fincept trading tool exposed to agent or new LIVE permission.
6. **Release gates remain open:** Qt GUI runtime before/after, existing VM provider issues, historical methodology limits, license notice conflict, and KAIROS local snapshot tests `/DATA` are NOT resolved by this source-only PR.

**No existing Fincept source, installed executable, profile, service, dashboard, broker, API subscription or saved user state was altered in the production application.**
