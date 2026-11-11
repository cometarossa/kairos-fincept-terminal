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
