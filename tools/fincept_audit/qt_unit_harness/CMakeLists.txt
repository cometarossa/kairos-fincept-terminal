# QA-LOCAL: build and run Fincept's own Qt Test suites without configuring the app.
#
# fincept-qt/tests/CMakeLists.txt is included UNMODIFIED, so the suite list, the
# per-target source lists and the compile settings are upstream's, not a copy.
# The full application configure needs seven Qt modules plus several
# FetchContent downloads; these unit suites need only Qt6::Core and Qt6::Test.
#
#   cmake -S tools/fincept_audit/qt_unit_harness -B <build> -G Ninja \
#         -DCMAKE_PREFIX_PATH=<Qt>/6.8.3/gcc_64
#   cmake --build <build>
#   QT_QPA_PLATFORM=offscreen ctest --test-dir <build> --output-on-failure
#
# This proves the listed units compile and pass against that Qt on this machine.
# It does not build FinceptTerminal, any screen or widget, and is not CI.
cmake_minimum_required(VERSION 3.27)
project(FinceptQtUnitHarness LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)             # same as fincept-qt/CMakeLists.txt
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

get_filename_component(FINCEPT_QT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../fincept-qt" ABSOLUTE)
if(NOT EXISTS "${FINCEPT_QT_DIR}/tests/CMakeLists.txt")
    message(FATAL_ERROR "fincept-qt/tests/CMakeLists.txt not found at ${FINCEPT_QT_DIR}")
endif()

# The application pins Qt with `6.8.3 EXACT` through _FINCEPT_QT_VER_ARGS and the
# test file reuses it. Keep the same pin unless the caller overrides it knowingly.
set(FINCEPT_HARNESS_QT_VERSION "6.8.3" CACHE STRING "Qt version to require (EXACT)")
set(_FINCEPT_QT_VER_ARGS ${FINCEPT_HARNESS_QT_VERSION} EXACT)
find_package(Qt6 ${_FINCEPT_QT_VER_ARGS} REQUIRED COMPONENTS Core Test)

enable_testing()
# The upstream file resolves sources and includes from PROJECT_SOURCE_DIR.
set(PROJECT_SOURCE_DIR "${FINCEPT_QT_DIR}")
add_subdirectory("${FINCEPT_QT_DIR}/tests" fincept_tests)

# KAIROS-side value-level reference suite for the native indicator engine. Same
# shape as upstream's tst_indicator_engine: one extra translation unit, Core + Test.
fincept_add_test(tst_indicator_engine_reference
    "${CMAKE_CURRENT_SOURCE_DIR}/tst_indicator_engine_reference.cpp"
    "${FINCEPT_QT_DIR}/src/algo_engine/IndicatorEngine.cpp")

# Isolated property-based temporal probes for known ADX/ Supertrend bugs.
fincept_add_test(tst_indicator_temporal_contracts
    "${CMAKE_CURRENT_SOURCE_DIR}/tst_indicator_temporal_contracts.cpp"
    "${FINCEPT_QT_DIR}/src/algo_engine/IndicatorEngine.cpp")
set_tests_properties(tst_indicator_temporal_contracts PROPERTIES TIMEOUT 30)
