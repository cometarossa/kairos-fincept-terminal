# API-01 V3 — isolated fixture decision chain

**Checkpoint 2026-11-08; research-only.** This branch is **stacked on PR #16**, not main. It does not modify the API-01 V2 branch and must not be merged before independent review of its dependency. Existing PR #9 (gateway), #15 (real Fincept volatility fixture), #12–14 (scientific/data) remain independent drafts; no copy or implicit integration is claimed.

The new `fixture_gate_chain.py` composes the **actual server-owned synthetic policy from PR #16** with a **deterministic in-memory toy volatility calculation** and a **separate mock gate**. The mock gate admits a proposal to a **research queue only** when a nonempty hypothesis and matching evidence SHA-256 are supplied, rejects tampering and mutation-shaped fields, and always reports `NOT_EVALUATED` and `trading_authority=false`. It does not actually enqueue, persist, call any LLM, call a real Fincept module, or invoke the KAIROS canonical evaluator.

Local tests: `python3 -m unittest discover -s tests/fincept_authority -v`. No network, broker, credentials, Qt, VM deployment, or API costs. This milestone is a small **contract demonstration**, not the requested full catalog→real Fincept tool→KAIROS gate end-to-end proof.

**Next task:** after reviewing stacked PRs, bind the actual headless volatility provider from #15 through the gateway #9 and server-owned policy #16, using provenance #12–14, then independently test fail-closed KAIROS gate adapter. Security issue KAIROS #619 and CI quarantine #618 must be checked afresh; no live authority.
