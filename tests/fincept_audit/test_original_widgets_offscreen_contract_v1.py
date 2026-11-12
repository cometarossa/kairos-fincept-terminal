"""Source/provenance checks for the original Fincept QWidget offscreen smoke.

These tests are *not* native Qt runtime or GUI-wide evidence.
"""
from pathlib import Path
import hashlib
import unittest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tools/fincept_audit/qt_widgets_smoke"
EXPECTED_ORIGINAL_BLOBS = {
    "fincept-qt/src/ui/widgets/StatusBadge.cpp": "bc5a21c7c406057c11fa4c1c0e324e74da7993a8",
    "fincept-qt/src/ui/widgets/SearchBar.cpp": "37eb60b9a856e21e51c061a93e1da15bdc969cfd",
    "fincept-qt/src/ui/theme/ThemeManager.cpp": "292c3ef8765284bfdfe2d038303ebb66d122250b",
}


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()


class NativeOriginalWidgetContract(unittest.TestCase):
    def test_exact_original_cpp_objects(self):
        for filename, expected in EXPECTED_ORIGINAL_BLOBS.items():
            with self.subTest(path=filename):
                original = ROOT / filename
                self.assertTrue(original.is_file())
                self.assertEqual(git_blob_sha(original.read_bytes()), expected)

    def test_cmake_builds_unmodified_originals_and_is_offscreen(self):
        cmake = (HARNESS / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("find_package(Qt6 6.8.3 EXACT REQUIRED COMPONENTS Widgets Test)", cmake)
        for filename in ("StatusBadge.cpp", "SearchBar.cpp", "ThemeManager.cpp"):
            self.assertIn(filename, cmake)
        self.assertIn("Qt6::Widgets Qt6::Test", cmake)
        self.assertIn("CMAKE_AUTOMOC ON", cmake)
        self.assertIn("QT_QPA_PLATFORM=offscreen", cmake)
        self.assertIn("TIMEOUT 30", cmake)

    def test_runtime_assertions_cover_real_widget_interactions(self):
        cpp = (HARNESS / "test_original_widgets.cpp").read_text(encoding="utf-8")
        for item in (
            "QApplication app(argc, argv)",
            "StatusBadge badge",
            "SearchBar search",
            "QSignalSpy submitted",
            "QTest::keyClick(input, Qt::Key_Return)",
            "search.clear()",
            "QCoreApplication::sendEvent(&badge, &lang)",
            "QCoreApplication::sendEvent(&search, &lang)",
            "Return submits query",
        ):
            with self.subTest(item=item):
                self.assertIn(item, cpp)
        self.assertNotIn("ExecuteMarketOrder", cpp)
        self.assertNotIn("QWebEngine", cpp)
        self.assertNotIn("QNetworkAccessManager", cpp)


if __name__ == "__main__":
    unittest.main()
