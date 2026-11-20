# Fincept Qt five-platform CI infrastructure recovery — 2026-11-20

Scope: isolated repair to the manually dispatched original \`build-cpp.yml\`
workflow, not the Fincept application, brokers, data services or KAIROS authority.

## Evidence and diagnosis

- On original Fincept draft [#57](https://github.com/cometarossa/kairos-fincept-terminal/pull/57),
  [GitHub Actions run #44819157845](https://github.com/cometarossa/kairos-fincept-terminal/actions/runs/44819157845)
  completed **FAILURE** on exact SHA \`01086c6d217af86f2449927f53bc81fd4832ee28\`.
  Separate architecture-ratchet [#44819153675](https://github.com/cometarossa/kairos-fincept-terminal/actions/runs/44819153675)
  completed **SUCCESS** at the same head.
- Linux x64 and macOS arm64 configured, built and ran headless self-tests, then
  packaging returned exit code 127 at \`bash .github/scripts/sync_scripts.sh\`.
  The script exists in the **repository root**, but packaging steps run from
  \`fincept-qt/\`. The same wrong path also occurs in Windows packaging and
  macOS Universal assembly, even though those steps were not reached.
- Both Windows jobs stopped **before CMake**: vcpkg supplied static
  \`libzs.lib\`, but the workflow searched \`z*.lib\` and therefore did not
  create the expected \`zlib.lib\` alias.
- macOS x64 compiled its C++ sources, then its final link attempted to use
  OpenSSL \`arm64\` libraries from the \`macos-15\` ARM runner for an
  \`x86_64\` executable. The linker rejected both OpenSSL libraries.

## Changes

1. Route the x64 build matrix to GitHub's standard \`macos-15-intel\` runner,
   preserving the existing Qt version and x64 CMake target. Enable headless
   self-tests now that macOS x64 is a **native** target.
2. Allow only the known static vcpkg archive alternatives \`libzs.lib\` and
   \`zs.lib\` when \`zlib.lib\` is absent. Preserve failure if neither exists.
3. Use \`$GITHUB_WORKSPACE\` to locate the repository-root packaging copy script
   in all four existing call sites. The same absolute-path convention is
   already used in \`release.yml\`.


## 2026-11-21 — Universal assembly checkout regression

The macOS Universal job runs on **another** runner and does not inherit
the five build jobs' checked-out files. Before this follow-up it attempted
to invoke the repository-root packaging script without first checking out
the repository. Even a five-platform compile PASS would have failed here.
A read-only `actions/checkout@v4` (with `persist-credentials: false`)
now precedes artifact downloads. The new offline regression reproduced
the missing checkout (RED), then passed (GREEN).

The already dispatched combined QA run
[44834073612](https://github.com/cometarossa/kairos-fincept-terminal/actions/runs/44834073612)
uses the **earlier** commit of #67 and does not contain this fix;
its five build legs remain useful evidence, but it cannot certify final
Universal assembly. New exact-head combined CI is still needed.


## Exact-source offline regression

\`python3 -m unittest discover -s tests/fincept_original -p 'test_build_cpp_workflow_infrastructure.py' -v\`

- **Before patch:** 5 executed, 4 FAIL (Intel runner, workspace script
  paths, synthetic real packaging copy, actual extracted Windows step against
  \`libzs.lib\`); 1 PASS (missing zlib aborts).
- **After patch:** **5/5 PASS** on the disposable iMac checkout. Tests execute
  the actual extracted Windows shell block with temporary vcpkg fixtures and
  the unchanged actual \`sync_scripts.sh\` from a nested \`fincept-qt\`
  directory; no external service or broker is used.
- Python YAML parser of modified workflow: **PASS**; \`git diff --check\`:
  **PASS**. \`actionlint\` was not installed; no actionlint PASS claimed.

## Open gates / integration order

- These are **offline infrastructure checks**, not a five-platform rebuild.
  Full Windows configure/link, macOS Intel link, Linux/macOS packages and
  Universal bundle **remain unverified on the patched workflow**.
- This repair is based independently on Fincept \`main\` at
  \`7716ee8613249fb44c4d14036c5bc16ed6f34e97\`. Original main still
  has the historical QGeoView shallow-clone defect; a full manual Actions
  run cannot be certified on this independent branch until paired with the
  separately reviewed #57 change or after #57 is integrated.
- The branch must remain **DRAFT** until exact-head CI and independent review.
  No auto-merge, release, deploy or widening of GitHub Actions permissions.
  No GitHub run is automatically dispatched by this change.
- Fincept #55 async-lifetime fix remains open and separate. Research-only
  KAIROS, no IG login, no DEMO/LIVE broker access or execution authority.
