# Verified-source execution checkpoint — 2026-11-11

## Concrete defect and correction

The technical probe SHA-256 checked source bytes but then used Python's source
loader. A timestamp-based bytecode cache with matching source size and timestamp
could execute different code. A fresh load could also create __pycache__ in the
original source directory, despite the probe's read-only intent.

Execute compile(data, path, 'exec') from the exact bytes already hashed, in the
existing module namespace. Do not reload the path, accept cached code, refresh
source pins or modify any original Fincept indicator script. This removes cache
reads/writes by this loader, not all possible filesystem effects of imports or
transitive dependencies; it is not an OS security sandbox.

## Evidence and dependency

Parent: draft #29, head 28325bf250a4b2008d9841490e1f5b3c5f6b4cf2, stacked on #26.
Before this patch the full parent suite passed 19/19, including all five original
indicator families (82 output columns on 180 synthetic bars). This closes its
previous local ta-unavailable verification gap for that exact head only.

Two regression tests added:
- Build a timestamp pyc containing a harmless 'cached' marker, replace its source
  with same-length verified 'source' bytes and preserve the timestamp. The
  original loader incorrectly returns 'cached'; the corrected loader returns
  'source' and leaves existing cache bytes untouched.
- Load a fresh verified module and assert no cache file/directory is created.

Red: 2 failures in 12 technical tests. Green: **21/21** full local tests PASS.
Isolated composition with #28 head 5f7aeb5cf8858829e9167720dd3035d24e9c2a6f's
Portfolio changes and #30 head 6eb3e0fe1a1428a51b76bd640de40025284a8b28's JSON
source/tests: **61/61 PASS**. This is an unmerged local test composition, not a
shared branch or installed binary. Diff --check PASS.

Reproduce: PYTHONPATH=<ta-install-dir>:. python -m unittest discover
-s tests/fincept_audit -p 'test_*.py' -q
Environment: Python 3.12.14, numpy 2.3.5, pandas 2.2.3, isolated ta 0.11.0.

## Boundaries and next work

Native Qt build/GUI, hosted CI and independent review remain NOT_VERIFIED.
Scientific/economic validity is NOT_EVALUATED. No broker, external provider,
paid API, deployment, user profile, workflow or runner change. Original source
hashes, routes, widgets and layouts retained. Rollback: revert this isolated
probe/test/doc commit; no migration. Keep DRAFT pending review.

Graphify repository discovery was attempted: no authorized repositories in the
current workspace. Direct GitHub and local source/test tools remain usable.
Next development increment: review synthetic backtest/bridge coverage against
the specialist roadmap; native acceptance remains a separate integration gate.
