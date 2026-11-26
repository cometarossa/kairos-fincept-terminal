cmake_minimum_required(VERSION 3.21)
project(FinceptOriginalScreenerCriteriaQA LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 6.4 REQUIRED COMPONENTS Core Gui Widgets Test Sql)
if(NOT DEFINED FINCEPT_SOURCE_DIR)
  message(FATAL_ERROR "Set FINCEPT_SOURCE_DIR to the unmodified, SHA-verified original fincept-qt/src tree")
endif()
add_executable(tst_original_screener_criteria
  tst_original_screener_criteria.cpp
  "${FINCEPT_SOURCE_DIR}/screens/screener/ScreenerCriteriaBuilder.cpp"
  "${FINCEPT_SOURCE_DIR}/screens/screener/ScreenerCriteriaBuilder.h"
)
target_include_directories(tst_original_screener_criteria PRIVATE "${FINCEPT_SOURCE_DIR}")
target_link_libraries(tst_original_screener_criteria PRIVATE
  Qt6::Core Qt6::Gui Qt6::Widgets Qt6::Test Qt6::Sql
)
enable_testing()
add_test(NAME screener_criteria_baseline COMMAND tst_original_screener_criteria)
set_tests_properties(screener_criteria_baseline PROPERTIES
  ENVIRONMENT "QT_QPA_PLATFORM=offscreen" TIMEOUT 40
)
# The separate --probe-defects mode intentionally checks suspected source defects.
# Do NOT mark it passing before running against the exact original source.
