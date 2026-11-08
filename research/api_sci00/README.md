# API-SCI-00 — temporal evidence preflight (research mock)

Source-only, offline prototype for the **separate** Fincept→KAIROS scientific boundary. Does not replace KAIROS Gate9R, the canonical evaluator, prospective freeze ledger, source entitlements, or the independent risk veto. It does not expose holdouts or broker routes.

Run: `cd research/api_sci00 && python3 -m unittest -v test_temporal_contract.py`.

This is deliberately narrower than the full data contract. It checks required provenance and time ordering and rejects future-available data, unverified prospective freeze, missing entitlements and mutation-shaped fields. It returns `authority=false` in all cases; `ELIGIBLE_FOR_INDEPENDENT_REVIEW` is **not** scientific acceptance. Fixture-only tests never establish alpha. A real production boundary additionally needs canonical data-source lineage, full transitive payload screening, immutable digests, session calendar, licensing, trusted server identity, ledger verification, cost and evaluator integration. No provider/network calls.
