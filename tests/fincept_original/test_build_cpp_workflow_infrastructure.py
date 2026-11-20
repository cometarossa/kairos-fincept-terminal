"""Offline regression for the manual five-platform Fincept Qt workflow."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github/workflows/build-cpp.yml"
COPY_SCRIPT = ROOT / ".github/scripts/sync_scripts.sh"


def lines():
    return WF.read_text(encoding="utf-8").splitlines()


def windows_step_shell():
    src = lines()
    start = src.index("      - name: Install OpenSSL + zlib (Windows)")
    run = next(i for i in range(start + 1, len(src)) if src[i] == "        run: |")
    end = next(i for i in range(run + 1, len(src))
               if src[i].startswith("      - name: "))
    return "\n".join(x[10:] if x.startswith("          ") else x
                     for x in src[run + 1:end]) + "\n"


class BuildCppWorkflowInfrastructureTest(unittest.TestCase):
    def test_intel_runner_architecture_and_selftest(self):
        src = lines()
        start = src.index("          # ---- macOS x64 (Intel) ----")
        section = "\n".join(src[start:start + 12])
        self.assertIn("- os: macos-15-intel", section)
        self.assertIn("arch: x64", section)
        self.assertIn("CMAKE_OSX_ARCHITECTURES=x86_64", section)
        self.assertIn("          - os: macos-15", "\n".join(src[50:65]))
        smoke = src.index("      - name: Run self-tests (headless)")
        self.assertIn("matrix.platform == 'Windows'", src[smoke + 1])
        self.assertNotIn("macOS", src[smoke + 1])

    def test_all_packaging_paths_are_workspace_anchored(self):
        self.assertTrue(COPY_SCRIPT.is_file())
        calls = [s.strip() for s in lines() if s.lstrip().startswith("bash ")
                 and ".github/scripts/sync_scripts.sh" in s]
        self.assertEqual(len(calls), 4, calls)
        expected = 'bash "' + chr(36) + '{GITHUB_WORKSPACE}/.github/scripts/sync_scripts.sh" '
        for call in calls:
            self.assertTrue(call.startswith(expected), call)

    def test_real_copy_script_from_nested_working_directory(self):
        with tempfile.TemporaryDirectory(prefix="fincept-copy-") as td:
            root = Path(td)
            script = root / ".github/scripts/sync_scripts.sh"
            script.parent.mkdir(parents=True)
            shutil.copyfile(COPY_SCRIPT, script)
            cwd = root / "fincept-qt"
            src = cwd / "scripts"
            src.mkdir(parents=True)
            (src / "keep.py").write_text("safe\n")
            (src / "discard.db").write_text("discard\n")
            (src / "__pycache__").mkdir()
            (src / "__pycache__/discard.pyc").write_text("discard\n")
            calls = [s.strip() for s in lines() if s.lstrip().startswith("bash ")
                     and ".github/scripts/sync_scripts.sh" in s
                     and "scripts dist/scripts" in s]
            self.assertTrue(calls)
            proc = subprocess.run(["bash", "-c", calls[0]], cwd=cwd,
                                  env={**os.environ, "GITHUB_WORKSPACE": str(root)},
                                  text=True, capture_output=True, timeout=20)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((cwd / "dist/scripts/keep.py").exists())
            self.assertFalse((cwd / "dist/scripts/discard.db").exists())
            self.assertFalse((cwd / "dist/scripts/__pycache__").exists())

    def _check_zlib(self, archive):
        with tempfile.TemporaryDirectory(prefix="fincept-vcpkg-") as td:
            root = Path(td) / "vcpkg"
            root.mkdir()
            shim = root / "vcpkg"
            shim.write_text("#!/bin/sh\nexit 0\n")
            shim.chmod(0o755)
            ssl = root / "installed/x64-windows/lib"
            ssl.mkdir(parents=True)
            (ssl / "libcrypto.lib").write_bytes(b"fixture")
            zlib = root / "installed/x64-windows-static-md/lib"
            zlib.mkdir(parents=True)
            if archive:
                (zlib / archive).write_bytes(b"static-zlib-fixture")
            env_file = Path(td) / "github_env"
            env = {**os.environ, "VCPKG_INSTALLATION_ROOT": str(root),
                   "GITHUB_ENV": str(env_file)}
            proc = subprocess.run(["bash", "-c", windows_step_shell()],
                                  env=env, text=True, capture_output=True,
                                  timeout=20, check=False)
            if archive:
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertEqual((zlib / "zlib.lib").read_bytes(),
                                 b"static-zlib-fixture")
                self.assertIn("ZLIB_ROOT=", env_file.read_text())
            else:
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("static zlib archive not found",
                              proc.stdout + proc.stderr)

    def test_aliases_vcpkg_libzs(self):
        self._check_zlib("libzs.lib")

    def test_missing_static_archive_fails_closed(self):
        self._check_zlib(None)


if __name__ == "__main__":
    unittest.main()
