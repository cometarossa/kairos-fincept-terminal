cmake_minimum_required(VERSION 3.27)
project(FinceptSupertrendExternalConventionAudit LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(Qt6 6.8.3 EXACT REQUIRED COMPONENTS Core)
get_filename_component(FINCEPT_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../fincept-qt/src" ABSOLUTE)
add_executable(supertrend_candidate_prefix_dump
    native_prefix_dump.cpp
    "${FINCEPT_SOURCE_DIR}/algo_engine/IndicatorEngine.cpp")
target_include_directories(supertrend_candidate_prefix_dump PRIVATE "${FINCEPT_SOURCE_DIR}")
target_link_libraries(supertrend_candidate_prefix_dump PRIVATE Qt6::Core)
