# QA-LOCAL — independent original portfolio analytics regression

Date: 2026-11-11. Source/test-only, pending independent review. This specialist
checkpoint advances QA-LOCAL / functional preservation in the master roadmap
[draft #3](https://github.com/cometarossa/kairos-fincept-terminal/pull/3).
It does not claim PORT-01 scientific admission or production integration.

## Reconciled sources and dependencies

- Fork main: `7716ee8613249fb44c4d14036c5bc16ed6f34e97` (Fincept 4.5.1).
- This work is stacked on preservation draft #26, exact parent
  `348db5a3014b6c0401b280731f1200474fbbcfd2`. It reuses all six parent files;
  it does not copy them into another independent main-targeted PR.
- Fork PRs #3/#8/#11/#15/#16/#17/#19/#24/#25/#26 checked OPEN/DRAFT.
  Open PR inventory contains no equivalent portfolio numeric oracle suite.
- KAIROS canonical checked at `d0b75a51dcf45a2b5d9e88f15e0220e165abe273`.
  #640/#641 remain OPEN/DRAFT. Exact-head hosted CI success: #640
  `40a67569bc65d5bda965440b526d82a986816d23`, run 42934907812;
  #641 `3336ac9fb2f012a3304903b202d1132dd048a4d8`, run 42931682930.
  Other local-only checks remain pending/queued, not passed.
- KAIROS runner recovery #632 remains OPEN/BLOCKED. No host admission claimed.
  Installed Fincept, Zima and MATER runtime: NOT_VERIFIED in this session.
- Fincept #26 exact-head workflow query returned no runs. Fork Actions are
  documented disabled; this work changes no setting and claims no GitHub CI PASS.

## Increment and independent oracle

Added `tests/fincept_audit/test_portfolio_metrics_oracle_v1.py` to execute
the ORIGINAL `fincept-qt/scripts/portfolio_metrics.py` and its original
`fincept_json.py` helper. Both source SHA-256s are pinned before import and
verified bytes are executed directly, avoiding stale bytecode. No application
file, production dependency declaration or formula is modified.

Only `_download` is substituted in memory, returning fabricated prices. This
does NOT test Yahoo/yfinance, a production external-data adapter or Qt wiring.
The synthetic benchmark alternates -1%/+1% for 60 days. ALPHA returns twice
that, BETA half. With weights 1/4 and 3/4, portfolio returns are exactly
7/8 of benchmark returns. Therefore independent expectations are:

| Quantity | Expected value |
|---|---|
| Portfolio beta | 7/8 |
| Holding betas | 2 and 1/2 |
| Portfolio sample annualized volatility | `0.00875 * sqrt(60/59 * 365.25)` |
| Historical 95% daily VaR and CVaR | 0.00875 each |
| Variance contributions | 4/7 and 3/7 |
| Correlation | 1 |
| Synthetic risk-free quote conversion | 4% -> 0.04 |

These closed-form constants do not call Fincept to generate expectations and
do not mirror its covariance/percentile algorithms. Tolerance: 12 decimal
places. Calendar is daily synthetic, not an equity trading calendar.

Additional tests verify missing holdings and coverage, explicit equal-weight
fallback, missing benchmark/yield, insufficient history, constant prices,
immutable inputs, invalid symbols, download failure, empty data, and one-line
strict JSON from the original CLI function. Common Python socket/DNS calls are
denied during each test; patch state is restored with ExitStack. This is defense
in depth, not an OS sandbox or supply-chain attestation.

## Executed evidence

Environment: cloud Linux x86_64, Python 3.12.14, NumPy 2.3.5, pandas 2.2.3.
`ta==0.11.0` installed into an isolated scratch dependency directory solely to
rerun the inherited five-family tests. No user machine or global package set changed.

| Verification | Result |
|---|---|
| New original portfolio functional tests | PASS, 12/12 |
| Parent original source preservation suite | PASS, 9/9 |
| Parent five-family technical probe tests | PASS, 4/4, 82 indicator columns |
| Combined local unittest suite | PASS, 25/25 |
| PR #24 exact source `d5b27bf62c65394818cc6a4dd13efe49c9ea3090` vs original baseline | PASS_STATIC_INVARIANTS; 52 routes, 36 widgets, seven presets |
| Native Qt compile / before-after GUI / saved profile | NOT_VERIFIED; CMake absent from this environment PATH |
| Real provider, installed PythonRunner, cross-market calendars | NOT_VERIFIED |
| Independent reviewer and GitHub CI on this increment | NOT_VERIFIED; do not auto-merge |

Reproduce from repository root using an environment containing the versions above:

```sh
python -m unittest discover -s tests/fincept_audit -p 'test_*.py' -v
```

Portfolio tests alone need only NumPy/pandas and stdlib:

```sh
python -m unittest discover -s tests/fincept_audit -p 'test_portfolio_metrics_oracle_v1.py' -v
```

The subset is executable without Qt, yfinance, credentials, paid APIs or KAIROS.
It does not certify all Portfolio/Risk features or economic strategy performance.

## Review, rollback and next concrete priority

This increment changes tests, the preservation coverage row and this checkpoint.
Review as a small stack above #26; do not alter other contributors' branches.
Rollback: drop/revert this increment's three files; no runtime state to recover.
No deployment, runner reactivation, broker operation, LLM call or new cost.
License text conflict remains a distribution review gate; original attributions
and application source are untouched.

Next QA-LOCAL increment: independent portfolio tests for mixed trading calendars,
staggered listing history and anticorrelated holdings. Explicitly assess existing
zero-fill behavior before considering any change; never silently alter formulas.
In parallel planning, DEV-01/#24 still requires an isolated, compatible native Qt
toolchain and original/hybrid GUI comparison. Do not create a second KAIROS widget.

## Second increment — incomplete histories and calendar characterization

Eight further tests executed on the unchanged original module: **33/33 total**
(20 Portfolio tests + 13 inherited). Three additional numerical/behavior oracles
cover anticorrelation (beta 1/8, risk contributions 4 and -3), a sufficient
40-return shared window, and an explicit every-second-day calendar convention.
An all-holdings-absent case verifies no portfolio is fabricated.

Four tests reproduce shortcomings; their PASS means reproduction, NOT acceptance:

| Finding | Reproduced original behavior | Integration verdict |
|---|---|---|
| PM-01: short shared history | 10 BETA returns padded into a 60-row portfolio; coverage 1, warning present | BLOCKED for scientific use without a data policy |
| PM-02: stale tail | BETA ends on Jan 21, portfolio as_of Mar 1, coverage 1, 60 portfolio vs 20 BETA returns, no warning; padding reduces estimated volatility | FAIL disclosure; scientific use BLOCKED |
| PM-03: internal gap | Missing Jan 31 price becomes zero that day and a two-day return the next; no warning | Calendar/data provenance NOT_VERIFIED; scientific use BLOCKED |
| PM-04: insufficient prices | Two closes produce one return; BETA disappears from holdings but missing=[] and warnings=[] | FAIL disclosure |

The mixed-calendar oracle proves the current zero-fill convention is implemented
consistently. It does not prove missing quotes are exchange closures. No complete
calendar or source freshness certification exists in this input contract.
Next small code increment: disclose missing-return padding and insufficient-return
exclusion, preserving all numerical formulas; submit separately above this audit.
The native GUI/real provider/independent-review gates remain open.

## Third increment — candidate disclosure correction (separate draft)

Dependency: audit PR #27, exact parent
`60b5a74705afdff3b3f4c4a29fa51c5365b9bfb6`; #27 itself depends on #26.
This is a **review candidate**, not an installed fix. Unlike the preceding
source-preservation audit, this increment deliberately changes two application
files for the reproduced disclosure defects:

- `fincept-qt/scripts/portfolio_metrics.py`: append warnings for holdings with
  fewer than two finite returns, and count missing return observations actually
  zero-filled in the chosen calculation window. The warning states calendar/data
  completeness is unverified; it never labels every gap a market closure or outage.
- `fincept-qt/src/screens/portfolio/PortfolioScreen_Handlers.cpp`: pass existing
  `a.warnings` to the existing risk tooltip and warning color. The service already
  parses warnings but previously only logged them. No new widget/layout/provider.

No formula, allocation, coverage value, timestamp, return window or error schema
changes. No suppression of existing warnings. Coverage continues to mean weighted
holding coverage, not temporal completeness. The intended visible behavior is a
warning-colored existing risk note with the quality notes in its tooltip.
**This visible behavior is source-wired but not GUI-runtime-verified.**

### Red/green evidence and compatibility

Nine new current-source tests were written before the patch: **six failed** on
missing disclosure/UI wiring, three passed. After the correction all nine pass.
One of them runs nine input scenarios through both original and current modules
and requires **exact equality of the entire output except warnings**; it also
requires every old warning to survive. Scenarios: complete, constant, globally
short, sufficient shared history, insufficient shared history, stale tail,
one-return exclusion, internal gap, entirely absent holding.

The 20 original numerical/characterization tests still execute **original source**
from fixed Git commit `7716ee8613249fb44c4d14036c5bc16ed6f34e97`, hash-verified
before execution. They do not silently switch their original pin to the patched
file. The nine new tests execute **current source**. Both use the same pinned
original JSON helper and synthetic download boundary. All combined tests:
**42/42 PASS** (20 original + 9 candidate + 13 inherited preservation/technicals).
The one Qt source test is explicitly not a compilation or GUI test.

Reproduction requires Git and the pinned baseline commit locally available in
addition to the previously listed Python dependencies. For a shallow checkout
missing that object, fetch that exact public Fincept commit first; absence must
fail rather than skip the original/candidate comparison.

### Remaining gates and risks

- **Qt build/GUI acceptance BLOCKED in this environment:** CMake not on PATH;
  the available `/usr/bin/qmake` wrapper fails because its Qt5 executable does
  not exist. The project requests Qt6 6.8.x. No global toolchain installation,
  installed application mutation or alternate GUI evidence claimed.
- Existing preserved source registry checks pass; no screens/widgets/presets
  removed. Portfolio behavior changes only in disclosure, pending native review.
- A legitimate mixed exchange calendar also produces the warning. This is
  intentional uncertainty disclosure; no calendar inference or error assertion.
- Gaps shared by every holding may not create a row in the union return index;
  this patch cannot certify temporal completeness or detect all provider gaps.
- Warnings do not repair historical return alignment, freshness or point-in-time
  evidence. PM-01/02/03 scientific admission remains BLOCKED. PM-02/04 disclosure
  corrected in candidate source only; runtime acceptance remains NOT_VERIFIED.
- Independent review, fork GitHub CI and original/hybrid GUI comparisons remain
  NOT_VERIFIED. No auto-merge or deploy, credentials, broker, paid API, service,
  runner, security setting, license or original user profile changes.

Rollback: revert this candidate commit; no data migration or runtime state.
Next gate: independent review plus a native Qt6 build and isolated risk-tooltip
smoke, including clean history, missing history and failed refresh. A subsequent
calendar-aware methodology change needs its own specification and independent
numerical validation; it must not be smuggled into this disclosure-only fix.
