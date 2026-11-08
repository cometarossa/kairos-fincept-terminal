# TOOL-01 / API-01 compatibility audit — 2026-11-08

**Task:** TOOL-01 V3 pre-integration, source-only. **Status:** BLOCKED_FOR_COMPOSITION (not a runtime failure). No broker, network, GUI, provider or VM access.

## Exact source evidence

- PR #16 commit `97c9dc1148b1221dc8f2fa96932a10b9e8a50b1b`, `tools/fincept_authority/server_policy.py`, Git blob `48950e8c2d2b09c9b4314b90fd94936e01bdd950`: `synthetic-researcher` is granted `quant.volatility.read` and `market.fixture.read` only. `authorize(principal, tool)` checks literal membership in server-owned `_POLICY`.
- PR #18 commit `3083e483c3cf5e94b9b157835f67fbbecbd8cd5b`, `research/tool01_v2/fixture_boundary.py`, Git blob `90e61d63a39938239a3240375151e240d8aa9027`: `execute` requires evidence `tool_id == fincept.research.volatility.fixture.v1` and `capability == research.compute`, but independently checks a hardcoded principal allowlist.
- The ACL tool name, evidence tool ID, and capability name are **three different identifiers**. No verified mapping binds them. Passing `quant.volatility.read` to the evidence boundary is not possible as an ACL check because its `execute` does not accept or call `authorize`. Passing `fincept.research.volatility.fixture.v1` to `authorize` denies it under current policy.

## Consequence

The separate PRs cannot yet be described as one enforced, server-authorized tool path. The fixture boundary's hardcoded principal check is **not** the server-owned ACL and does not establish authentication. The SHA-256 fields validate syntax, not data-to-hash integrity or trusted provenance. No canonical Gate9R evaluation is connected.

## Smallest safe next increment

On a **fresh isolated branch** (do not modify PR #16/#18), create a composition-only test importing the exact two pinned implementations without copying Fincept licensed assets. Define one explicit, versioned mapping from ACL `quant.volatility.read` to evidence `fincept.research.volatility.fixture.v1` / `research.compute`; require the server-owned `authorize` verdict **before** invoking any fixture runner. Negative tests: reviewer denied, unknown principal denied, mismatched tool ID denied, forged request scopes denied, runner not called on denial, broker/security/risk/deployment names absent, synthetic evidence never gains scientific/trading approval. Include actual Fincept runner from PR #15 only after separately verifying its output schema and local VM runtime. Test on exact commit; CI remains NOT_RUN.

## Safety and review

KAIROS issue #619 remains OPEN and CI quarantine PR #618 remains DRAFT at this check. GitHub Actions status not independently attested in this audit; do not claim CI PASS. License redistribution unresolved. No integration, scientific acceptance, trading or deployment is authorized. This document is a source comparison, not a passing end-to-end test.
