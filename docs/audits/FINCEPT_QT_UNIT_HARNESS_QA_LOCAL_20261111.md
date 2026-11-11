# QA-LOCAL — native Qt unit suites and an exact reference for the C++ indicator engine (2026-11-11)

**Status: local runs on one Linux machine. Not CI, not a build of FinceptTerminal,
not a GUI test.** No original Fincept file is modified. Synthetic data only.

## What this adds

- `tools/fincept_audit/qt_unit_harness/CMakeLists.txt` builds Fincept's own Qt
  Test suites by including `fincept-qt/tests/CMakeLists.txt` **unmodified**. The
  full application configure needs seven Qt modules and several FetchContent
  downloads; these suites need only `Qt6::Core` and `Qt6::Test`.
- `tools/fincept_audit/indicator_reference_v1.py` computes 22 indicators (36
  values, current and previous bar) from their textbook definitions with exact
  `Fraction` arithmetic on a 120-bar integer fixture.
- `tools/fincept_audit/qt_unit_harness/tst_indicator_engine_reference.cpp` is a
  native Qt Test that rebuilds the same fixture and compares
  `fincept::algo::IndicatorEngine::compute` with those values within relative
  1e-9. A Python test keeps the embedded table identical to the generator.

## Result (Qt 6.8.3 gcc_64 from the official archive, GCC 13.3, Ubuntu 24.04)

| Suite | Result |
|---|---|
| `tst_result` (upstream) | 16 passed |
| `tst_broker_modify_fields` (upstream) | 15 passed |
| `tst_indicator_engine` (upstream) | 8 passed |
| `tst_indicator_engine_reference` (new) | 40 passed |
| `tst_order_validator` (upstream) | **does not compile** — see below |

The C++ engine agrees with the exact reference on all 36 values: SMA, EMA, WMA,
DEMA, TEMA, RSI, MACD (line, signal, histogram), Stochastic (%K, %D), CCI,
Williams %R, MFI, ROC, Aroon (up, down), ATR, Bollinger (upper, middle, lower,
width, %B), Keltner (upper, middle, lower), Donchian (upper, lower), OBV, CMF,
VWAP, windowed volume change, Ichimoku (tenkan, kijun, senkou A and B). The
test also shows the comparison can fail: moving one close by a cent breaks at
least 25 of the 36.

Conventions confirmed in the engine: EMA seeded with the SMA of the first
window; RSI and ATR with Wilder smoothing; Bollinger with the population
deviation; Keltner bands from an EMA of the true range (not the Wilder ATR the
standalone ATR indicator uses); VWAP cumulative over the supplied window.

Not covered: ADX and Supertrend, edge cases (flat ranges, zero volume, short
history), and everything outside `IndicatorEngine`.

## Finding: upstream `tst_order_validator` cannot be built as declared

`fincept-qt/tests/CMakeLists.txt` adds `tst_order_validator` with one extra
source, `src/trading/OrderValidator.cpp`, and says that file "includes only its
own header". At fork `main` `7716ee86` it also includes
`core/logging/Logger.h` and `storage/repositories/SettingsRepository.h`
(the settings-driven pre-trade risk gate), which pulls in `QSqlDatabase`. The
target links only `Qt6::Test` and `Qt6::Core`, so it fails at compile time
(`QSqlDatabase: No such file or directory`) and would need the settings
repository, the database layer and the logger to link.

This is reported, not fixed: the fix belongs in the order-validation code
(for example moving the settings persistence out of `OrderValidator.cpp`), and
that code is on the broker order path, which is outside the scope of this work.
The other suites are built by naming their targets.

## Reproduce

```bash
pip install aqtinstall && aqt install-qt linux desktop 6.8.3 linux_gcc_64 -O <qt>
cmake -S tools/fincept_audit/qt_unit_harness -B <build> -G Ninja \
      -DCMAKE_PREFIX_PATH=<qt>/6.8.3/gcc_64
cmake --build <build> --target tst_result tst_broker_modify_fields \
      tst_indicator_engine tst_indicator_engine_reference
QT_QPA_PLATFORM=offscreen ctest --test-dir <build> -E tst_order_validator --output-on-failure
python -m pytest -q tests/fincept_audit/test_indicator_reference_v1.py   # 6 passed, stdlib only
```
