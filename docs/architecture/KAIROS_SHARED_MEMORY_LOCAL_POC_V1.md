# KAIROS Shared Memory — isolated local proof (v0.1)

**Scope:** Independent, local-only Python library prototype for the Fincept-first architecture.
**Branch:** feature/kairos-memory-contract-local-poc-v1 of cometaRossa/kairos-fincept-terminal.
**Status:** Runs with synthetic data on the authorized iMac; **NOT deployed** on ZimaBlade.
**No broker access, no account keys, no network services, no LLM calls.**
**KAIROS controls:** security P0 #619 and CI quarantine #618 remain open. Neither is bypassed.

## Why this is not "ChatGPT's memory"

The Fincept UI and its agents will eventually use a **scoped, authenticated memory gateway**.
ChatGPT's private product Memory is a separate feature, and this prototype does not connect
to ChatGPT. Hindsight and Mem0 will be *optional search indexes*, never sources of truth.

### Layers

1. GitHub/immutable source records: code, decisions, PRs, issue statuses.
2. A deterministic evidence/decision ledger with externally anchored hashes.
3. This **local append-only application-level memory index**, with SQLite FTS5,
   timestamp filtering and provenance references, for fast deterministic lookup.
4. Optional Hindsight/Mem0 semantic index to *suggest* related records, always
   revalidated against their originals through the memory gateway.

Do not promote an LLM-generated summary or the database hash chain to immutable proof.
An administrator who can rewrite the complete SQLite database can regenerate the chain;
a signed, separately stored ledger is still needed. This POC has **no actual ACL gateway**
and must never be exposed as an HTTP endpoint. Bank IDs and scope strings are filters,
**not access control**.

## Verified on iMac, 2026-11-07

Environment: Intel macOS, Python **3.11.14**, built-in SQLite **3.51.2**, FTS5 available.
All inputs were synthetic: **300 records** spanning 3 scopes; 60 repeated local recalls.

| Measurement | Observed | Interpretation |
|---|---:|---|
| Unit tests | **14/14 PASS** | Source/datetime/scope/FTS/tamper/hindsight-mock safety |
| 300 synthetic writes | ~242 ms total | CPU/disk-local baseline only |
| Recall 60 iterations, median | ~1.92 ms | One token query, cached SQLite, three scopes |
| Recall p95 | ~2.02 ms | Not comparable to semantic embedding search |
| Reopen SQLite and resolve original | PASS | Durable across process reopen (not restart disaster recovery) |
| Hindsight mirror calls | mock PASS | **No live Hindsight backend**, no embeddings, no LLM |
| Mem0 | NOT TESTED | Backend later |
| ZimaBlade latency/resource/soak | NOT TESTED | Existing load would make direct deploy unsafe |

These timings are micro-benchmarks on local fake documents, **not a performance guarantee**
for a financial corpus or a real concurrent multi-agent workload.

## How to reproduce (no dependencies to install)

From the repository root:

\`\`\`bash
python3.11 -m unittest discover -s tests/kairos_memory_poc -p 'test_*.py' -v
python3.11 -m tools.kairos_memory_poc.bench_local
\`\`\`

Example; always write into a new, mode 0700 private directory and use **synthetic** data:

\`\`\`python
from datetime import datetime, timezone
from pathlib import Path
from tools.kairos_memory_poc import LocalEvidenceMemory

store = LocalEvidenceMemory(Path("/private/tmp/kairos-private-example/memory.sqlite"))
record = store.remember(
    scope="kairos:research",
    content="Synthetic trial 12 failed on its frozen evaluation window",
    source_ref="fixture:trial-12",
    observed_at=datetime.now(timezone.utc),
)
print(store.recall("frozen evaluation", scope="kairos:research"))
print(store.get_original(record.id, scope="kairos:research"))
assert store.verify_chain()
\`\`\`

Do **not** use a globally shared /tmp directory directly as the DB parent and do not
put real account data, prompts containing credentials or original private chats into
this POC. The code fails closed if the DB parent is group/world-accessible.

## Memory contract and correctness

- \`remember(scope, content, source_ref, observed_at, expires_at=None)\`: source mandatory; identical retries are deduplicated.
- \`recall(query, scope, as_of, limit)\`: default scope explicitly required; UTC timestamps
  enforce *both observation and recording time* <= as_of; active supersessions and expiry
  are evaluated relative to the same as_of.
- \`supersede(id, corrected_content, scope, source_ref, observed_at)\`: append correction,
  preserve original; once superseded, only the new record is recalled after correction time.
- \`get_original(id, scope)\`: exact stored original with timestamp and source; scope required.
- \`verify_chain()\`: detects local mutation/truncation inconsistencies **within the stored
  chain**; separate anchored audit is required.
- No APIs for \`place_order\`, \`cancel_order\`, \`enable_live\`, \`set_risk_override\`.
- Existing databases that are symlinks or group-readable are rejected. The FTS query escapes operators and uses lexical AND; **it does not understand semantics**.
- \`HindsightMirror\` uses documented Hindsight client method signatures
  \`retain(bank_id=..., content=..., document_id=...)\` and \`recall(bank_id=..., query=...)\`.
  Tests inject a fake client with no network. Only **fixture:** records in explicit
  allowlisted scopes can be mirrored in this initial POC.
- Hindsight \`UntrustedMemoryHint\` never provides broker authority or an authoritative
  record. It has no point-in-time guarantee; direct model or trade logic must not consume
  it as proof without resolving referenced evidence first.

## Production blockers

1. **Authentication/ACL**: scoped identity and tenancy independent of bank names;
   authenticated MCP/REST ingress, TLS or hardened local socket, no public port.
2. **Privacy/forget**: no secure erasure, retention governance, PII detection, per-tenant
   encryption or verified backup deletion yet. Do not ingest user private data.
3. **External anchor & backup**: no cryptographic signature or remote read-only anchor;
   SQLite integrity and WAL + restore/recovery need tested policy.
4. **Schema/semantic**: integration with Hindsight and Mem0 remains only a
   **mock-verified SDK contract**, not a live backend acceptance test.
5. **Latency/scale**: 300 synthetic records are insufficient to estimate real workloads;
   need >=1000 versioned, synthetic or sanitized evidence documents, p95 precision,
   source attribution, stale/conflict accuracy and bad-prompt injection tests.
6. **Headless**: no service process or deploy packaging has been created; a single-file
   index is not a fault-tolerant memory plane.
7. **Scientific authority**: exact-account equity, broker price, risk approval, order
   lifecycle and trading permissions must remain in independently verified systems.

## Next POC iteration

Build isolated Hindsight on the Mac using a **pinned release and sandbox** (Intel Mac requires
the vendor's slim variant), with DeepSeek or an approved local LLM and local embedding model
only once costs/privacy and egress are reviewed. Run the **same synthetic corpus and 30
question/answer source-verification pairs** on Hindsight and Mem0, not competing marketing
benchmarks. Fail closed on missing provenance, wrong chronology, cross-scope retrieval or
output that invents an order. Consult the [memory shortlist](https://github.com/cometarossa/kairos-fincept-terminal/blob/docs/kairos-persistent-research-plane-v1/docs/architecture/SHARED_AGENT_MEMORY_SHORTLIST_AND_POC_20261107.md)
in draft PR #1 for integration alternatives.

**Forbidden in this milestone:** installing on ZimaBlade, touching canonical KAIROS,
enabling the fork Actions, opening a broker, using a real portfolio, importing secrets,
or treating generated memories as evidence of profitability.
