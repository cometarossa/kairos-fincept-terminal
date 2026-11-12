# QA-LOCAL — native Qt unit suites and an exact reference for the C++ indicator engine (2026-11-11)

**Status: local runs on one Linux machine. Not CI, not a build of FinceptTerminal,
not a GUI test.** No original Fincept file is modified. Synthetic data only.

## What this adds

- `tools/fincept_audit/qt_unit_harness/CMakeLists.txt` builds Fincept's own Qt
  Test suites by including `fincept-qt/tests/CMakeLists.txt` **unmodified**. The
  full application configure needs seven Qt modules and several FetchContent
  downloads; these suites need only `Qt6::Core` and `Qt6::Test`.
- `tools/fincept_audit/indicator_reference_v1.py` computes 24 indicators (40
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
| `tst_indicator_engine_reference` (new) | 44 passed |
| `tst_order_validator` (upstream) | **does not compile** — see below |

The C++ engine agrees with the exact reference on 37 of the 40 rows, current
and previous bar (ADX +DI/−DI agree on the current bar only, Supertrend not at
all — see the defects below): SMA, EMA, WMA,
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

ADX's value matches the reference exactly. Two defects were found and are
**pinned, not fixed**, in the reference suite (rows marked `current_only` /
`diverges`, which fail once the engine is fixed):

- **ADX `previous.plus_di` / `previous.minus_di` repeat the current bar's value.**
  `compute_adx` writes `pdi_curr`/`mdi_curr` into both `current` and `previous`.
  Any condition that reads the prior +DI/−DI (for example a DI crossover) sees no
  change and can never fire.
- **Supertrend ratchets the wrong band.** The engine lets the final lower band
  rise only when the previous close was above the *upper* band (and the upper band
  fall only when it was below the *lower* band). The textbook rule compares with
  the band itself. On the fixture the long-side line falls on 66 of 110 bars,
  where by definition it never may; the current value is 104.71 against 105.84.
  The direction also flips on the current bands instead of the previous ones.

A separate draft PR proposes the fix. Because `IndicatorEngine` feeds the
algo-trading condition evaluator, fixing it changes signals of any strategy that
uses these two indicators; that is an owner decision.

Not covered: edge cases (flat ranges, zero volume, short history), and everything
outside `IndicatorEngine`.

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
python -m pytest -q tests/fincept_audit/test_indicator_reference_v1.py   # 8 passed, stdlib only
```
