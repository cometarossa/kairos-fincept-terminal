"""Offline tests of the real PR #25 sidecar capture helper, no broker/network."""
import sys
import tempfile
import unittest

from research.kairos_bridge_v1.sidecar import BridgeRejected, _capture_bounded


class BoundedCaptureTests(unittest.TestCase):
    def test_exact_byte_limit_and_overflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            for size in (4096, 4097):
                argv = [sys.executable, "-c",
                        f'import sys;sys.stdout.buffer.write(b"x"*{size})']
                if size == 4096:
                    code, out = _capture_bounded(argv, cwd=tmp, env={},
                                                 timeout=3, limit=4096)
                    self.assertEqual(code, 0)
                    self.assertEqual(len(out), size)
                else:
                    with self.assertRaisesRegex(BridgeRejected, "OVERSIZE_FIXTURE_OUTPUT"):
                        _capture_bounded(argv, cwd=tmp, env={},
                                         timeout=3, limit=4096)

    def test_stdout_stderr_share_one_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            for stderr_size, rejected in ((2048, False), (2049, True)):
                argv = [sys.executable, "-c",
                        "import sys;sys.stdout.buffer.write(b'x'*2048);"
                        f"sys.stderr.buffer.write(b'y'*{stderr_size})"]
                if rejected:
                    with self.assertRaisesRegex(BridgeRejected, "OVERSIZE_FIXTURE_OUTPUT"):
                        _capture_bounded(argv, cwd=tmp, env={}, timeout=3, limit=4096)
                else:
                    code, out = _capture_bounded(argv, cwd=tmp, env={},
                                                 timeout=3, limit=4096)
                    self.assertEqual(code, 0)
                    self.assertEqual(len(out), 2048)
                    self.assertEqual(out, 'x' * 2048)
                    self.assertNotIn('y', out)

    def test_benign_stderr_does_not_corrupt_stdout_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = [sys.executable, "-c",
                    "import sys;sys.stdout.write('{\"ok\":true}');"
                    "sys.stderr.write('harmless warning\\n')"]
            code, out = _capture_bounded(argv, cwd=tmp, env={},
                                         timeout=3, limit=4096)
            self.assertEqual(code, 0)
            self.assertEqual(out, '{"ok":true}')
            self.assertNotIn('warning', out)

    def test_invalid_stdout_utf8_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(BridgeRejected, 'INVALID_FIXTURE_ENCODING'):
                _capture_bounded([sys.executable, "-c",
                                  "import sys;sys.stdout.buffer.write(bytes([255]))"],
                                 cwd=tmp, env={}, timeout=3, limit=4096)

    def test_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(BridgeRejected, "TIMEOUT"):
                _capture_bounded([sys.executable, "-c",
                                  "import time;time.sleep(2)"],
                                 cwd=tmp, env={}, timeout=.2, limit=4096)


if __name__ == "__main__":
    unittest.main()
