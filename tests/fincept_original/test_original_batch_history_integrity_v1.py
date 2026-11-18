"""Offline ORIGINAL Fincept batch_all fail-closed history boundary.

No Yahoo import or provider traffic; tests the exact production Python
converter with injected fake data, and checks native C++ wiring uses the same
shared strict OHLCV decoder that standalone get_history already uses.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "fincept-qt/scripts/yfinance_data.py"
MARKET = ROOT / "fincept-qt/src/services/markets/MarketDataService.cpp"


class OriginalBatchHistoryConversion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous = sys.modules.get("yfinance")
        fake_yf = types.ModuleType("yfinance")
        fake_yf.Ticker = lambda *args: (_ for _ in ()).throw(AssertionError("NO_NETWORK_ALLOWED"))
        sys.modules["yfinance"] = fake_yf
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            spec = importlib.util.spec_from_file_location("original_batch_history_integrity_qa", SCRIPT)
            assert spec and spec.loader
            cls.provider = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.provider)
        finally:
            sys.path.remove(str(SCRIPT.parent))

    @classmethod
    def tearDownClass(cls):
        if cls.previous is None:
            sys.modules.pop("yfinance", None)
        else:
            sys.modules["yfinance"] = cls.previous

    @staticmethod
    def _run_one(provider_result):
        request = {"histories": [{"symbol": "SPY", "period": "5d", "interval": "1d"}]}
        with patch.object(OriginalBatchHistoryConversion.provider, "get_historical_period", return_value=provider_result) as f:
            result = OriginalBatchHistoryConversion.provider.get_batch_all(request)
        f.assert_called_once_with("SPY", "5d", "1d")
        return result["histories"][0]

    def test_valid_history_preserved_without_claiming_exchange_asof(self):
        bars = [{"timestamp": 1704153600, "open": 100, "high": 105, "low": 98, "close": 101, "volume": 0}]
        row = self._run_one(bars)
        self.assertEqual(row["points"], bars)
        self.assertNotIn("error", row)
        self.assertEqual((row["symbol"], row["period"], row["interval"]), ("SPY", "5d", "1d"))

    def test_empty_provider_history_fails_instead_of_succeeding_as_empty_series(self):
        row = self._run_one([])
        self.assertEqual(row["points"], [])
        self.assertEqual(row.get("error"), "HISTORY_UNAVAILABLE")

    def test_provider_error_cannot_be_laundered_into_success_or_leak_its_message(self):
        sentinel = "TEST-ONLY-INTERNAL-COOKIE-MUST-NOT-LEAK"
        row = self._run_one({"error": sentinel, "symbol": "SPY"})
        self.assertEqual(row.get("error"), "HISTORY_UNAVAILABLE")
        self.assertNotIn(sentinel, str(row))
        self.assertEqual(row["points"], [])

    def test_provider_exception_error_is_bounded_without_token_echo(self):
        with patch.object(self.provider, "get_historical_period", side_effect=RuntimeError("fake-token-123456789")):
            row = self.provider.get_batch_all({"histories": [{"symbol": "SPY", "period": "5d", "interval": "1d"}]})["histories"][0]
        self.assertEqual(row.get("error"), "HISTORY_UNAVAILABLE")
        self.assertNotIn("fake-token", str(row))

    def test_missing_null_wrong_type_and_false_are_unavailable(self):
        for value in (None, "[]", {}, False, True, 3):
            with self.subTest(value=value):
                row = self._run_one(value)
                self.assertEqual(row.get("error"), "HISTORY_UNAVAILABLE")
                self.assertEqual(row["points"], [])

    def test_batch_omitted_histories_does_not_fetch(self):
        with patch.object(self.provider, "get_historical_period", side_effect=AssertionError("Unexpected fetch")):
            self.assertEqual(self.provider.get_batch_all({}), {})

    def test_native_qt_datahub_history_uses_same_strict_decoder_as_mcp(self):
        source = MARKET.read_text()
        refresh = source[source.index("void MarketDataService::refresh("):source.index("void MarketDataService::publish_quote_to_hub(")]
        single = source[source.index("void MarketDataService::fetch_history("):source.index("// ── Static symbol lists", source.index("void MarketDataService::fetch_history("))]
        self.assertIn("history_integrity::decode(QJsonDocument(pts))", refresh)
        self.assertIn("history_integrity::decode(doc)", single)
        self.assertIn("if (!decoded.has_value())", refresh)
        self.assertIn("hub.publish_error(topic", refresh)
        self.assertIn("self->publish_history_to_hub(sym, per, ivl, *decoded)", refresh)
        # Old Qt conversion silently turned null/missing prices into 0.0.
        loop = refresh[refresh.index('const QJsonArray pts = h.value("points").toArray();'):refresh.index('++hists_ok;', refresh.index('const QJsonArray pts = h.value("points").toArray();'))]
        self.assertNotIn("toDouble()", loop)
        self.assertNotIn("points.append", loop)


if __name__ == "__main__":
    unittest.main()
