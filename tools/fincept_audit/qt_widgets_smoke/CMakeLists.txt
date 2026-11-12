cmake_minimum_required(VERSION 3.27)
project(FinceptOriginalWidgetsSmoke LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 6.8.3 EXACT REQUIRED COMPONENTS Widgets Test)
get_filename_component(FINCEPT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../fincept-qt" ABSOLUTE)
add_executable(original_widgets_smoke
    "${FINCEPT_DIR}/src/ui/widgets/StatusBadge.cpp"
    "${FINCEPT_DIR}/src/ui/widgets/SearchBar.cpp"
    "${FINCEPT_DIR}/src/ui/theme/ThemeManager.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/test_original_widgets.cpp"
)
target_include_directories(original_widgets_smoke PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/stubs"
    "${FINCEPT_DIR}/src")
target_link_libraries(original_widgets_smoke PRIVATE Qt6::Widgets Qt6::Test)
enable_testing()
add_test(NAME original_widgets_smoke COMMAND original_widgets_smoke)
set_tests_properties(original_widgets_smoke PROPERTIES
    ENVIRONMENT "QT_QPA_PLATFORM=offscreen"
    TIMEOUT 30)
