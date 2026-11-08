# DATA-01 V1 — offline fixture OHLCV provenance envelope

Status: **SOURCE-ONLY / NOT INTEGRATED / NOT SCIENTIFICALLY ADMITTED**. One isolated iteration on fork main SHA `7716ee8613249fb44c4d14036c5bc16ed6f34e97`. Coordinate with API-SCI-00 draft PR #12, API-01 draft PR #9, Algo/Backtesting audit draft PR #11, LLM tool contract draft PR #8. No edits to their branches.

`ohlcv_envelope.prepare(rows, provenance)` validates a **synthetic-only** OHLCV fixture and produces a VectorBT-compatible `brokerCandles` payload plus a separate, deterministic provenance envelope. Explicit `SYNTHETIC_FIXTURE` and `FIXTURE_ONLY` are mandatory. Unknown/real sources fail closed. UTC-Z timestamps, monotonic unique bars, request boundaries, finite OHLCV, source identity and rights are checked. `actual_first/last`, bar count and SHA256 are recorded. It deliberately labels session-calendar coverage `UNVERIFIED_SESSION_CALENDAR` and science `NOT_EVALUATED`: neither successful metadata parsing nor provider `usingSyntheticData=false` proves real market origin, rights, causal PIT, fees, or scientific admission.

Run locally without network or broker:

```sh
cd research/data01_offline
python3 -m unittest -v test_ohlcv_envelope
python3 -m py_compile ohlcv_envelope.py test_ohlcv_envelope.py
```

12 synthetic tests pass on Python 3.11/macOS, including reject paths, stable digest and no mutation. **Not run in Debian VM**, not wired to Fincept VectorBT or KAIROS evaluator. This is a data-contract building block, not a deployed adapter. No order, broker, secret, paid API, GUI, server or runner action. The source preflight in API-SCI-00 remains the separate authority for historical-as-of/prospective timestamps, and canonical KAIROS scientific/risk gates are not implemented or bypassed here.

Next: DATA-01 V2 should compare this fixture envelope to API-SCI-00 schema and test a single offline VectorBT invocation with a real installed provider, without copying private data or changing its environment. Full calendar/source-rights and canonical gate tests remain outstanding. Security KAIROS #619 and CI quarantine #618 block privileged integration; fork Actions disabled.
