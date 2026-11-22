"""No-network regressions: correct Qt offscreen plugin in packaged Linux AppImage."""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[2]
FILES=(ROOT/".github/workflows/build-cpp.yml", ROOT/".github/workflows/build-linux-qa.yml")
PLUGIN="libqoffscreen.so"

def linux_steps(path):
    data=yaml.safe_load(path.read_text(encoding="utf8"))
    steps=data["jobs"]["build"]["steps"]
    package=next(s for s in steps if s.get("name")=="Package (Linux)")
    smoke=next(s for s in steps if s.get("name")=="Verify packaged Linux AppImage in headless mode")
    return steps,package,smoke

class LinuxOffscreenTest(unittest.TestCase):
    def test_packaging_workflows_preserve_offscreen_and_test_real_appimage(self):
        for path in FILES:
            with self.subTest(path=path.name):
                steps,pkg,smoke=linux_steps(path)
                run=pkg["run"]
                self.assertIn('AppDir/usr/plugins/platforms/libqoffscreen.so',run)
                self.assertIn('QT_ROOT_DIR',run)
                self.assertIn('install -D -m 0755',run)
                self.assertLess(run.index('QT_OFFSCREEN_SRC='),run.index('./linuxdeploy-x86_64.AppImage'))
                self.assertLess(steps.index(pkg),steps.index(smoke))
                self.assertLess(steps.index(smoke),next(i for i,s in enumerate(steps) if s.get("name")=="Upload artifact"))
                self.assertEqual(smoke["if"],"runner.os == 'Linux'")
                self.assertEqual(smoke["env"]["QT_QPA_PLATFORM"],"offscreen")
                self.assertEqual(str(smoke["env"]["APPIMAGE_EXTRACT_AND_RUN"]),"1")
                self.assertIn('dist/FinceptTerminal-Linux-x86_64.AppImage',smoke["run"])
                self.assertNotIn('build/FinceptTerminal',smoke["run"])

    @unittest.skipUnless(sys.platform.startswith('linux'), 'requires GNU install -D')
    def test_extracted_real_staging_block_with_matching_plugin_fixture(self):
        _,pkg,_=linux_steps(FILES[0])
        run=pkg["run"]
        block=run.split("# ── Headless QPA platform plugin:",1)[1].split("./linuxdeploy-x86_64.AppImage",1)[0]
        script="set -e\n# "+block
        with tempfile.TemporaryDirectory(prefix="fincept-qt-offscreen-") as td:
            root=Path(td)
            qt=root/"Qt/plugins/platforms"
            qt.mkdir(parents=True)
            (qt/PLUGIN).write_bytes(b"matching-Qt6-plugin")
            env={**os.environ,"QT_ROOT_DIR":str(root/"Qt")}
            passed=subprocess.run(["bash","-c",script],cwd=root,env=env,text=True,capture_output=True,timeout=10)
            self.assertEqual(passed.returncode,0,passed.stderr)
            target=root/"AppDir/usr/plugins/platforms"/PLUGIN
            self.assertEqual(target.read_bytes(),b"matching-Qt6-plugin")
            target.unlink()
            (qt/PLUGIN).unlink()
            failed=subprocess.run(["bash","-c",script],cwd=root,env=env,text=True,capture_output=True,timeout=10)
            self.assertNotEqual(failed.returncode,0)
            self.assertIn("offscreen platform plugin missing",failed.stderr)
            self.assertFalse(target.exists())

    def test_linux_only_qa_matrix_does_not_schedule_other_platforms(self):
        y=yaml.safe_load(FILES[1].read_text())
        m=y["jobs"]["build"]["strategy"]["matrix"]["include"]
        self.assertEqual([(x["platform"],x["arch"]) for x in m],[("Linux","x64")])

if __name__=="__main__":
    unittest.main()
