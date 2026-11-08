# FINCEPT × KAIROS — Contratto vincolante per autonomia LLM e accesso agli strumenti V1

**Data:** 2026-11-08 · **Stato:** architettura proposta (documentazione sola lettura) · **Proprietà:** fork Fincept come prodotto; KAIROS canonico per scientificità, rischio e autorità.
**Motivazione esplicita dell'operatore:** «tutto questo deve poter funzionare in autonomia sotto il controllo di LLM ... i dati che mette a disposizione Fincept possano essere letti e interpretati da un cervello LLM passando per tutti i gate che stiamo costruendo».

Questo documento integra la [Master Roadmap generale](https://github.com/cometarossa/kairos-fincept-terminal/blob/docs/fincept-kairos-master-roadmap-v1/docs/roadmap/FINCEPT_KAIROS_MASTER_ROADMAP.md) in [PR #3](https://github.com/cometarossa/kairos-fincept-terminal/pull/3), il [Fincept-first ADR](https://github.com/cometarossa/kairos-fincept-terminal/pull/1), e l'inventario strumenti [PR #5](https://github.com/cometarossa/kairos-fincept-terminal/pull/5) e analisi [PR #6](https://github.com/cometarossa/kairos-fincept-terminal/pull/6), [PR #7](https://github.com/cometarossa/kairos-fincept-terminal/pull/7). Sono PR DRAFT, NON funzioni deployate. La costituzione KAIROS prevale sempre. Nessuna ripetizione degli inventari esistenti.

## Invariante centrale

**Fincept è il piano dati, strumenti e prodotto operativo; KAIROS è il modulo di interconnessione scientifica, verifica e autorità; l'LLM è il controllore di ricerca e ragionamento, NON il controllore diretto del broker.** Un qualsiasi modello compatibile (DeepSeek primario, Claude/Gemini/GPT/locale opzionali) può leggere strumenti Fincept *autorizzati*, proporre un piano di ricerca, invocare un catalogo di strumenti non mutanti, leggere risultati tipizzati, analizzarli, proporre nuove prove e decisioni di portafoglio teorico. La persistente orchestrazione headless continua anche se Qt o ChatGPT si chiudono.

**Non cambiare la UI Fincept finché non necessario**, non rimuovere widget o strumenti perché difficili, non sostituire i calcoli Fincept e KAIROS per mera equivalenza di nome. Preservare l'applicazione originale il più possibile, riparare le funzioni non operative, estendere con modulo KAIROS senza creare un altro terminale da zero.

## Pipeline prevista

```text
FINCEPT SOURCE & TOOLS (DataHub, dashboard, screeners, Quant Lab,
                     backtests, sentiment, macro, market data, ...)
       │  explicit registered read-only adapters, no UI scraping as primary
       ▼
Tool Catalog & read adapters (metadata, JSON schema, permissions, cost,
data provider, entitlement, timestamp, method and provenance)
       ▼
Data/Evidence envelope: asset, exchange/symbol, quote vs portfolio,
source ID, observed_at, available_at, received_at, staleness,
rights, quality, response hash, original reference, errors, cost
       ▼
Persistent LLM Tool Orchestrator (model-neutral)
- inspect catalog → ask allowed tool → receive typed output
- explore data & construct hypotheses → request experiments
- attach model/version/budget, rationale, contrary evidence
- memory lookup returns UNTRUSTED hints; resolve original ledger
       ▼
KAIROS GATES — independent deterministic verification
  G0 schema, identity, entitlement, request authorization
  G1 data quality, market time, completeness & freshness
  G2 temporal PIT / historical-as-of vs prospective freeze;
     outcomes/holdout protected from hypothesis generator
  G3 repeatable numerical checks, null baselines, costs/slippage
  G4 portfolio risk, ruin avoidance, drawdown, exposure, liquidity
  G5 policy, tool capability, approval, audit and fail-closed abstain
       ▼
Ledger of findings, accepted/rejected hypotheses and theoretical decisions
       ▼
FINCEPT KAIROS MODULE: evidence, risk, reproducibility, model verdict,
                     status, portfolio theory, pending next experiment
```

The G0–G5 labels above are **logical integration stages**, NOT replacements for, renamings of or bypasses around the already defined KAIROS Gate9R or constitution. Before implementation map every proposed stage to real canonical KAIROS gate IDs and evidence; if a control is missing or has an unknown implementation it is **NOT VERIFIED**, not green. Risk/execution authorization remains a separate constitution-bound gateway.

## Tool catalog contract and capability classes

Every candidate Fincept tool has an explicit unique ID, exact source path/version/entrypoint, semantic version, owner, input/output JSON Schema, engine requirements (Qt-bound vs Python headless), duration/cpu/memory, default timeout, authentication, entitlement, provider credits/cost ceiling, and allowable side effects.

Capability classification is **DENY-BY-DEFAULT**:

| Class | Examples | LLM use |
|---|---|---|
| `market.read` | Market data, watchlists, screener results, prices (with timestamp/quality) | Allow only after provider entitlement + freshness gate; no implicit live-broker access |
| `research.compute` | Historical indicators, independent backtest, factor tests, quant worker | Allow for synthetic/offline workloads at first; quota, sandbox and provenance |
| `research.simulate` | Hypothetical paper-portfolio accounting on fixtures | Separate, explicitly labeled, no real account mutation |
| `portfolio.observe` | Future authorized read-only IG snapshot | BLOCKED pending privacy, credentials isolation, licensing and security gate |
| `broker.mutate` | Place, cancel, modify, liquidate, leverage, tool MCP with trade side effects | **NEVER EXPOSE TO LLM/RESEARCH ORCHESTRATOR** |
| `security.mutate` | Live enable, kill-switch override, risk exception, secrets/runner changes | **NEVER EXPOSE TO LLM/RESEARCH ORCHESTRATOR** |

A feature offered in the GUI is not automatically callable by AI: first identify its source logic and side effects; extract an authenticated read-only adapter or use a governed data connector. Do not auto-enable all MCP tools. Separate a **catalog listing** from a **capability grant**; grants require explicit server-side ACL bound to agent/session, not model text. Server-side verification prevents direct HTTP/MCP bypass of UI logic.

## Scientific/evidence output minimum

A result is incomplete until it includes, or is explicitly marked missing for: `tool_id`, `tool_version`, `request_id`, `job_id`, `model_id`, `provider`, `source_id`, `source_ref`, `asset_id`, `observed_at`, `available_at`, `received_at`, `market_session`, `data_as_of`, `freshness_state`, `quality_flags`, `entitlement_status`, `content_digest`, `raw_evidence_ref`, `compute_environment`, `parameters`, `validation_report` and `cost`. Never invent unavailable timestamps or convert receiving time into event time. A source like news or scraped HTML remains **untrusted input**; prompt instructions embedded in it are not allowed to change tools, risk or authorization.

LLM selection and fallback are configuration, not data ownership. Each run records model/provider/version and token cost; if a provider fails, tool freshness is unknown, source rights are unknown or gate invalidates the experiment, result is **DEGRADED/ABSTAIN**, never implicit fallback into trading.

## Autonomous research and portfolio decision policy

1. Research supervisor picks next job from durable bounded queue, independent of Fincept Qt; no duplicate scheduler when KAIROS already provides that function.
2. LLM selects tool and creates hypothesis with explicit as-of clock and objective.
3. Tool adapters read data and run bounded calculations; mutable tools not visible; all trial attempts are recorded, even failed.
4. An independently configured deterministic evaluator evaluates admissibility/robustness, no leakage or outcome exposure before prospective resolution.
5. LLM may propose **theoretical** allocation, `HOLD`, `REBALANCE_PROPOSAL`, `ABSTAIN`, exposures and evidence. Outputs are proposals, not broker instructions or authoritative account positions.
6. Canonical KAIROS risk and policy gates evaluate and reject/permit theoretical decision recording. An LLM cannot sign its own pass, edit the evidence ledger, or override Gate9R.
7. Future broker connectivity requires a distinct, independently tested authorization interface, beyond this contract, initially IG read-only. `LIVE=false` and no new DEMO authority.

## Vertical acceptance tests for first usable prototype

- **Catalog:** inventory from PR #5, annotate read/compute/simulate/mutate, source and output schema. Every mutation route rejected by tool gateway even when called directly.
- **Tool read:** same fixed source snapshot returned identically through Fincept adapter and typed API; source, timestamps, quality and cost reported or marked missing.
- **Model-neutrality:** replay a synthetic structured sequence with fake DeepSeek and fake Claude using identical catalog permissions; no model-specific path is required.
- **Safety negative:** malicious prompt inside market news or tool response cannot invoke a forbidden tool, change risk policies, retrieve holdout or fabricate a successful gate.
- **Temporal:** intentionally stale/out-of-order, unclosed bar, unexpected lookahead or source unavailable leads to fail-closed decision, not `0.0` as a genuine market indicator.
- **Independence:** agent resumes a simulated research job after Qt exits or is killed, without losing/duplicating work; on restart the idempotent ledger shows one logical execution.
- **Portfolio:** theoretical decision references admissible calculations and limit checks; request resembling order/cancel has no endpoint available to research orchestrator.
- **Security:** no port exposed or privileged runner until KAIROS issue #619 and quarantine PR #618 resolved and independently reviewed; fork GitHub Actions remain disabled.
- **Deployment:** only after resource budgets/rollback/secret boundaries verified; no server installation or live APIs from this documentation change.

## Dependencies and ownership

Use existing roadmap task IDs:
- **DEV-00:** source-backed tool catalog and mode/side effects (PR #5–#7 pending).
- **API-01:** authenticated typed read-only tool gateway + contract test.
- **API-SCI-00 / DATA-01:** provenance/clock envelope and science evidence, mapped to actual KAIROS dual-clock invariants.
- **TOOL-01:** one first *real* Fincept function headless with synthetic data, failing closed.
- **RUN-01 / AI-01:** persistent model-neutral orchestrator and bounded LLM gateway.
- **MEM-01:** shared memory (PR #2), retrieval cannot grant authority.
- **SCI-01 / PORT-01:** independent experiments and theoretical portfolio decisions.
- **SEC-00, IG-01:** isolated security gate and separate future, read-only broker integration.
- **UI-01:** a KAIROS module inside existing Fincept UI, not UI redesign.

**Primary success criterion:** a compliant LLM can autonomously inspect an allowed Fincept data/tool catalog, invoke a real read-only/simulated quant tool, analyze the typed result, have a research/portfolio proposal *rejected or admitted* by independent KAIROS gates and show the complete evidence trail in Fincept, with no GUI requirement for the research workflow and no broker mutation. Only successful exact-sha acceptance tests establish implementation. This document is a design mandate, not proof that it has been implemented.

## Continuity and release

This is a standalone architecture addendum submitted as its own DRAFT PR rather than editing the busy PR #3 branch. The main branch, KAIROS canonical code and production runtime are untouched. At the next roadmap iteration, read this contract, verify PR status and decide whether to integrate its non-duplicating requirements into the master roadmap through the established review workflow. Never treat open PRs as completed features.
