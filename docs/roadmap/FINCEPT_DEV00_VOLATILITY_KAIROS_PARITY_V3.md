# DEV-00 V3 — Fincept volatility vs canonical KAIROS: overlap and contract drift

**Date:** 2026-11-08 (Europe/Rome). **Scope:** one isolated SOURCE-ONLY feature-contract comparison following DEV-00 V1 [draft PR #5](https://github.com/cometarossa/kairos-fincept-terminal/pull/5) and V2 [draft PR #6](https://github.com/cometarossa/kairos-fincept-terminal/pull/6). Neither is merged. This is NOT a runtime, numerical parity, scientific or legal certification.

## Pinned source references

- Fincept fork main SHA 7716ee8613249fb44c4d14036c5bc16ed6f34e97: [volatility_indicators.py](https://github.com/cometarossa/kairos-fincept-terminal/blob/7716ee8613249fb44c4d14036c5bc16ed6f34e97/fincept-qt/scripts/technicals/volatility_indicators.py) (L6–13 imports; L16–35 ATR; L38–66 Bollinger; L69–101 Keltner; L104–151 Donchian/Ulcer; L154–201 aggregate).
- Canonical KAIROS branch feature/kairos-autonomous-bridge SHA 77f0c0cc635945c808cafd581c1bfbcaaddffcac: [analysis/technical/indicators.py](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/blob/77f0c0cc635945c808cafd581c1bfbcaaddffcac/analysis/technical/indicators.py) (L21–45 validation; L48–76 preparation; L155–198 volatility) and [ai/features/multi_timeframe_features.py](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/blob/77f0c0cc635945c808cafd581c1bfbcaaddffcac/ai/features/multi_timeframe_features.py) (uses ATR_Percent and BB_Position).
- KAIROS files were read from GitHub at their exact SHA; NO KAIROS source/data was copied into the Fincept fork. Availability of any module at runtime has NOT been checked.

## Source-backed overlap and incompatibilities

| Feature | Fincept source | KAIROS source | Consequence |
|---|---|---|---|
| ATR | Explicit 14-period window, fillna False, lowercase high/low/close. Wrapper around ta.volatility.AverageTrueRange | Same library call but uppercase High/Low/Close; window omitted, depending on installed ta default | Duplicate concept, not demonstrated numerical equality; exact ta version and default must be pinned |
| Bollinger | Window 20, deviation multiplier 2, lowercase close, outputs bb_mavg/hband/lband/pband/wband | Window 20, deviation multiplier **2.5**, uppercase Close, BB_High/Low/Mid/Width/Position | NOT default-equivalent: parameter and output schema must be explicit |
| Keltner | window 20, window_atr 10, fillna False, original_version True; returns 7 fields | Library default arguments; returns only KC_High/Low | Potentially different defaults and output coverage; parity NOT VERIFIED |
| Donchian/Ulcer | Functions exist and aggregate includes the results | Not present in canonical add_volatility_indicators function | Potential additive research candidate; NOT proof KAIROS lacks it elsewhere |
| Data schema | lowercase OHLC input; aggregate copies the dataframe | uppercase OHLC; prepare_dataframe may drop missing bars and substitutes Volume=1000 when absent; volatility method mutates passed frame | Contract needs explicit casing, UTC closed-bar ordering, missingness policy and no silent synthetic-volume use as market evidence |
| Error behavior | Direct wrappers propagate ta exceptions; missing warmup/schema validation in this file | Broad try/except logs failures and fills indicator columns with zeros if missing | Fail-closed adapter needed on BOTH sides: never accept zero fabricated by error handling as actual volatility |
| PIT/provenance | No available-at, observed-at, source identity parameter in these indicator wrappers | No PIT envelope in the local indicator function; broader KAIROS dual-clock rules exist separately | Adapter must supply timestamp, source, eligibility and evaluator separation |
| Dependencies | pandas and ta imported; no CLI in this file | pandas, numpy, ta and core.utils | Headless candidate only. Inspected iMac Python 3.11 lacks pandas, numpy, ta and pytest; no runtime calculation test performed |
| Authority | No direct trading call in this particular Fincept module | Canonical KAIROS constitution/Gate9R owns independent risk and execution controls | Feature results and LLM memory must NEVER authorize broker orders |

## Technical integration decision

**KEEP canonical KAIROS indicator/scientific authority; use Fincept as the product, tool catalog and research comparison surface.** The user-chosen Fincept-first architecture does NOT mean silently replacing KAIROS formulae or risk gates with Fincept library defaults.

Future read-only capability design (concept, not deployed):
- KAIROS.features.volatility.v1: existing KAIROS outputs with source identity, as-of eligibility, complete bar timestamp and error state.
- Fincept.research.volatility.v1: optional experimental comparator on synthetic input, explicit parameters and pinned dependencies, no broker or protected holdout access.
- Fincept KAIROS UI side-by-side: provenance, values, parameters, data age and explicit NOT COMPARABLE when formulas differ.

No duplicate scheduler, data ingestion, evaluator or indicator calculation unless justified by documented measurable gaps. No Fincept exchange orders, broker credential tooling or MCP mutating capabilities are part of this research contract.

## Tests executed on Mac — 10/10 PASS, static-only

Added [tests/fincept_kairos_contract/test_fincept_volatility_static_contract.py](../../tests/fincept_kairos_contract/test_fincept_volatility_static_contract.py). Python 3.11 stdlib AST/unittest reads the exact Fincept file without importing it or ta/pandas.

Checks: six public function names; ATR default 14; BB window 20 and multiplier 2; Keltner/Donchian defaults; lowercase OHLC; pandas/ta imports; absence of named direct network/broker imports; absence of direct calls to named trading mutations in this file; aggregate output fields; no source/PIT parameters. This is schema-drift detection, NOT a proof of numerical parity, side-effect-free transitive imports, end-to-end headless runtime, lookahead safety, data rights or performance. No network, third-party installation, GUI or broker operation was performed. Pytest is not installed; unittest was used successfully.

Command: python3.11 -m unittest discover -s tests/fincept_kairos_contract -p 'test_*.py' -v
Result: Ran 10 tests, OK; compileall of that test directory PASS.

## Next gated increment

1. [LEG-01 draft PR #4](https://github.com/cometarossa/kairos-fincept-terminal/pull/4) records conflicting LICENSE / docs/COMMERCIAL_LICENSE.md; this is not licensing clearance. Clarify before code redistribution/operation.
2. Under an approved sandbox with pinned ta/pandas and synthetic complete OHLC bars, compare actual ATR/Bollinger values with explicit matching parameters, windows and warmup, and independent golden reference values. No silent zero/NaN coercion.
3. Establish a versioned UTC bar/PIT/source identity contract; reject duplicate, missing, unclosed or out-of-order bars, and never treat synthetic Volume as provider-originated evidence.
4. Keep KAIROS current calculation authority and expose secondary Fincept result only for independent research validation; record differences rather than override originals.
5. Stop if imports require credentials/external services, license is unsettled, provider cost/entitlement unknown, or any broker-mutating path emerges.

**Permanent blockers:** KAIROS security [issue #619](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/issues/619) OPEN and CI quarantine [PR #618](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/618) OPEN DRAFT; fork GitHub Actions OFF. No ZimaBlade deploy, IG, DEMO/LIVE, trades, paid provider calls or external ports.
