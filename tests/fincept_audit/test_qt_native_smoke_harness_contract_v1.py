"""Offline source-contract checks for the disposable native QtCore smoke harness.

These tests verify provenance and regression coverage; they are NOT a native
Qt compilation or a claim about GUI functionality.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tools" / "fincept_audit" / "qt_smoke_native_contract"


class NativeQtSmokeHarnessSourceContractTests(unittest.TestCase):
    def test_cmake_compiles_original_smoke_source_not_a_copy(self):
        cmake = (HARNESS / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn('set(SMOKE_SOURCE "${FINCEPT_QT_DIR}/src/app/ScreenSmokeTest.cpp")', cmake)
        self.assertIn('"${SMOKE_SOURCE}"', cmake)
        self.assertIn('find_package(Qt6 ${FINCEPT_HARNESS_QT_VERSION} EXACT REQUIRED COMPONENTS Core)', cmake)
        self.assertIn('target_link_libraries(fincept_smoke_native_contract PRIVATE Qt6::Core)', cmake)
        self.assertIn('add_test(NAME fincept_smoke_native_contract COMMAND fincept_smoke_native_contract)', cmake)
        self.assertTrue((ROOT / "fincept-qt/src/app/ScreenSmokeTest.cpp").is_file())

    def test_no_gui_or_broker_dependencies_in_stubs(self):
        for relative in (
            "stubs/app/DockScreenRouter.h",
            "stubs/auth/InactivityGuard.h",
            "stubs/core/logging/Logger.h",
        ):
            self.assertTrue((HARNESS / relative).is_file())
        router = (HARNESS / "stubs/app/DockScreenRouter.h").read_text(encoding="utf-8")
        self.assertIn("all_screen_ids()", router)
        self.assertIn("screen_widget(", router)
        self.assertIn("navigate(", router)
        native = (HARNESS / "test_smoke_native.cpp").read_text(encoding="utf-8")
        for forbidden in ("ExecuteMarketOrder", "QApplication", "QWebEngine", "IGDemoCanonicalAdapter"):
            self.assertNotIn(forbidden, router + native)

    def test_unconstructed_screen_is_a_bounded_failure(self):
        cmake = (HARNESS / "CMakeLists.txt").read_text(encoding="utf-8")
        source = (ROOT / "fincept-qt/src/app/ScreenSmokeTest.cpp").read_text(
            encoding="utf-8-sig")
        native = (HARNESS / "test_smoke_native.cpp").read_text(encoding="utf-8")
        self.assertIn("kConstructDeadlineMs = 8000", source)
        self.assertIn("set_tests_properties(fincept_smoke_native_contract", cmake)
        self.assertIn("TIMEOUT 30", cmake)
        self.assertIn("unbuilt.materialize_on_navigation = false", native)
        self.assertIn("run_screen_smoke_test(&unbuilt) == 1", native)
        self.assertIn("unbuilt.navigation_calls == 1", native)

    def test_runtime_assertions_cover_both_failure_and_success(self):
        source = (ROOT / "fincept-qt/src/app/ScreenSmokeTest.cpp").read_text(encoding="utf-8-sig")
        self.assertIn("if (ids.isEmpty())", source)
        self.assertIn("return 4;", source)
        native = (HARNESS / "test_smoke_native.cpp").read_text(encoding="utf-8")
        for expected in (
            "run_screen_smoke_test(nullptr) == 2",
            "run_screen_smoke_test(&locked) == 3",
            "run_screen_smoke_test(&empty) == 4",
            "run_screen_smoke_test(&populated) == 0",
            "locked.inventory_reads == 0 && locked.navigation_calls == 0",
            "empty.inventory_reads == 1 && empty.navigation_calls == 0",
            "populated.last_navigation_exclusive",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, native)


if __name__ == "__main__":
    unittest.main()
