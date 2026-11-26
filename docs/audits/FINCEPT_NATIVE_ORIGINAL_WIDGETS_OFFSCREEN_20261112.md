# Fincept — native original QWidget offscreen smoke (2026-11-12)

**Scope:** native compile and widget-behaviour verification against unchanged original Fincept source. It is **not** a full application/52-screen, ADS router, dashboard, integrated KAIROS, profile, PIN, or broker verification.

## Source and isolation

- Fork baseline: `main` at `7716ee8613249fb44c4d14036c5bc16ed6f34e97`.
- Build includes original `fincept-qt/src/ui/widgets/StatusBadge.cpp` (Git blob `bc5a21c7c406057c11fa4c1c0e324e74da7993a8`), `SearchBar.cpp` (`37eb60b9a856e21e51c061a93e1da15bdc969cfd`), and `ThemeManager.cpp` (`292c3ef8765284bfdfe2d038303ebb66d122250b`) via CMake directly, with **Qt6::Widgets + Qt6::Test** and automatic moc.
- The only stub is the *logger header* (prevents log output/file and other app dependencies). **Widgets and ThemeManager are not mocked**, are not edited, and no broker or network is loaded.
- Isolated cache/worktree on iMac with official Qt **6.8.3 qtbase clang_64**, CMake 4.0.1, AppleClang 16, `QT_QPA_PLATFORM=offscreen`. Fincept installed executable, user profile, PIN, running VM, IG/broker, existing services and credentials were not touched.

## Verified local test, on exact source blobs

- Native CMake configure/compile/link: **PASS**, including Qt meta-object compilation for original QObject widgets.
- **CTest 1/1 PASS; 16/16 native checks PASS**: default/connected/disconnected/loading status badge labels, token-derived colors, custom badge survival of language-change events, live QLineEdit child, input size, forwarding text, `text_changed` signal, Return-key `search_submitted` signal, placeholder on language change, clearing the search and its emitted change.
- **3/3 Python source/provenance contract tests PASS**. The test computes Git blob IDs to pin each untouched original source and verifies native CMake/offscreen wiring and behavioural assertions.
- **Negative control EXPECTED FAIL**: in a disposable copy, removing only the original `returnPressed → search_submitted` connection from `SearchBar.cpp` caused CTest **0/1 FAIL**, on `FAIL Return submits query`. The negative-control script explicitly checked this failure and cleaned its temporary directory.

## Reproduction

From a branch checkout containing this harness and unmodified Fincept sources, with a Qt6.8.3 clang_64 prefix for macOS:

```sh
cmake -S tools/fincept_audit/qt_widgets_smoke -B /tmp/fincept-original-widgets-build \
  -DCMAKE_PREFIX_PATH=/path/to/Qt/6.8.3/macos -DCMAKE_BUILD_TYPE=Debug
cmake --build /tmp/fincept-original-widgets-build --parallel 2
ctest --test-dir /tmp/fincept-original-widgets-build --output-on-failure -V
python3 -m unittest discover -s tests/fincept_audit \
  -p test_original_widgets_offscreen_contract_v1.py -v
```

CTest sets `QT_QPA_PLATFORM=offscreen` for this standalone binary. The intended test does not log in to Fincept or access a user account. Keep all compiled objects and SDKs outside the installed app path.

## Interpretation

**VERIFIED**: two original Qt widget classes and the original theme implementation compile and exhibit the tested labels, style tokens, i18n callbacks, search entry and signals in an isolated native QtWidgets process; the test can catch a broken search submission.

**NOT VERIFIED**: actual full terminal GUI, screen factories, 35 dashboard widgets, layout presets, KAIROS hybrid composition, saved profiles, real authentication, or market/trading performance. The tested 2 widgets are a small but genuine slice of the original components, not a proxy for all 52 screens. Fork Actions CI not run; all evidence is local. This PR is DRAFT, non-authoritative and must not be merged without review and applicable gates.
