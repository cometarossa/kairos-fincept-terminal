import os
from pathlib import Path
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from twelve_fx_attempt_qa_v1 import once,AttemptDenied

class TestAttempt(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.p=Path(self.tmp.name)
        self.p.chmod(0o700)
    def tearDown(self):self.tmp.cleanup()
    def deny(self,mode="success",code="ATTEMPT_ALREADY_CONSUMED",**kwargs):
        with self.assertRaisesRegex(AttemptDenied,"^"+code+"$"):once(self.p,mode,**kwargs)
    def test_success_and_claim(self):
        self.assertEqual(once(self.p,"success"),"FIXTURE_OK")
        self.assertEqual((self.p/"attempt.json").read_bytes(),b'{"scope":"OFFLINE_FIXTURE_ONLY","attempt":"CONSUMED"}\n')
        self.assertEqual((self.p/"attempt.json").stat().st_mode & 0o777,0o600)
        self.deny()
    def test_failure_no_retry(self):
        self.assertEqual(once(self.p,"failure"),"FIXTURE_FAILED")
        self.deny()
    def test_deadline_no_retry(self):
        start=time.monotonic()
        self.assertEqual(once(self.p,"stall",deadline_seconds=.25),"DEADLINE_EXCEEDED")
        self.assertLess(time.monotonic()-start,2.0)
        self.deny()
    def test_concurrent_claim(self):
        def run(_):
            try:return once(self.p,"success")
            except AttemptDenied as exc:return str(exc)
        with ThreadPoolExecutor(max_workers=8) as pool:
            result=list(pool.map(run,range(8)))
        self.assertEqual(result.count("FIXTURE_OK"),1)
        self.assertEqual(result.count("ATTEMPT_ALREADY_CONSUMED"),7)
    def test_partial_claim(self):
        (self.p/"attempt.json").write_bytes(b"partial")
        self.deny()
        self.assertEqual((self.p/"attempt.json").read_bytes(),b"partial")
    def test_symlink_claim(self):
        (self.p/"attempt.json").symlink_to(self.p/"not-created")
        self.deny()
        self.assertFalse((self.p/"not-created").exists())
    def test_insecure_directory(self):
        self.p.chmod(0o755)
        self.deny(code="DIRECTORY_DENIED")
        self.assertFalse((self.p/"attempt.json").exists())
    def test_bad_scope(self):
        for mode,deadline in (("other",1),("success",True),("success",float("nan")),("success",10)):
            with self.subTest(mode=mode,deadline=deadline):
                self.deny(mode,code="SCOPE_DENIED",deadline_seconds=deadline)
        self.assertFalse((self.p/"attempt.json").exists())
    def test_spawn_failure(self):
        with patch("twelve_fx_attempt_qa_v1.subprocess.run",side_effect=OSError("synthetic secret")):
            self.assertEqual(once(self.p,"success"),"CHILD_UNAVAILABLE")
        self.deny()
    def test_fsync_failure(self):
        with patch("twelve_fx_attempt_qa_v1.os.fsync",side_effect=OSError("fixture")):
            self.deny(code="ATTEMPT_STATE_UNCERTAIN")
        self.deny()
if __name__=="__main__":unittest.main()
