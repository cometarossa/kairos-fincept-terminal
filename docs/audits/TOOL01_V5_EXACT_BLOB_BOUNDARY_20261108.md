# TOOL-01 V5 — exact-blob integration boundary audit (2026-11-08)

Status: **SOURCE_ONLY / NOT_TESTED runtime / no scientific approval**. This is one independent microiteration, not a repeat of PR #20 or the Debian VM tests. The original source files were fetched read-only by GitHub connector at their exact PR heads; the GitHub blob hashes below are verified by the connector. No code or branch owned by other PRs was modified.

## Exact source evidence

| PR | HEAD commit | file | Git blob SHA |
|---|---|---|---|
| #15 | `24d97689ddee17a2288de6310933457179454478` | `research/tool01_volatility/fincept_volatility_fixture.py` | `3eab179dc6b6617c62fc15d77e61ce647a9b3e7d` |
| #16 | `97c9dc1148b1221dc8f2fa96932a10b9e8a50b1b` | `tools/fincept_authority/server_policy.py` | `48950e8c2d2b09c9b4314b90fd94936e01bdd950` |
| #18 | `3083e483c3cf5e94b9b157835f67fbbecbd8cd5b` | `research/tool01_v2/fixture_boundary.py` | `90e61d63a39938239a3240375151e240d8aa9027` |
| #20 | `9760e1fc2c23b531a866311fe2b1e962af46aa14` | `research/tool01_v4/composition.py` | `4b858b6154b7ceda14b5579a3c1e39524af89b69` |
| #20 | same | `tests/tool01_v4/test_composition.py` | `16f962c1364efc159ef19b0d9fc646e510d44295` |

## Verified contract alignment

- PR #16 grants `quant.volatility.read` only to `synthetic-researcher`; PR #20 maps it to `fincept.research.volatility.fixture.v1` / `research.compute`; PR #15 emits exactly those evidence identifiers.
- PR #18 checks synthetic classification, two syntactically valid SHA-256 strings, a nonempty result dictionary, quality flags, zero declared API cost and `broker_authority is False`.
- PR #20 checks the server policy before invoking its supplied runner and then delegates to PR #18. These are **source observations**, not execution of the exact composed blobs.

## Concrete remaining gaps (fail-closed integration blockers)

1. **Untrusted identity transport:** `execute(principal, ...)` accepts a caller-provided string. The prototype is explicitly not authentication. A caller able to select `synthetic-researcher` can pass the toy policy; an actual service must bind the principal from an independently authenticated channel.
2. **No proof that hashes bind to execution:** PR #18 checks only 64-hex syntax, not that `input_sha256` matches supplied fixture bytes or `source_sha256` matches the allowlisted installed Fincept module. PR #20 does not pin those hashes. A forged evidence dict with arbitrary valid-looking digests could pass.
3. **No numeric/result integrity gate:** PR #18 checks `result` is a nonempty dict, but does not check the expected eight indicators, finite numeric values, bar count, observation/availability timestamps, or source rights. The actual PR #15 runner does check finite indicators internally, but PR #20 accepts an arbitrary injected callable.
4. **No independent canonical scientific adjudication:** `RESEARCH_ONLY` remains `NOT_EVALUATED`; no KAIROS Gate9R, dual-clock, cost/ruin or portfolio approval is invoked. No orders are authorized.

## Next bounded implementation task

On a **new isolated branch**, add a fixture-specific verification layer that checks exact expected indicator keys, finite numeric results, `bar_count=120`, explicit `SYNTHETIC_FIXTURE` and fixture rights, and binds SHA-256 to trusted bytes/allowlisted source identity supplied by the service (never from LLM request fields). Write negative tests for forged hashes, NaN/Infinity, missing fields and principal spoofing, using original PR #15/#16/#18/#20 files checked out at the above commits. Execute the tests against exact source files before claiming PASS. Then run a separately authorized read-only VM fixture; do not deploy.

## Safety and checkpoint

Canonical KAIROS P0 [#619](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/issues/619) remains OPEN; CI quarantine [#618](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/618) remains OPEN/DRAFT at this audit. Fork PR #1/#2/#3/#8/#10/#11/#15/#16/#18/#20 were OPEN/DRAFT at bootstrap. No Actions/runner/VM/Zima/IG/broker/credentials/network/API-cost changes, no merge, no scientific promotion. LIVE=false. GitHub CI not run. Source-only audit is not a runtime PASS.
