# LEG-01 — Fincept license and asset source audit V1

**Date:** 2026-11-08 Europe/Rome. **Fork base:** `cometarossa/kairos-fincept-terminal` main `7716ee8613249fb44c4d14036c5bc16ed6f34e97`. **Scope:** read-only source inspection. Not a legal opinion, licensing clearance, upstream contact or deployment authorization.

## Confirmed contradiction at exact base SHA

- [`LICENSE`](../../LICENSE), lines 1–16: AGPL-3.0-or-later grant. Lines 18–86: *dual licensing notice* purporting to restrict AGPL to noncommercial use and requiring paid commercial license for business/internal use; lines 128–133 reiterate this restriction.
- [`docs/COMMERCIAL_LICENSE.md`](../COMMERCIAL_LICENSE.md), lines 1–15: **v3.0, effective 2026-08-11**, says this repository is **AGPL-3.0-or-later and under no other license**, and that the prior separate commercial license for this repository is discontinued. Lines 71–76 expressly withdraw the former commercial-license requirement and enforcement provisions.
- These statements **conflict within the same source revision**. Do not infer that the restrictive terms are necessarily enforceable under AGPL, or that the later-dated document necessarily overrides all LICENSE clauses. Obtain authoritative clarification and, where appropriate, qualified legal review before commercial/internal deployment or redistribution.
- [`docs/COMMERCIAL_LICENSE.md`](../COMMERCIAL_LICENSE.md) lines 55–61 and `LICENSE` lines 89–106 reserve Fincept trademarks and branding/trade dress. Source code licensing, trademark rights, assets, and data/API service terms are separate questions.
- `LICENSE` lines 135 onward include a contributor assignment / CLA notice. Upstream contribution is a separate decision from fork-only work.
- The upstream license document describes AGPL source-availability obligations for redistribution and modified network service in `docs/COMMERCIAL_LICENSE.md` lines 20–31. This document does not certify which planned KAIROS integrations constitute derivative works.

## Initial asset / entitlement matrix

| Item | Source path | Current classification | Next check |
|---|---|---|---|
| Core Qt/C++ source | `fincept-qt/` | LICENSE_CONFLICT | Read source only; clarify licensing before redistribution |
| Fincept logos, icon and UI marks | `fincept_icon.ico`, `images/`, Qt screens/styles | TRADEMARK_AND_ASSET_UNVERIFIED | Inventory actual mark uses; no branded release |
| Bundled zip code | `fincept-qt/third_party/qzip/` | THIRD_PARTY_NOTICE_UNVERIFIED | Inspect headers, upstream license and attribution |
| Python/provider integrations | `fincept-qt/` | MODULE_AND_PROVIDER_RIGHTS_UNVERIFIED | DEV-00 per-module entrypoint, costs, headless support, authority |
| Fincept data/API services | `LICENSE` lines 78–86 | SEPARATE_SERVICE_TERMS | No paid requests; verify scopes and entitlements |
| Enterprise features | `docs/COMMERCIAL_LICENSE.md` lines 33–51 | NOT_ASSUMED_AVAILABLE | Do not assume Enterprise code/entitlements in this fork |

This is **triage**, not a full third-party dependency inventory. A bundled library is not evidence of licensing infringement.

## Operational decision and boundaries

1. DEV-00 may proceed as **source-only capability inventory**, marking each module LICENSE_UNRESOLVED / PROVIDER_TERMS_UNVERIFIED / THIRD_PARTY_NOTICE_UNVERIFIED. Do not integrate, copy or distribute ambiguous assets merely because they are visible in the public tree.
2. Preserve copyright/AGPL notices and attribution. Do not publish a branded derivative, expose modified services, copy Enterprise features or call paid data providers as a consequence of this audit.
3. Before redistribution or business/internal use, seek authoritative clarification of the conflicting upstream texts and relevant trademark/third-party/data terms. Do not contact upstream without operator authorization.
4. This task modifies **documentation only** in an isolated **draft PR**; it does not modify LICENSE, headers, branding, CI, broker, runner or runtime.
5. KAIROS canonical security P0 [#619](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/issues/619) and CI quarantine [PR #618](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/618) remain open and block privileged integration.

## Definition of Done — this increment

- [x] Exact main SHA and two license documents checked.
- [x] Conflicting clauses, relevant line references and initial asset boundaries documented.
- [x] Safe source-only DEV-00 continuation and distribution gate specified.
- [ ] Upstream/legal resolution: **NOT VERIFIED / not requested**.
- [ ] Full third-party and branding inventory: **NOT VERIFIED**.
- [ ] Operational licensing or provider access: **NOT AUTHORIZED**.

**Next task:** DEV-00, inventory 15–25 Fincept capabilities against existing KAIROS services, including source paths, provider/cost, headless feasibility, mutating authority and unresolved license status.
