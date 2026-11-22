"""Linux-focused offline CMake, asset and workflow contract tests."""
from pathlib import Path
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
import yaml

ROOT = Path(__file__).resolve().parents[2]
CM = ROOT / "fincept-qt/CMakeLists.txt"
WF = ROOT / ".github/workflows/build-cpp.yml"
LNX = ROOT / ".github/workflows/build-linux-qa.yml"
PNG = ROOT / ".github/scripts/create_fallback_icon.py"
COPY = ROOT / ".github/scripts/sync_scripts.sh"

class LinuxBuildTest(unittest.TestCase):
    def test_pinned_qgeoview_full_history(self):
        import re
        cm = CM.read_text()
        m = re.search(r"FetchContent_Declare\(\s*QGeoView\b(.*?)\n\)", cm, re.S)
        self.assertIsNotNone(m)
        self.assertIn("4b2c52c80940e1073c259ded1a57df83036ba1c9",m.group(1))
        self.assertRegex(m.group(1),r"GIT_SHALLOW\s+FALSE")

    def test_linux_script_path(self):
        s=WF.read_text()
        self.assertIn('bash "${GITHUB_WORKSPACE}/.github/scripts/sync_scripts.sh" scripts AppDir/usr/bin/scripts',s)
        self.assertIn('python3 "${GITHUB_WORKSPACE}/.github/scripts/create_fallback_icon.py"',s)
        self.assertTrue(COPY.is_file())

    def test_real_script_from_nested_working_dir(self):
        import shutil
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            script=root/".github/scripts/sync_scripts.sh"
            script.parent.mkdir(parents=True)
            shutil.copyfile(COPY,script)
            work=root/"fincept-qt"
            (work/"scripts").mkdir(parents=True)
            (work/"scripts"/"safe.py").write_text("pass\n")
            (work/"scripts"/"ignore.db").write_text("skip")
            p=subprocess.run(["bash",str(script),"scripts","AppDir/usr/bin/scripts"],cwd=work, text=True,capture_output=True,timeout=20)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertTrue((work/"AppDir/usr/bin/scripts/safe.py").is_file())
            self.assertFalse((work/"AppDir/usr/bin/scripts/ignore.db").exists())

    def test_png_is_deterministic_valid_rgba_256(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=Path(td)/"a.png",Path(td)/"b.png"
            for target in (a,b):
                p=subprocess.run([sys.executable,str(PNG),str(target)],capture_output=True,text=True,timeout=20)
                self.assertEqual(p.returncode,0,p.stderr)
            blob=a.read_bytes()
            self.assertEqual(blob,b.read_bytes())
            self.assertTrue(blob.startswith(bytes.fromhex("89504e470d0a1a0a")))
            pos=8
            names=[]
            dat=b""
            while pos<len(blob):
                count=struct.unpack(">I",blob[pos:pos+4])[0]
                name=blob[pos+4:pos+8]
                data=blob[pos+8:pos+8+count]
                crc=struct.unpack(">I",blob[pos+8+count:pos+12+count])[0]
                self.assertEqual(crc,zlib.crc32(name+data)&0xffffffff)
                pos += 12+count
                names.append(name)
                if name==b"IDAT":dat+=data
            self.assertEqual(pos,len(blob))
            self.assertEqual(names,[b"IHDR",b"IDAT",b"IEND"])
            self.assertEqual(struct.unpack(">II",blob[16:24]),(256,256))
            raw=zlib.decompress(dat)
            self.assertEqual(len(raw),256*(1+256*4))

    def test_linux_only_workflow_matrix(self):
        with LNX.open() as f:flow=yaml.safe_load(f)
        matrix=flow["jobs"]["build"]["strategy"]["matrix"]["include"]
        self.assertEqual(len(matrix),1)
        self.assertEqual(matrix[0]["platform"],"Linux")
        self.assertEqual(matrix[0]["arch"],"x64")
        self.assertEqual(matrix[0]["os"],"ubuntu-22.04")
        self.assertEqual(set(flow["jobs"]),{"build"})

if __name__=="__main__":
    unittest.main()
