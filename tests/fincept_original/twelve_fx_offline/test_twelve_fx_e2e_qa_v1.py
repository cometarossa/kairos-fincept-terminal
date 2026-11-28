from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from twelve_fx_attempt_qa_v1 import once, AttemptDenied

class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.root.chmod(0o700)
    def tearDown(self):
        self.temp.cleanup()
    def deny(self):
        with self.assertRaisesRegex(AttemptDenied,"^ATTEMPT_ALREADY_CONSUMED$"):
            once(self.root,"tls_success",deadline_seconds=3)
    def test_valid_series_single_attempt(self):
        self.assertEqual(once(self.root,"tls_success",deadline_seconds=3),"TLS_FIXTURE_SHAPE_ONLY")
        self.deny()
    def test_rate_limit_no_retry(self):
        self.assertEqual(once(self.root,"tls_rate_limit",deadline_seconds=3),"TLS_FIXTURE_RATE_LIMITED")
        self.deny()
    def test_invalid_series_no_retry(self):
        self.assertEqual(once(self.root,"tls_invalid",deadline_seconds=3),"TLS_FIXTURE_DATA_REJECTED")
        self.deny()
    def test_competing_full_pipeline(self):
        def task(_):
            try:return once(self.root,"tls_success",deadline_seconds=3)
            except AttemptDenied as exc:return str(exc)
        with ThreadPoolExecutor(max_workers=4) as pool:
            result=list(pool.map(task,range(4)))
        self.assertEqual(result.count("TLS_FIXTURE_SHAPE_ONLY"),1)
        self.assertEqual(result.count("ATTEMPT_ALREADY_CONSUMED"),3)
    def test_deadline_before_transport(self):
        self.assertEqual(once(self.root,"stall",deadline_seconds=.15),"DEADLINE_EXCEEDED")
        self.deny()
if __name__=="__main__":unittest.main()
