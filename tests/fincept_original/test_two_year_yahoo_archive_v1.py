"""Offline-only regression of the original 2y/1d archive window."""
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import capture_public_yahoo_history_f2_v1 as capture


NOW = 1795600000
def rows(n=500, span=720):
    return [{"timestamp": NOW - 86400 - ((n-1-i)*span*86400)//(n-1),
             "open": 100.0, "high": 102.0, "low": 99.0,
             "close": 101.0, "volume": 0} for i in range(n)]


class ArchiveWindowTests(unittest.TestCase):
    def test_two_year_envelope(self):
        s = capture.build_snapshot(rows(), NOW, "SPY", "2y")
        raw = base64.b64decode(s["bars_base64"], validate=True)
        self.assertEqual(json.loads(raw), rows())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), s["bars_sha256"])
        self.assertEqual((s["period"], s["interval"]), ("2y", "1d"))
        self.assertLess(len(json.dumps(s)), 250000)

    def test_coverage_and_invalid_bars(self):
        for rr in (rows(439), rows(561), rows(span=600), rows(span=800)):
            with self.assertRaises(capture.CaptureRejected):
                capture.build_snapshot(rr, NOW, "SPY", "2y")
        for key, value in (("high", 90), ("close", float("nan")), ("volume", -1)):
            rr = rows()
            rr[100][key] = value
            with self.assertRaises(capture.CaptureRejected):
                capture.build_snapshot(rr, NOW, "SPY", "2y")
        rr = rows()
        rr[100]["timestamp"] = rr[99]["timestamp"]
        with self.assertRaises(capture.CaptureRejected):
            capture.build_snapshot(rr, NOW, "SPY", "2y")

    def test_allowlist_and_ack_before_io(self):
        with self.assertRaises(capture.CaptureRejected):
            capture.build_snapshot(rows(), NOW, "AAPL", "2y")
        for ack in ("", capture.DUAL_ACK, capture.MULTI_ACK, capture.ACK):
            with patch.dict(os.environ, {"FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK": ack}):
                with patch.object(capture, "private_directory") as io:
                    with self.assertRaisesRegex(capture.CaptureRejected, "explicit opt-in"):
                        capture.capture(Path("/not-used"), "SPY", "2y")
                    io.assert_not_called()

    def test_archive_namespace_and_original_adapter_contract(self):
        calls = []
        def fake(symbol, period, interval, **kw):
            calls.append((symbol, period, interval, kw))
            return rows()
        adapter = types.SimpleNamespace(get_historical_period=fake)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "archive-2y-SPY").mkdir(mode=0o700)
            with patch.dict(os.environ, {"FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK": capture.ARCHIVE_ACK}), patch.dict(sys.modules, {"yfinance_data": adapter}), patch.object(capture.time, "time", return_value=NOW):
                capture.capture(root, "SPY", "2y")
            self.assertEqual(calls, [("SPY", "2y", "1d", {"strict_research": True})])
            self.assertFalse((root / "snapshot.json").exists())
            self.assertFalse((root / "long-SPY").exists())
            self.assertTrue((root / "archive-2y-SPY" / "snapshot.json").is_file())

    def test_daily_archive_rejects_duplicate_dates_and_long_gaps(self):
        rr = rows()
        rr[100]["timestamp"] = rr[99]["timestamp"] + 1
        with self.assertRaises(capture.CaptureRejected):
            capture.build_snapshot(rr, NOW, "SPY", "2y")
        rr = rows()
        del rr[100:110]
        with self.assertRaises(capture.CaptureRejected):
            capture.build_snapshot(rr, NOW, "EURUSD=X", "2y")

    def test_failed_archive_capture_preserves_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            dest = root / "archive-2y-EURUSD=X"
            dest.mkdir(mode=0o700)
            old = dest / "snapshot.json"
            old.write_text('{"captured_at_unix":1795599999}')
            old.chmod(0o600)
            before = old.read_bytes()
            adapter = types.SimpleNamespace(get_historical_period=lambda *a, **k: [])
            with patch.dict(os.environ, {"FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK": capture.ARCHIVE_ACK}), patch.dict(sys.modules, {"yfinance_data": adapter}), patch.object(capture.time, "time", return_value=NOW):
                with self.assertRaises(capture.CaptureRejected):
                    capture.capture(root, "EURUSD=X", "2y")
            self.assertEqual(old.read_bytes(), before)

    def test_legacy_windows_unchanged(self):
        rr = rows(5, 4)
        self.assertEqual(capture.build_snapshot(rr, NOW, "SPY", "5d")["period"], "5d")
        self.assertEqual(capture.build_snapshot(rows(128, 180), NOW, "SPY", "6mo")["period"], "6mo")
        with self.assertRaises(capture.CaptureRejected):
            capture.build_snapshot(rows(), NOW, "SPY", "6mo")


if __name__ == "__main__":
    unittest.main()
