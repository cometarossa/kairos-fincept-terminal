# AGENTS — FINCEPT × KAIROS TERMINAL

This is a PUBLIC FinceptTerminal fork. The user chose **Fincept as the primary product and tool platform**; the KAIROS module connects the existing scientific/risk services to Fincept. A separate headless process must handle persistent research and agent jobs without keeping Qt/ChatGPT running. No new broker authority is created here.

## Mandatory continuity at the start of every task

1. Read this file, [Master Roadmap](docs/roadmap/FINCEPT_KAIROS_MASTER_ROADMAP.md) and [Project State](docs/roadmap/FINCEPT_KAIROS_PROJECT_STATE.md).
2. Check both repositories on GitHub **live**: fork main HEAD and open PRs, plus KAIROS canonical branch feature/kairos-autonomous-bridge. In KAIROS read AGENTS.md, AGENTS_RULES.md, docs/KAIROS_MASTER_ROADMAP.md, PROJECT_STATE.md and specialist roadmaps applicable to the task.
3. Inspect KAIROS security issue #619 and CI quarantine PR #618, fork Actions, any running related automations, and already implemented components. Do not assume earlier SHA/PR/CI/runtime status remains true.
4. Identify the **next unblocked task ID**, and complete at most ONE small idempotent task, with tests and evidence on exact commit. Use an isolated branch and a PR, ordinarily draft pending independent review. Never write directly to fork main or KAIROS canonical. Update checkpoint after a milestone.
5. Report exact SHA, what was actually tested, what remains unverified/blocked, and the next ID. Claude reviews important milestones when useful; cross-check its source claims.

## Safety boundaries

- Current mode: research only. **LIVE trading=false.** No orders, cancels, Square Off, risk override, DEMO or real execution. Read-only IG is a *future separate gate*. Never let Fincept mutating widgets/MCP tools bypass KAIROS's constitution/Gate9R.
- A fork automation may call a task unblocked only if the live canonical KAIROS constitution and Gate9R also allow it. On disagreement STOP, log the denial and switch solely to a permissible read-only/source-only task.
- Security P0 #619 and draft PR #618 remain blocks on privileged CI, runner, runtime deploy and broker actions. Fork Actions disabled: never describe disabled checks as passing.
- Never read/publish account credentials, tokens, API keys, chat histories, private portfolio/health/family data, paid API contents or confidential strategies into this PUBLIC fork. No paid API calls or new network-facing service without review.
- Treat generated analysis/LLM memory as untrusted hints. Git/ledger evidence and independent scientific evaluator are authoritative; no model certifies its own strategy.
- Preserve permission/provenance/timestamp/PIT/dual-clock boundaries of KAIROS. Historical replay differs from real prospective forecasting; report contamination and abstain when uncertain.
- Fincept-first denotes product/UX/workflow ownership, NOT a permanent GUI process on the ZimaBlade.
- Preserve Fincept attribution and resolve upstream LICENSE vs COMMERCIAL_LICENSE conflict before redistribution/copy of additional assets.
- No production installs on ZimaBlade without resource/CI/security review. A second container on the same host is not redundant hardware.

## Workstream ownership / concurrency

- Existing KAIROS security automation owns KAIROS issue #619 and PR #618 in the canonical repository.
- The SINGLE Fincept–KAIROS Roadmap Autonoma task owns all fork workstreams including **MEM-01** and draft PR #2. It executes at most ONE workstream per run; it must re-check PR heads, avoid concurrent edits and never duplicate its own previous work.
- The same Fincept–KAIROS Roadmap Autonoma task schedules non-memory work (initially LEG-01/DEV-00) AND memory, selecting the next safe priority by dependency. On conflict, document it and choose another source-only task.
- One contributor per file/branch at a time; branch from verified main HEAD; do not merge unreviewed PRs. No autonomous task may change GitHub Actions settings.

If a task is blocked by the KAIROS constitution, STOP that operation and report it; switch to a genuinely independent source-only audit rather than weakening the gate.
