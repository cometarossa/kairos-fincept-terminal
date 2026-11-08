# API-01 V2: server-owned capability boundary (synthetic-only)

This standalone Python prototype is a **non-networked** ACL decision helper. The service owns the allowlist; LLM-supplied roles, scopes, approvals and requests never grant authority. Its principals are deliberately fake and hard-coded. The prototype is **not** authentication: production use requires an independently verified identity transport, revocation, audit ledger, versioned tool schema, budget/timeouts and separation from any privileged broker runtime. Do not attach it to the Qt app, an MCP endpoint or a real broker.

ALLOW_READ_COMPUTE_ONLY is a permission to call a hypothetical read/compute tool, **not** a KAIROS scientific gate verdict. All resulting hypotheses remain NOT_EVALUATED, no Gate9R approval or trading permission exists. This prototype does not import any Fincept licensed assets. Follow PR #9 for the earlier gateway mock, PR #8 for contract, PR #15 for the real volatility headless experiment; do not treat their draft code as merged.

Local test: python3 -m unittest discover -s tests/fincept_authority -v.
