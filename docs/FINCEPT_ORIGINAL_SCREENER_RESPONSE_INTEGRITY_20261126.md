# Original Screener response integrity — 26 November 2026

Status: source candidate, not deployed. Base Fincept main `6cc33eaeac13eb37e6162bf715e1dd9542f3c73d`, original Python backend blob `87e0f48f1af7e6e3a54c4338895bcbb99561734c`. Separate from the native Qt criteria stack #51–53. Preserve the original ScreenerService and provider request logic. No new MCP tool, provider session, or broker authority.

## Reproduced defects and correction

Original scratch regression (Mac PID70685): 8/12 passed, 4 expected failures: duplicate quote symbols, empty fundamentals, unrelated ticker records, and heterogeneous quote times without warning. Candidate refuses malformed result envelopes and quote lists, duplicate quote identities; discards invalid/unrequested/duplicate fundamentals responses and discloses missing matched coverage. Valid quote timestamps must be positive integer seconds not later than local collection time, and delay values nonnegative integer minutes; invalid values become null with explicit warnings. `as_of` is still the latest valid reported quote time, not proof of simultaneous or fresh market observations. Existing pagination, filter catalogue (76 fields, 22 predefined screens), numerical values and request paths are unchanged for ordinary valid inputs. Native Qt parser already consumes the warnings field. Qt runtime behavior, true Yahoo schema compatibility, market freshness, fundamental publication times and economic merit remain unverified. Missing values are not a zero or a trade signal.

## Exact tested candidate

- Backend blob `0f66b5da2ef05ff972ef43d78af85f052edbf27f`, tests blob `31313d144c0e15561b801217649636c0779c88db`, unchanged JSON helper blob `5da097ee5e377be786f4c7f3c7b1390074d24233`.
- Mac PID74861: 23 tests and 34 subtests passed. ZimaBlade PID2658253: 23 tests passed, exit 0, same exact source/test/helper blobs, Python 3.12.13, nonroot, network none, RO source and root, scratch only. Synthetic transport only; no external Yahoo requests or credentials.
- Added the tests to the existing isolated Linux F2 AppImage QA step; no extra workflow job or runner. Actual CI and independent review pending. No new deployment or service modification.

## Next

Inspect the original MCP registry and bounded read-only service path; prefer a narrow versioned screening interface reusing the original backend rather than a second screener or arbitrary Python dispatch. Admit only after provenance, bounded provider budget, actual original Linux package, cross-process KAIROS client and fail-closed tests. No scientific or execution authority, no IG calls. Keep #632 CI recovery separate. Remaining malformed numeric/metadata edge cases and actual GUI/provider compatibility require review; the present change does not certify the full feature.
