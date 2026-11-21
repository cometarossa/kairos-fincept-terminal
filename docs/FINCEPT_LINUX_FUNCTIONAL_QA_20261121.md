# Fincept Linux x64 — prioritized native QA (2026-11-21)

Operator priority: **Linux only**. Windows/macOS platform gates are not acceptance criteria for this scope.

## Actual previous evidence
- Combined pre-fix build: https://github.com/cometarossa/kairos-fincept-terminal/actions/runs/44834073612 at SHA d3106363. Linux x64 **configured, compiled, and passed the original Qt headless self-tests**; AppImage packaging failed solely when generating a fallback icon: `ModuleNotFoundError: No module named PIL`. Combined CI is **not** a Linux release PASS.
- Previously (individual #57), a Linux packaging step also failed because the scripts copy command was resolved from `fincept-qt/` instead of workspace root.

## Linux-only corrections
- Fix QGeoView's historical CMake git SHA fetch by disabling shallow clone; keep original exact SHA.
- Make Linux AppImage script copy use `$GITHUB_WORKSPACE` so it works from `fincept-qt/`.
- Replace Pillow icon generation with deterministic standard-library PNG, using the original PNG when it exists.
- Add an opt-in **Linux x64 dedicated** GitHub Actions workflow with exactly one Ubuntu 22.04 matrix leg, copied from the original workflow's Linux job; it runs the original build, original `--selftest-*` flags, and AppImage packaging. Neither Windows nor macOS is scheduled.
- Add regression tests validating exact pin, native copy script behavior, PNG CRC and decompression, Linux-only matrix.

## Limits / next gate
The local Python/shell tests do **not** replace a full Linux native build. Promote only when the new dedicated Linux CI reaches SUCCESS and the built binary is inspected, ideally with a Debian 13 GUI/offscreen runtime smoke. The AppImage may still fail for an unrelated packaging dependency; diagnose separately. No IG, KAIROS broker, trading or cloud LLM API calls.
