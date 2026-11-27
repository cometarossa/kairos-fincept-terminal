import json
import os
import socket
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/yahoo_capture_service_v1"))
import screener_request_once_v1 as client


@unittest.skipUnless(sys.platform == "linux", "Linux AF_UNIX and SO_PEERCRED contract")
class SingleAttemptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.request = self.root / "request"
        self.attempt = self.root / "attempt"
        self.request.mkdir(mode=0o700)
        self.attempt.mkdir(mode=0o700)
        self.payloads = []

    def exchange(self, reply=b"CAPTURE_OK\n", mode=0o600, before_reply=None):
        path = self.request / "request.sock"
        errors = []
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(path))
            path.chmod(mode)
            server.listen(1)
            server.settimeout(0.5)

            def serve():
                try:
                    conn, _ = server.accept()
                    with conn:
                        conn.settimeout(2)
                        raw = bytearray()
                        while True:
                            chunk = conn.recv(513)
                            if not chunk:
                                break
                            raw.extend(chunk)
                        self.payloads.append(bytes(raw))
                        if before_reply:
                            before_reply()
                        conn.sendall(reply)
                except socket.timeout:
                    pass
                except Exception as exc:
                    errors.append(exc)

            thread = threading.Thread(target=serve)
            thread.start()
            try:
                result = client._run(self.request, self.attempt)
            finally:
                thread.join(3)
                self.assertFalse(thread.is_alive())
        path.unlink()
        self.assertFalse(errors, errors)
        return result

    def test_exact_payload_durable_before_send_and_single_attempt(self):
        def check_attempt():
            raw = json.loads((self.attempt / "attempt.json").read_bytes())
            self.assertEqual(raw, json.loads(self.payloads[0]))
            self.assertEqual((self.attempt / "attempt.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.exchange(before_reply=check_attempt), "CAPTURE_OK")
        r = json.loads(self.payloads[0])
        self.assertEqual(set(r), {"scope", "screen_id", "request_id", "issued_at_unix"})
        self.assertEqual(r["scope"], client.SCOPE)
        self.assertEqual(r["screen_id"], "day_gainers")
        self.assertRegex(r["request_id"], "^[0-9a-f]{32}$")
        result = json.loads((self.attempt / "result.json").read_bytes())
        self.assertEqual(result, {"request_id": r["request_id"], "status": "CAPTURE_OK", "automatic_retry": False})
        self.assertEqual(self.exchange(), "ALREADY_ATTEMPTED")
        self.assertEqual(len(self.payloads), 1)

    def test_ambiguous_reply_no_retry(self):
        self.assertEqual(self.exchange(b"CAPTURE_OK\nDENIED\n"), "ATTEMPT_UNCERTAIN")
        self.assertEqual(self.exchange(), "ALREADY_ATTEMPTED")
        self.assertEqual(len(self.payloads), 1)

    def test_unknown_reply_no_retry(self):
        self.assertEqual(self.exchange(b"unknown\n"), "ATTEMPT_UNCERTAIN")
        self.assertEqual(self.exchange(), "ALREADY_ATTEMPTED")

    def test_truncated_reply_no_retry(self):
        self.assertEqual(self.exchange(b"CAPTURE_OK"), "ATTEMPT_UNCERTAIN")
        self.assertEqual(self.exchange(), "ALREADY_ATTEMPTED")

    def test_overlong_reply_no_retry(self):
        self.assertEqual(self.exchange(b"x" * 65), "ATTEMPT_UNCERTAIN")
        self.assertEqual(self.exchange(), "ALREADY_ATTEMPTED")

    def test_cooldown_not_retried(self):
        self.assertEqual(self.exchange(b"COOLDOWN\n"), "COOLDOWN")
        self.assertEqual(self.exchange(), "ALREADY_ATTEMPTED")

    def test_unsafe_socket_no_attempt(self):
        self.assertEqual(self.exchange(mode=0o666), "PRECHECK_DENIED")
        self.assertEqual(list(self.attempt.iterdir()), [])
        self.assertEqual(self.payloads, [])

    def test_nonempty_transaction_no_attempt(self):
        (self.attempt / "result.json").touch()
        self.assertEqual(self.exchange(), "PRECHECK_DENIED")
        self.assertEqual(self.payloads, [])

    def test_partial_or_symlink_attempt_denied(self):
        (self.attempt / "attempt.json").symlink_to(self.root / "missing")
        self.assertEqual(self.exchange(), "ALREADY_ATTEMPTED")
        self.assertEqual(self.payloads, [])

    def test_peer_pid_is_not_authority(self):
        self.assertTrue(client._peer_allowed(struct.pack("3i", 0, os.geteuid(), os.getegid())))
        self.assertFalse(client._peer_allowed(struct.pack("3i", 0, os.geteuid() + 1, os.getegid())))
        self.assertFalse(client._peer_allowed(struct.pack("3i", 1, os.geteuid(), os.getegid() + 1)))

    def test_no_opt_in_no_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(client, "_run") as call:
            self.assertEqual(client.main(), 2)
            call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
