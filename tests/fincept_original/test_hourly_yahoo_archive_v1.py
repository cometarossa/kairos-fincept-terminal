"""No-network archive contract tests; all rows are synthetic."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import capture_public_yahoo_hourly_archive_v1 as archive

NOW = 1795600800
def rows():
    import datetime
    start = NOW - 364 * 86400
    return [{"timestamp": t, "open": 1.1, "high": 1.2, "low": 1.0,
             "close": 1.15, "volume": 0}
            for t in range(start, NOW, 3600)
            if datetime.datetime.fromtimestamp(t, datetime.timezone.utc).weekday() < 5]


class HourlyArchiveTests(unittest.TestCase):
    def test_round_trip_and_size(self):
        r = rows()
        encoded = archive.build_archive(r, NOW)
        self.assertEqual(archive.inspect_archive(encoded, hashlib.sha256(encoded).hexdigest()), r)
        self.assertGreater(len(encoded), 250000)
        self.assertLess(len(encoded), archive.MAX_ENVELOPE)

    def test_bad_coverage(self):
        for r in (rows()[:4999], rows()[1200:], rows()[:1000] + rows()[1120:]):
            with self.assertRaises(ValueError):
                archive.build_archive(r, NOW)

    def test_invalid_bar(self):
        for key, value in (("high", 0.9), ("volume", -1), ("open", True), ("close", float("nan"))):
            r = rows()
            r[100][key] = value
            with self.assertRaises(ValueError):
                archive.build_archive(r, NOW)
        r = rows()
        r[100]["timestamp"] += 1
        with self.assertRaises(ValueError):
            archive.build_archive(r, NOW)

    def test_tampering_and_authority(self):
        encoded = archive.build_archive(rows(), NOW)
        with self.assertRaises(ValueError):
            archive.inspect_archive(encoded, "0"*64)
        for key, value in (("execution_authority", True), ("broker_calls", 1), ("rows", 5000)):
            env = json.loads(encoded)
            env[key] = value
            altered = archive._canonical(env)
            with self.assertRaises(ValueError):
                archive.inspect_archive(altered, hashlib.sha256(altered).hexdigest())

    def test_no_ack_no_io(self):
        with patch.dict(os.environ, {"FINCEPT_PUBLIC_HOURLY_ARCHIVE_ACK": ""}), patch.object(archive, "private_directory") as io:
            with self.assertRaisesRegex(ValueError, "OPT_IN_REQUIRED"):
                archive.capture(Path("/not-used"))
            io.assert_not_called()

    def test_single_original_call_and_immutable_publication(self):
        calls = []
        def fake(*a, **kw):
            calls.append((a, kw))
            return rows()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.dict(os.environ, {"FINCEPT_PUBLIC_HOURLY_ARCHIVE_ACK": archive.ACK}), patch.dict(sys.modules, {"yfinance_data": types.SimpleNamespace(get_historical_period=fake)}), patch.object(archive.time, "time", return_value=NOW):
                receipt = archive.capture(root)
                before = (root / archive.FILENAME).read_bytes()
                self.assertEqual(receipt["sha256"], hashlib.sha256(before).hexdigest())
                self.assertEqual((root / archive.FILENAME).stat().st_mode & 0o777, 0o400)
                self.assertFalse((root / "snapshot.json").exists())
                with self.assertRaisesRegex(ValueError, "ARCHIVE_ALREADY_EXISTS"):
                    archive.capture(root)
                self.assertEqual((root / archive.FILENAME).read_bytes(), before)
            self.assertEqual(calls, [(("EURUSD=X", "1y", "1h"), {"strict_research": True})])

    def test_failed_provider_leaves_no_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.dict(os.environ, {"FINCEPT_PUBLIC_HOURLY_ARCHIVE_ACK": archive.ACK}), patch.dict(sys.modules, {"yfinance_data": types.SimpleNamespace(get_historical_period=lambda *a, **k: [])}):
                with self.assertRaises(ValueError):
                    archive.capture(root)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
