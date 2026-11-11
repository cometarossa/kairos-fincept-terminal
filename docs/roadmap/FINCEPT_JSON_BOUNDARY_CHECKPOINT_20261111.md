# QA-LOCAL: preserve JSON results on Decimal conversion overflow

2026-11-11; source-only review candidate against fork main
`7716ee8613249fb44c4d14036c5bc16ed6f34e97`. Advances functional preservation
in master roadmap draft #3. No new dashboard, bridge or quant engine.

## Reproduction and minimum correction

The original `fincept-qt/scripts/fincept_json.py` checks `Decimal.is_finite()`
before converting to float. `Decimal('1e10000')` is finite but converts to
`inf`; the subsequent strict `json.dumps(..., allow_nan=False)` raises
ValueError and no JSON envelope is emitted. The negative equivalent also fails.
This was reproduced locally on the original source, not inferred from a log.

The correction uses the existing `_finite_or_none()` helper after conversion.
The overflowing field becomes JSON null; valid neighboring fields survive.
Normal Decimal conversion, nonfinite/null handling, output schema and encoding
are unchanged. There is no attempt to change financial precision or serialize
arbitrary precision numbers as strings; this follows the existing null policy.

## Tests actually executed

`tests/fincept_audit/test_json_numeric_boundary_v1.py` exercises current source:

- Original red run: eight test methods, two failing signed-overflow subcases
  and four errors; three methods passed.
- Corrected run: **10/10 PASS**, including two additional NumPy/pandas cases.
- Covers positive/negative overflow, nested payload preservation, ordinary
  Decimal values including existing tiny-value underflow behavior, Decimal
  NaN/sNaN/infinities, float NaN/infinities, caller allow_nan override,
  one-line stdout, UTF-8 bytes, input immutability, ordinary scalars, NumPy
  arrays/scalars, pandas missing values and Decimal columns.
- Decimal handling also exercised with optional NumPy/pandas bindings disabled.

Linux cloud, Python 3.12.14, NumPy 2.3.5, pandas 2.2.3. No provider, market data,
broker or GUI invoked. Reproduce from repository root:

```sh
python -m unittest discover -s tests/fincept_audit -p 'test_json_numeric_boundary_v1.py' -v
```

## Compatibility and integration gates

Only one runtime expression plus its explanatory comment changes. No Qt source,
layout, indicator formula, saved profile or installed application changes.
This verifies serialization, not every consumer or a native GUI build.
No GitHub CI or independent review PASS claimed. Keep DRAFT until reviewed.

PRs #26/#27/#28 remain separate pending work. #28 at
`3cf22fd622bf34109088bbcaf4d0dd12d2806abd` was rerun in this continuation:
**42/42 PASS**, workflow query returned no runs. PR #29 independently extends
OHLCV input-preservation tests and is not duplicated here.

**Pin reconciliation required:** the earlier Portfolio audit tests pin the
original JSON helper SHA-256. They should reject this deliberately changed helper
if the branches are blindly combined. Before integration, preserve an original
Git-pinned helper for historical tests and run separate candidate tests with this
helper. Do not silently replace the historical pin or call the combined stack
green. No other contributor's branch has been edited for this fix.

KAIROS canonical remains `d0b75a51dcf45a2b5d9e88f15e0220e165abe273` at this
continuation's check. No KAIROS authority, runner, deployment, paid API, account,
credential or provider change. Budget increment zero. Original attribution kept.
Rollback: revert this isolated change; no migration. Next safe gate: independent
review and explicit original/candidate helper reconciliation before combining
the draft stacks. Qt6 build/GUI testing remains separately NOT_VERIFIED.
