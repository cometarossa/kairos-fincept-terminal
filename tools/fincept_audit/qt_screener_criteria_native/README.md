# ScreenerCriteriaBuilder — native QA and fail-closed regression (2026-11-15)

**DRAFT / VERIFIED COMPONENT TESTS / NOT A FULL PRODUCT OR MERGED FIX.**

This is an isolated, synthetic-only Qt Widgets harness. The independent QA parent
[Fincept #52](https://github.com/cometarossa/kairos-fincept-terminal/pull/52) tested
the original unchanged Fincept source at fork `main`
`7716ee8613249fb44c4d14036c5bc16ed6f34e97`. This **child fix branch**
changes the original `ScreenerCriteriaBuilder.cpp`, retaining the same isolated
harness with stricter CTest assertions. The change must not merge ahead of its QA
parent without review/rebase.

## Exact source/test identity

| Input | Verified Git blob |
|---|---|
| Original `ScreenerCriteriaBuilder.cpp` | `0bd59d3911b32f3758de04e2b6b6b20eebd4be0c` |
| Fixed `ScreenerCriteriaBuilder.cpp` | `5b544c214919835685a61562273c97b4d1c5c451` |
| Original `ScreenerCriteriaBuilder.h` | `e9eb9c7eb1c268b0265f8ac22b7cb889964c1999` |
| Test harness `tst_original_screener_criteria.cpp` (fixed branch) | `e6d22c7f13e0fdcba6f9888f0e5b62584bd8054c` |
| Regression CMake `CMakeLists.txt` (fixed branch) | `e3000e7011a79fb43ce272c0409548c52acbb9e9` |

## Actual source-real native results

**Environment verified at execution:** ZimaBlade, transient `ubuntu:24.04` Docker
container, GNU C++ 13.3.0, CMake 3.28.3 and Ubuntu-packaged Qt 6.4.2
(Core, Gui, Widgets, Test, Sql). Code checkout mounted read-only and verified
with `git hash-object`. `QT_QPA_PLATFORM=offscreen`; no installed Fincept app.

1. **Original parent #52, exact QA HEAD `fb99831e6eb209c48ebc9dd642d00ca6b3a80846`:**
   native build successful; CTest **1/1 PASS** with **31/31 baseline checks PASS**.
   The separately run `--probe-defects` had **2 expected assertion failures**
   out of 3 checks and returned exit 1:
   - `1e308T` was accepted as a numeric filter despite a nonfinite scaled value.
   - An emptied replacement catalog still allowed building a stale query.
   Baseline CTest log SHA-256:
   `f6180778730d3edc1e9007e25b70766a2a63e8abcb7e79d6fc909ecfb206cdfb`.
   Original strict-probe log SHA-256:
   `9347fe571a571f1c8757df718170c87d5378481356dff1141e9c917a053e50a7`.

2. **Fixed child exact code HEAD `f4b6f11a827592b2185dc6942627542be7456aab`:**
   native build successful; CTest **2/2 PASS** (baseline **31/31**, registered
   fail-closed suite **7/7**, zero failures).
   Fixed CTest log SHA-256:
   `0a3cc43f7105106aa86862a12a88f503cce28b053cde5a60c17a08f90870ad00`.
   The child branch's later **documentation-only** commits do not change the
   verified source/harness blob identities above.

### Independent macOS Qt 6.8.3 / AppleClang 16 confirmation

**VERIFIED on 2026-11-15:** separate scratch checkout of this child PR
at exact Git HEAD `4b46727991af501ed9e4b461873ddfcf6ca55136`
on the connected iMac (macOS 14.5, x86_64, AppleClang 16.0.0),
using the open-source Qt **6.8.3** `clang_64` `qtbase` archive
installed into a disposable `/private/tmp` directory by aqtinstall.
The original Fincept application, profile and settings were **not opened**.

The checkout was clean; independently verified unmodified test/source blobs:
fixed C++ `5b544c214919835685a61562273c97b4d1c5c451`,
test `e6d22c7f13e0fdcba6f9888f0e5b62584bd8054c`,
CMake `e3000e7011a79fb43ce272c0409548c52acbb9e9`.
Qt's `qmake -query QT_VERSION` reported `6.8.3`.

**Native CMake build and link PASS; CTest 2/2 PASS** with
**31/31 baseline + 7/7 strict checks = 38/38 PASS**, zero failures;
`QT_QPA_PLATFORM=offscreen`. Mac CTest log SHA-256:
`c6f6e25264c805e47ec895e7c9902ede690d7be140f87f3fb7f26eea84afa5c5`.
A harmless missing-font alias warning was printed by Qt. This is a
**second independent platform/compiler/Qt version confirmation** of the
*component*, not of ScreenerScreen or Fincept as a product.

An intermediate attempt to link the official Qt 6.8.3 Linux binaries
inside a minimal Ubuntu 24.04 container was blocked **at linker/ABI dependency
resolution** (including missing `libicui18n.so.73`); C++ compilation itself
succeeded. **No Linux Qt 6.8.3 CTest PASS is claimed.** The valid Linux
test evidence remains Qt 6.4.2/GCC 13.3, and the valid Qt 6.8.3 evidence is
macOS/AppleClang.

## What the fix does

- Validates the **scaled** `K/M/B/T` number is finite *after* multiplication
  before assigning the output; this rejects the reproduced `1e308T` case.
- Refuses to construct a Screener query when the field catalog is absent, returning
  a user-facing error **without touching the prior output query**.
- Clears stale criterion rows when a replacement catalog has no usable fields.
- Registers the strict fail-closed probes as a **second CTest** only in the
  fixed branch, without hiding a known-red original test.

## Reproduce against a verified isolated checkout

```sh
cmake -S tools/fincept_audit/qt_screener_criteria_native \
  -B /tmp/fincept-criteria-native-build \
  -DFINCEPT_SOURCE_DIR="$PWD/fincept-qt/src" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/fincept-criteria-native-build --parallel 2
QT_QPA_PLATFORM=offscreen \
  ctest --test-dir /tmp/fincept-criteria-native-build -V --output-on-failure
```

## Boundaries

**Not verified:** complete ScreenerScreen GUI, Yahoo/provider errors,
saved screens and watchlists, installed
Fincept profile/PIN, network data, authenticated KAIROS tool API, scientific edge or
trading. No market provider, account, real-price dataset, network order, broker,
IG, application settings, privileged runner, scientific holdout, or installed
Fincept process was touched by these tests. Fincept GitHub-native CI is still
**NOT VERIFIED**. This is source-real **component** evidence, not product release
authority. Keep the fix PR **DRAFT** pending independent review.
