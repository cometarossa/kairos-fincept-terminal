# Fincept -> KAIROS: non-destructive, OFFLINE research sidecar V1

**Status: prototype / dependency-stacked DRAFT; not deployed.**
Date: 2026-11-11. Fork main pinned `7716ee8613249fb44c4d14036c5bc16ed6f34e97`.
This branch is based on **open DRAFT #17**, which is based on **open DRAFT #16**. It **does not** edit or replace any original Fincept application code or merge other drafts. The independent real Fincept synthetic fixture runner is still **open DRAFT #15**. The bridge also references no KAIROS secrets or broker.

## Real composition: a single pinned tool (no general tool dispatch)

```
Fincept's original volatility_indicators.py (sha256: 76c8a232...)
 + actual PR #15 fixture runner (sha256: 35574f23...)
               |
  local, opt-in synthetic CLI
  server_policy.authorize("synthetic-researcher", "quant.volatility.read")
  exact capability mapping and pinned source bytes checked BEFORE subprocess
  private scratch copies, sanitized environment, bounded timeout
  exact fixture input digest, schema, numeric outputs, rights, zero cost
               |
    fincept_kairos_readonly_bridge_v1 JSON
    RESEARCH INPUT ONLY / NOT_EVALUATED / NO BROKER AUTHORITY
               |
        FUTURE KAIROS consumer (independent gate, not yet connected)
```

The tool-name drift from [DRAFT audit #19](https://github.com/cometarossa/kairos-fincept-terminal/pull/19) is explicitly resolved **only for this offline fixture**:
ACL `quant.volatility.read` maps to evidence ID
`fincept.research.volatility.fixture.v1` with capability `research.compute`.
Unknown/alternative mappings, generic execution, `tool_invoke`, `run_python_script`, broker actions and extra scopes are rejected before any tool execution.

**Toy principal, not authentication.** Anyone who can run this local CLI can specify
`--principal synthetic-researcher`. The draft #16 policy governs a toy
offline research lane only. Do not network-expose it, register it as a
service, issue MCP bearer credentials, or promote a fixture result.
The subprocess reads audited user-local installed `pandas`/`ta` dependencies
under an isolated Python flag, but dependency source/versions are **not attested
or sandboxed**; this is not an arbitrary code execution security boundary.
The pinned original Python module and pinned PR #15 harness are trusted
for this limited offline experiment only.

## Reproduction (local user, no subscription or paid API)

From a checkout of this stacked branch, with a local copy of the **exact** PR
#15 fixture script and original Fincept source (both SHA-256 pinned in code):

```sh
python3 -m unittest discover -s tests/fincept_authority -v
python3 -m unittest discover -s tests/fincept_kairos_bridge -v
python3 -m research.kairos_bridge_v1.sidecar \
    --principal synthetic-researcher \
    --tool quant.volatility.read \
    --fincept-module fincept-qt/scripts/technicals/volatility_indicators.py \
    --fixture-runner /path/to/PR15/fincept_volatility_fixture.py \
    --out /existing/private/directory/fincept_kairos_readonly_bridge_v1.json
```

Without `--out`, the fixture-only JSON is printed to stdout; no file is
changed. The report is written only to an explicitly supplied existing
directory; no Fincept profiles, dashboard layouts, source files or
system services are modified. It is not auto-forwarded to KAIROS.

### Evidence actually observed (Mac, 2026-11-11)

- **8/8 new stdlib unittest PASS** (deny-by-default ACL, no subprocess on
  denial, schema/provenance/authority rejection, numeric tampering, SHA
  pinning, fixed local output 0600/symlink refusal).
- Actual copied, exact Fincept volatility module was executed by the copied
  exact PR #15 fixture runner in a sanitized, bounded subprocess; output had
  **120 synthetic OHLC bars, 8 indicator fields**, fixture evidence hash,
  zero provider calls, `scientific_status=NOT_EVALUATED`,
  `broker_authority=false`, `trading_authority=false`.
- The first isolated subprocess attempt was **REJECTED** because Python `-I`
  hid the Mac's user-site `pandas` and `ta`. A second implementation loads
  only the local user-site dependency path explicitly, and the end-to-end
  offline proof passed. That dependence is **NOT** a production sandbox.
- **No Qt compile or GUI regression done**; this is separate from DRAFT #24.
  Fincept fork GitHub Actions are disabled: **NO FINCEPT CI GREEN CLAIM**.
  Source dependencies and environment have not been independently attested.

## 2026-11-15 — real sidecar subprocess-output regression and Mac smoke

**OPEN DRAFT / code published / local exact-blob evidence only.** The
existing research sidecar PR #25 was updated in place, **not** forked into a
duplicate PR. Before the docs-only commit, the exact code/test head was
`cc2f9bb2b5947e593b95b2d6e0085448c6518f4a`:

| Component | Published Git blob, verified against locally tested file |
|---|---|
| `research/kairos_bridge_v1/sidecar.py` | `b8070312dec300b8e7a2b24913c178b33b91ca99` |
| Existing `test_readonly_sidecar.py` | `30b4f221a375cf2f7fce187bad328775a43f94e5` |
| Added `test_bounded_capture.py` | `824d0f6014a4e0dc0c48d3817feb09b884bf3555` |

The previously unbounded `subprocess.run(..., capture_output=True)` was
replaced with a POSIX private-process-group `Popen` / selector reader:
`MAX_EVIDENCE_BYTES` (16 KiB) bounds **stdout + stderr together**;
**only stdout** is decoded as the evidence JSON. Warnings on stderr do
not contaminate valid stdout, and stderr is never returned as evidence.
An over-limit output, invalid UTF-8 stdout, bad process exit or deadline
failure fails closed. Private process group cleanup uses `SIGKILL` even
after the immediate child exits; this does not authorize a privileged
service. Original denial tests now patch the actually invoked `Popen`,
rather than the superseded `subprocess.run`.

**Mac local:** Python 3.12.9, `python -m unittest discover -s
tests/fincept_kairos_bridge -v`: **13/13 PASS, zero failures**, including
boundary 4096/4097 byte cases, shared 2048+2048 / 2048+2049 stdout-stderr
limits, benign stderr with valid stdout JSON, bad UTF-8, timeout and
existing authorization/evidence/report safety tests. `git diff --check`
PASS. All three test/source blobs independently matched GitHub.

**Separate real offline end-to-end re-smoke:** Mac Python 3.9.9,
unmodified original Fincept `volatility_indicators.py` pinned SHA-256
`76c8a2329c3109d801222ecc987f57005041533e8264c90f1d8b46a4c0109897`,
and exact PR #15 fixture script pinned SHA-256
`35574f23f043811d0524bd17c11dae7a48cc5234e5f0117e0fe60393762879d3`.
Actual `python -m research.kairos_bridge_v1.sidecar --principal
synthetic-researcher --tool quant.volatility.read --fincept-module
fincept-qt/scripts/technicals/volatility_indicators.py --fixture-runner
/path/to/pinned/fincept_volatility_fixture.py` **exit 0** with 120
synthetic bars / all 8 expected indicators. The returned
`fincept_kairos_readonly_bridge_v1` envelope has
`kind=SYNTHETIC_RESEARCH_INPUT_ONLY`,
`verdict=RESEARCH_INPUT_ONLY_NOT_SCIENTIFICALLY_ACCEPTED`,
`principal_is_authenticated=false`, `scientific_status=NOT_EVALUATED`,
`broker_authority=false`, `trading_authority=false`,
`external_api_calls=0`, `provider_credits=0`. Smoke stdout SHA-256
`28c6b08b9c23f6792a92ab8afc650cf5719a21bc3fef3a57fb84a391e57b5dfa`,
stderr 0 bytes. No `--out` file persistence or existing app/profile use.

**Limits:** the synthetic toy principal is **not authenticated**;
Python user-installed dependencies are not supply-chain attested;
Windows portability is **NOT VERIFIED** (this capture uses POSIX
selectors/process groups); full Fincept Qt workflows, provider data,
scientific predictive merit, KAIROS tool dispatch, native fork CI,
broker access and deployment are **NOT VERIFIED**. This is not a trading
gateway, validated strategy or authorization to run a live or demo order.

## 2026-11-16 — descendant pipe lifetime: source-real POSIX regression

**Test-only increment in the existing DRAFT #25; no change to the sidecar
logic, installed app, dependency chain or trading authority.** At exact
published PR code+test commit `f620242992848bc654a1ec9de9921fc2fa0d748b`
the new source-pinned
`tests/fincept_kairos_bridge/test_bounded_descendants.py` has Git blob
`560dadb58de885ea63c79a1b77f01f2ab8492087`; the unchanged
`sidecar.py` blob remains `b8070312dec300b8e7a2b24913c178b33b91ca99`.

The regression starts an **actual** private POSIX process group in an
isolated Mac checkout and covers two cases: (1) the direct parent exits
successfully while its descendant keeps the captured pipe descriptors open;
the sidecar raises `PINNED_TOOL_UNAVAILABLE_OR_TIMEOUT`, then kills the
descendant before it can write a delayed completion sentinel, and a start
sentinel independently proves the child ran; (2) a short-lived descendant
finishes normally, closes the inherited pipes and returns valid stdout
without a spurious timeout. No broker, GUI, network or user profile.

**Exact post-publication remote worktree** checked out from GitHub at
`f620242992848bc654a1ec9de9921fc2fa0d748b`, clean git status;
macOS 14.5 / Python 3.12.9,
`python3.12 -m unittest discover -s tests/fincept_kairos_bridge -v`:
**15/15 PASS** (the previous 13 tests plus 2 real POSIX descendant tests).
Log SHA-256 `584d70cae6782ddc22de2b54907a5da4a5564f0c0c3c129d6df46d98a977262a`.
No native GitHub Actions were returned by the Fincept fork for this
revision (**NOT VERIFIED**), nor does this result prove portability to
Windows or full Fincept Qt lifecycle. Reviewer should still assess
process-group cleanup and dependency isolation independently before merge.

## Safe interpretation / next steps

The JSON is not a market observation, data entitlement, scientific
validation, reproducible alpha, official authenticated agent API, hedge,
risk override or trade instruction. The source hashes attest only exact
locally read Python bytes, not installed dependency supply chain or an
unforgeable identity. If Fincept is absent, version-mismatched, or a tool
fails, **the bridge rejects**; Fincept can run independently. If KAIROS is
down, this opt-in proof creates no background agent or privileged service.

Next: independently validate this synthetic-only envelope at KAIROS input
boundary as `HOLD_SYNTHETIC_ONLY`, and only later explore a transport
between authenticated non-mutating services with data licenses/PIT, cost
quotas and exact canonical science/risk gate mapping. This proof **does not
authorize** connecting the existing unrestricted Fincept MCP server, exposing
KAIROS dashboard's unauthenticated LAN API to the public internet, or
activating live/demo broker actions.

License notices in fork `LICENSE` vs `docs/COMMERCIAL_LICENSE.md` remain
contradictory; do not package copied Fincept source into KAIROS or distribute
a derived binary before resolving terms.
