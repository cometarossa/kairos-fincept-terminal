# Compile and execute Fincept's EXACT original ScreenSmokeTest.cpp against
# disposable QtCore-only stubs. This is a native C++ *logic contract*, not
# a GUI, ADS, WebEngine, showEvent or installed-app test.
cmake_minimum_required(VERSION 3.27)
project(FinceptQtScreenSmokeNativeContract LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Fincept app uses Qt 6.8.3. Change consciously if testing another version.
set(FINCEPT_HARNESS_QT_VERSION "6.8.3" CACHE STRING "Qt6 exact version")
find_package(Qt6 ${FINCEPT_HARNESS_QT_VERSION} EXACT REQUIRED COMPONENTS Core)

get_filename_component(FINCEPT_QT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../fincept-qt" ABSOLUTE)
set(SMOKE_SOURCE "${FINCEPT_QT_DIR}/src/app/ScreenSmokeTest.cpp")
if(NOT EXISTS "${SMOKE_SOURCE}")
    message(FATAL_ERROR "Original Fincept ScreenSmokeTest.cpp is missing")
endif()

add_executable(fincept_smoke_native_contract
    "${SMOKE_SOURCE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/test_smoke_native.cpp"
)
# The 3 stub headers intentionally shadow expensive app/runtime dependencies.
# ScreenSmokeTest.h itself is the unchanged original header.
target_include_directories(fincept_smoke_native_contract PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/stubs"
    "${FINCEPT_QT_DIR}/src"
)
target_link_libraries(fincept_smoke_native_contract PRIVATE Qt6::Core)

enable_testing()
add_test(NAME fincept_smoke_native_contract COMMAND fincept_smoke_native_contract)
