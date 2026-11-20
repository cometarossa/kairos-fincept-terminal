"""Opt-in real CMake FetchContent checkout of original pinned QGeoView.

Default run: SKIP, because it requires network access to GitHub. This is a
standalone source-acquisition check, not a Qt/GUI build or broker tool.
Execute with FINCEPT_QGEOVIEW_NETWORK_FETCH_REQUIRED=1 and a configured Git
client/CMake. No credentials, external trading APIs, or remote mutations.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
CMAKE_SOURCE = ROOT / "fincept-qt" / "CMakeLists.txt"
PATCH_SOURCE = ROOT / "fincept-qt" / "cmake/patches/qgeoview_remove_agl.cmake"
SHA = "4b2c52c80940e1073c259ded1a57df83036ba1c9"
FLAG = "FINCEPT_QGEOVIEW_NETWORK_FETCH_REQUIRED"


class QGeoViewActualFetchContentTest(unittest.TestCase):
    def test_fresh_original_cmake_fetch_of_exact_sha_and_patch(self):
        if os.getenv(FLAG) != "1":
            self.skipTest("Real GitHub fetch is opt-in, network disabled by default")
        cmake = shutil.which("cmake")
        git = shutil.which("git")
        self.assertIsNotNone(cmake, "CMake required, no silent skip in required mode")
        self.assertIsNotNone(git, "Git required, no silent skip in required mode")
        src = CMAKE_SOURCE.read_text(encoding="utf-8")
        # Preserve the actual source declaration (including SHA, shallow mode,
        # patch command) instead of reconstructing a substitute.
        m = re.search(
            r"^FetchContent_Declare\(\s*QGeoView\b.*?^\)",
            src, re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(m, "Original QGeoView declaration missing")
        block = m.group(0)
        self.assertIn(SHA, block)
        self.assertRegex(block, r"GIT_SHALLOW\s+FALSE")
        self.assertTrue(PATCH_SOURCE.is_file())

        with tempfile.TemporaryDirectory(prefix="fincept-qgeoview-fetch-") as td:
            root = Path(td)
            patch = root / "cmake/patches/qgeoview_remove_agl.cmake"
            patch.parent.mkdir(parents=True)
            patch.write_bytes(PATCH_SOURCE.read_bytes())
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.27)\n"
                "project(FinceptQGeoViewPinQA LANGUAGES NONE)\n"
                "include(FetchContent)\n"
                # CMake >= 3.30 deprecated FetchContent_Populate(name). This
                # explicitly opts into the old behavior for fetch-only smoke.
                "if(POLICY CMP0169)\n cmake_policy(SET CMP0169 OLD)\nendif()\n"
                + block + "\n"
                + "FetchContent_Populate(QGeoView)\n"
                + "execute_process(COMMAND git -C \"\u0024{qgeoview_SOURCE_DIR}\" rev-parse HEAD"
                + " OUTPUT_VARIABLE pinned OUTPUT_STRIP_TRAILING_WHITESPACE"
                + " RESULT_VARIABLE code)\n"
                + "if(NOT code EQUAL 0 OR NOT pinned STREQUAL \"" + SHA + "\")\n"
                + "  message(FATAL_ERROR \"Wrong QGeoView pinned revision: \u0024{pinned}\")\n"
                + "endif()\n"
                + "file(READ \"\u0024{qgeoview_SOURCE_DIR}/lib/CMakeLists.txt\" qgeo_cmake)\n"
                + "if(qgeo_cmake MATCHES \"-framework AGL\")\n"
                + "  message(FATAL_ERROR \"Original AGL patch did not remove framework\")\n"
                + "endif()\n"
                + "message(STATUS \"QGEOVIEW_PIN_AND_PATCH_PASS=\u0024{pinned}\")\n"
            )
            result = subprocess.run(
                [cmake, "-S", str(root), "-B", str(root / "build")],
                capture_output=True, text=True, timeout=240, check=False,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            evidence = result.stdout + "\n" + result.stderr
            self.assertEqual(result.returncode, 0, evidence[-6000:])
            self.assertIn("QGEOVIEW_PIN_AND_PATCH_PASS=" + SHA, evidence)
            # PATCH_COMMAND runs inside FetchContent's nested CMake process;
            # its stdout is not forwarded on a successful quiet configure.
            # The original patch stamp is an executable-phase marker.
            stamps = list((root / "build").rglob("*qgeoview*patch*"))
            self.assertTrue(stamps, "No CMake QGeoView PATCH_COMMAND stamp found")


if __name__ == "__main__":
    unittest.main()
