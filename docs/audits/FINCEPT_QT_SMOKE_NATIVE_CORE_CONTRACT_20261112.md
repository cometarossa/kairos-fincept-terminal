# Fincept — native QtCore smoke logic harness (2026-11-12)

**Branch:** `test/qt-screen-smoke-native-core-contract-20261112`, based on
Fincept DRAFT #39 at `7c2e29d2795dcc2a979aca96720a0cc54fe403f9`.
No Fincept running process or installed profile is touched.

## Goal and scope

A small, disposable **native QtCore compilation/test harness** for the *exact*
`fincept-qt/src/app/ScreenSmokeTest.cpp`. The separate test entrypoint builds
with real `Qt6::Core` but replaces router, logger and lock-service dependencies
using header stubs in the test tree. It will exercise the real C++ branch outcomes
for: null router (2), locked PIN flag (3), empty screen registry (4), and one
successfully constructed fake screen (0). Tests also verify no navigation
happens with the lock or an empty registry and that positive navigation is
exclusive.

**Important limitations:** all routing and authentication inputs are mocks.
This is NOT a real `DockScreenRouter`, `QApplication`, widget construction,
screen `showEvent`, FinceptTerminal build, GUI smoke, permission test, or broker
integration. A successful run does not establish any working GUI screen.

## Reproduce when Qt 6.8.3 + CMake are available

From the root of a checkout containing this PR and DRAFT #39:

```sh
cmake -S tools/fincept_audit/qt_smoke_native_contract -B /tmp/fincept-smoke-native -DCMAKE_PREFIX_PATH=/path/to/Qt/6.8.3/gcc_64
cmake --build /tmp/fincept-smoke-native
ctest --test-dir /tmp/fincept-smoke-native --output-on-failure
python3 -m unittest discover -s tests/fincept_audit -p 'test_qt_native_smoke_harness_contract_v1.py' -v
```

Use an isolated checkout/build directory and a verified Qt toolchain. A
compiler error or missing Qt is **NOT VERIFIED**, never a pass. No app install,
account access, PIN clearing, or GitHub Actions enablement is required.

## Current evidence

- **3/3 Python source-contract tests PASS on iMac (2026-11-12)** using an isolated file tree populated from the GitHub branch; no install. Git blob hashes checked for CMake (`c22c6354e8fa8664c0935a49099f1f265c72be52`), source test (`a82a4366c4474aeae78dcd7fce6f512dc214cb3b`) and original Qt smoke C++ (`8eaa31502b00aea5fc7585ecdc2c09eb4a56e06f`). These are **not C++ runtime tests**.
- Original Fincept DRAFT #39 separately has **7/7 source tests PASS** at exact
  `7c2e29d2` on iMac.
- As of creation: **native QtCore build NOT RUN** because no authorized
  Qt6 toolchain with repository checkout has yet been verified.
- DRAFT #36 provides a separate Qt unit harness for indicators on Ubuntu; its
  earlier results do not certify this new test or the GUI.
- No broker mutation, IG login, order, API key access, service restart, or
  scientific admission.
