# Fincept CMake QGeoView historical SHA: reliable FetchContent checkout

**2026-11-16. Scope: source dependency acquisition only, independent of KAIROS/IG.**

During the full original Fincept Terminal 4.5.1 CMake configure on a disposable
Debian 13 QA container (Qt **6.8.2**, GCC 14, CMake 3.31), `FetchContent`
successfully cloned the public QGeoView repository in shallow mode, but failed
to check out the project's pinned **historical commit**
`4b2c52c80940e1073c259ded1a57df83036ba1c9`. The source declaration
used `GIT_TAG <raw SHA>` **and** `GIT_SHALLOW TRUE`, which doesn't guarantee
that an older commit is present when the upstream default branch has advanced.

A separate exact-SHA fetch (`git fetch origin <pinned SHA> --depth=1`)
succeeded. Reconfiguring the original project with an explicit verified
`FETCHCONTENT_SOURCE_DIR_QGEOVIEW` override let CMake proceed. After adding
the real Qt XKB and private-header packages to the disposable container, the
**full original CMake configure and generate completed with exit code 0**
for Qt 6.8.2 MINOR mode and generated the complete `FinceptTerminal`
Ninja build graph (783 actions). This validates the diagnosis, but the
source-directory override is a workaround: it bypasses CMake's own pin
verification.

## Source fix and independent, network-free regression

Change only QGeoView's `FetchContent_Declare` from `GIT_SHALLOW TRUE` to
`GIT_SHALLOW FALSE`; preserve the exact full SHA, repository URL, existing
patch command, Qt pinning, and all downstream compile flags.

`tests/fincept_original/test_qgeoview_historical_sha_pin.py`:
- asserts the original CMake declaration preserves the exact upstream URL,
  historical SHA, patch script, and full-history clone requirement;
- constructs an artificial two-commit Git repository and a local `file://`
  bare mirror, demonstrating that a depth-1 clone lacks the earlier pinned
  commit while an ordinary full clone can check it out;
- runs entirely offline, no CMake download, Qt, API or broker required.

**RED → GREEN on the exact source:** before the CMake edit,
`test_cmake_uses_full_history_for_pinned_qgeoview` **failed**, while the
independent Git-history repro passed; after the edit, **2/2 PASS**.

## Explicit limits

The synthetic local Git mirror proves the underlying Git history behavior,
not that a future GitHub outage or upstream history rewrite cannot occur.
Genuine Qt 6.8.3 release-builder compatibility and full Fincept executable
link/run remain distinct gates. Qwen4-Max reviewed the minimal design **in
English** via an interactive subscription; it did not inspect this PR's
exact code or sign off the patch.

No trading, provider/IG account, credentials, GitHub Actions permissions,
runtime services, execution authority or deployment was changed.

## 2026-11-16 — Fresh live GitHub FetchContent verification (follow-up)

**Real source-acquisition smoke PASS on the Intel iMac with CMake 4.0.1.**
The new `tests/fincept_original/test_qgeoview_fetchcontent_integration.py`
extracts the **unchanged real QGeoView `FetchContent_Declare` block** from
`fincept-qt/CMakeLists.txt`, copies the unchanged original CMake AGL patch
script into a temporary read-only-purpose harness, then requests a **fresh
real GitHub clone** via `FetchContent_Populate(QGeoView)`. No
`FETCHCONTENT_SOURCE_DIR_QGEOVIEW` override is used, and Git verification
remains enabled.

The isolated harness asserts:
- actual Git `HEAD` is exactly `4b2c52c80940e1073c259ded1a57df83036ba1c9`;
- the original patch phase has a CMake-generated stamp, and the fetched
  QGeoView source contains no residual `-framework AGL`;
- fresh CMake configure and generate both exit successfully;
- the result contains the verified SHA marker.

The first integration test revealed only a **harness assertion error**:
CMake suppresses the nested successful FetchContent patch console log,
so looking for the patch's console message falsely failed even though
checkout and generation succeeded. Replacing that assertion with the
real CMake patch stamp yielded a **1/1 PASS** on a fresh temp directory.
The pre-existing independent offline Git-history checks remain **2/2 PASS**.

Run this opt-in network validation via:

```bash
FINCEPT_QGEOVIEW_NETWORK_FETCH_REQUIRED=1 python3 -m unittest \
  discover -s tests/fincept_original \
  -p 'test_qgeoview_fetchcontent_integration.py' -v
```

Without that environment switch, the network test **SKIPS explicitly**.
It never contacts any market, IG/broker or production service, and creates
only temporary QA files. This closes **fresh real GitHub fetch/pin/patch
verification for QGeoView with CMake 4.0.1**, not the broader Qt GUI/full
Fincept compile/link/runtime gate. A separate containerized full-project
CMake run with this PR's changed CMake has **not yet been performed**.
