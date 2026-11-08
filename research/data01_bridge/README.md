# DATA-01 V2 — cross-PR synthetic fixture → temporal preflight → real VectorBT provider

**Status:** one narrow offline functional test, not merged, not a scientific backtest, not a service.

## Exact inputs and run evidence (2026-11-08)

- Fincept fork main base: `7716ee8613249fb44c4d14036c5bc16ed6f34e97`.
- DATA-01 PR #13, head `240e10d502809072c5fc720b1987e6d40165469e`, source `research/data01_offline/ohlcv_envelope.py`, VM copy SHA-256 `dcd274943d4dbbe3a139d5f83592c8d439e15dfd3fd3d53dd37760006b3b196b`.
- API-SCI-00 PR #12, head `334fda9c6e8f03e50d0947a24a1dce811758a8c8`, source `research/api_sci00/temporal_contract.py`, VM copy SHA-256 `1949c7fd9b5943a8c2203b069a5d59788684d3059ada29f5276a77b560d51d22`.
- Fincept installed VectorBT provider: `/home/lab/fincept-app/usr/share/fincept-terminal/scripts/Analytics/backtesting/vectorbt/vectorbt_provider.py`; interpreter `/home/lab/.local/share/com.fincept.terminal/venv-numpy1/bin/python`.
- VM Debian 13 on iMac; no GUI restart, broker access, install, network service, Zima, or GitHub Actions.

**Verified command:** `python3 -B bridge_fixture.py --envelope-file ohlcv_envelope.py --temporal-file temporal_contract.py --provider-file /home/lab/fincept-app/usr/share/fincept-terminal/scripts/Analytics/backtesting/vectorbt/vectorbt_provider.py --provider-python /home/lab/.local/share/com.fincept.terminal/venv-numpy1/bin/python`, with source files copied into a private `/tmp/fincept-data01-v2-fixture` directory in the VM.

**Actual VM output:**
```json
{"bar_count":320,"broker_authority":false,"digest":"235f04216aef90bf3aaa9edf660af0f8d4f9ed28d170342b90697a8d9a9ffbfa","provenance_class":"SYNTHETIC_FIXTURE","provider_source":"synthetic-regression-fixture","provider_status":"completed","provider_synthetic_flag":false,"result":"FIXTURE_PIPELINE_PASS","scientific_status":"NOT_EVALUATED","temporal_verdict":"FIXTURE_ONLY"}
```

**Interpretation:** a genuine installed VectorBT backend accepted the 320-bar OHLCV payload prepared by DATA-01 and preflighted by API-SCI-00, with no broker credentials. The provider reports `usingSyntheticData=false` **despite** artificial inputs: this means only its *internal synthetic fallback* was not used. The authoritative fixture classification remains `SYNTHETIC_FIXTURE`. The temporal gate returned `FIXTURE_ONLY`, and the bridge explicitly preserved `NOT_EVALUATED` and `broker_authority=false`. This is a **functional interface test**, not alpha, real data, PIT correctness, independent scientific certification, net-cost parity or trading permission.

## Scope, unresolved constraints

- This harness dynamically loads two *separate unmerged PRs* from explicitly supplied paths. It does not copy or merge their code, mutate either branch, or change the Fincept installed package.
- The fixture data are deterministic, artificial and not a market series. The 320-bar source digest is reproducible.
- The synthetic `available_at` is chosen to follow the final candle; the contract validates chronology but does **not** independently prove actual historical publication time or prospective freezing.
- No provider request for remote data is intended; no kernel network isolation was applied. A Python subprocess is executed; use only in an offline controlled VM. No real account access was made.
- The script does not supply the full DATA-01 envelope to VectorBT: it passes only provider-compatible keys and retains the envelope for separate audit. An actual provenance-preserving API bridge is still needed.
- Installed Fincept binary/source parity and the other five backtesting providers remain unverified. No CI, independent review, GUI smoke, persistent headless service or scientific evaluator run occurred.
- P0 KAIROS #619 OPEN and CI quarantine PR #618 OPEN/DRAFT; fork Actions OFF. No mutation privileges.

**Next:** TOOL-01 or DATA-01 V3: add a typed read-only adapter with provenance carried through the output and a mock KAIROS independent decision-gate fixture, without importing broker tools or relying on GUI state. Avoid modifying PR #12/#13 while open.
