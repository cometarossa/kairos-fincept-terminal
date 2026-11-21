"""Compile original Fincept quote/MCP translation units with a real Qt 6.8 SDK.

This is an **opt-in** original-source build check. It compiles the changed
translation units to real ELF/Mach-O object files (not mocks or just headers).
It does NOT link FinceptTerminal, run the Qt app, call market providers, or
test KAIROS/IG authentication.

Run in an isolated environment with compiler + Qt 6.8 dev packages:
    FINCEPT_QT_COMPILE_REQUIRED=1 python3 -m unittest -v \
      tests.fincept_original.test_qt6_market_original_compile

Without the opt-in flag it SKIPS if the Qt 6.8 toolchain is unavailable.
With the flag it FAILS CLOSED instead of reporting a misleading green.
"""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "fincept-qt" / "src"
QT_MODULES = ("Qt6Core", "Qt6Network", "Qt6Widgets", "Qt6Sql", "Qt6Concurrent")


class OriginalFinceptQt6TranslationUnits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required = os.getenv("FINCEPT_QT_COMPILE_REQUIRED") == "1"
        compiler = shutil.which("g++") or shutil.which("clang++")
        pkg_config = shutil.which("pkg-config")
        if not compiler or not pkg_config:
            message = "C++ compiler and pkg-config required for original Qt6 compilation"
            if required:
                raise AssertionError(message)
            raise unittest.SkipTest(message)

        version_cmd = subprocess.run(
            [pkg_config, "--modversion", "Qt6Core"],
            capture_output=True, text=True, check=False, timeout=15,
        )
        version = version_cmd.stdout.strip()
        if version_cmd.returncode != 0 or not version.startswith("6.8."):
            message = f"Qt 6.8.x required for original-source QA, found {version or 'unavailable'}"
            if required:
                raise AssertionError(message)
            raise unittest.SkipTest(message)

        cflags = subprocess.run(
            [pkg_config, "--cflags", *QT_MODULES],
            capture_output=True, text=True, check=False, timeout=15,
        )
        if cflags.returncode != 0:
            message = "Qt6 Core/Network/Widgets/Sql/Concurrent development modules required"
            if required:
                raise AssertionError(message + ": " + cflags.stderr.strip())
            raise unittest.SkipTest(message)
        cls.compiler = compiler
        cls.flags = shlex.split(cflags.stdout)
        cls.qt_version = version

    def compile_original_object(self, relative_path):
        source = SRC_ROOT / relative_path
        self.assertTrue(source.is_file(), f"Original source missing: {source}")
        with tempfile.TemporaryDirectory(prefix="fincept-qt6-original-tu-") as build_dir:
            obj = Path(build_dir) / (source.stem + ".o")
            cmd = [
                self.compiler, "-std=c++20", "-O0", "-fPIC",
                "-Wno-deprecated-declarations",
                "-I", str(SRC_ROOT), "-I", str(ROOT / "fincept-qt/include"),
                *self.flags, "-c", str(source), "-o", str(obj),
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False, timeout=180,
            )
            self.assertEqual(
                result.returncode, 0,
                f"Original {relative_path} with Qt {self.qt_version} did not compile:"
                f"\n{result.stderr[-7500:]}",
            )
            self.assertTrue(obj.is_file())
            self.assertGreater(obj.stat().st_size, 1024)

    def test_original_market_data_service_compiles(self):
        self.compile_original_object("services/markets/MarketDataService.cpp")

    def test_original_mcp_markets_tools_compiles(self):
        self.compile_original_object("mcp/tools/MarketsTools.cpp")


if __name__ == "__main__":
    unittest.main()
