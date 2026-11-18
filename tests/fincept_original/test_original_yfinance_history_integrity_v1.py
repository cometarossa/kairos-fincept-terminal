"""Offline, ORIGINAL yfinance_data.py conversion using an isolated fake Ticker.

This tests the production adapter code with a pandas DataFrame but never loads
or contacts yfinance/Yahoo; it does NOT establish provider availability.
"""
import importlib.util
import json
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[2] / "fincept-qt" / "scripts"


class OriginalProviderHistoryConversion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stub = types.ModuleType("yfinance")
        stub.Ticker = lambda *_: (_ for _ in ()).throw(AssertionError("Unexpected provider access"))
        cls.prev = sys.modules.get("yfinance")
        sys.modules["yfinance"] = stub
        spec = importlib.util.spec_from_file_location("fincept_qa_original_yfinance_data_v1", SCRIPTS / "yfinance_data.py")
        assert spec is not None and spec.loader is not None
        cls.module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(SCRIPTS))
        try:
            spec.loader.exec_module(cls.module)
        finally:
            sys.path.remove(str(SCRIPTS))

    @classmethod
    def tearDownClass(cls):
        if cls.prev is None:
            del sys.modules["yfinance"]
        else:
            sys.modules["yfinance"] = cls.prev

    def test_timezone_aware_provider_index_converts_to_utc_epoch(self):
        idx = pd.DatetimeIndex(["2024-01-02 09:30:00", "2024-01-03 09:30:00"], tz="America/New_York")
        frame = pd.DataFrame({
            "Open": [100.0, 101.0], "High": [105.0, 107.0],
            "Low": [99.0, 100.0], "Close": [103.0, 106.0], "Volume": [1000, 1250]},
            index=idx,
        )
        fake = types.SimpleNamespace(history=lambda **kwargs: frame)
        with patch.object(self.module.yf, "Ticker", return_value=fake) as ticker:
            result = self.module.get_historical_period("SYNTH", "5d", "1d")
        ticker.assert_called_once_with("SYNTH")
        self.assertEqual(len(result), 2)
        self.assertEqual([r["timestamp"] for r in result], [int(x.timestamp()) for x in idx])
        self.assertEqual(result[1]["volume"], 1250)
        self.assertEqual(result[1]["close"], 106.0)

    def test_missing_volume_remains_null_not_false_zero(self):
        idx = pd.DatetimeIndex(["2024-01-02"], tz="UTC")
        frame = pd.DataFrame({
            "Open": [100.0], "High": [102.0], "Low": [99.0], "Close": [101.0],
            "Volume": [float("nan")]}, index=idx,
        )
        with patch.object(self.module.yf, "Ticker", return_value=types.SimpleNamespace(history=lambda **_: frame)):
            result = self.module.get_historical_period("SYNTH", "5d", "1d")
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["volume"])
        self.assertIn('"volume": null', json.dumps(result))

    def test_known_zero_volume_stays_zero(self):
        idx = pd.DatetimeIndex(["2024-01-02"], tz="UTC")
        frame = pd.DataFrame({"Open": [100], "High": [102], "Low": [99],
                              "Close": [101], "Volume": [0]}, index=idx)
        with patch.object(self.module.yf, "Ticker", return_value=types.SimpleNamespace(history=lambda **_: frame)):
            result = self.module.get_historical_period("SYNTH", "5d", "1d")
        self.assertEqual(result[0]["volume"], 0)

    def test_finite_close_filter_and_empty_data(self):
        idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], tz="UTC")
        frame = pd.DataFrame({"Open": [100, 101], "High": [102, 103], "Low": [99, 100],
                              "Close": [float("nan"), 102], "Volume": [100, 110]}, index=idx)
        with patch.object(self.module.yf, "Ticker", return_value=types.SimpleNamespace(history=lambda **_: frame)):
            result = self.module.get_historical_period("SYNTH", "5d", "1d")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["volume"], 110)
        with patch.object(self.module.yf, "Ticker", return_value=types.SimpleNamespace(history=lambda **_: frame.iloc[:0])):
            self.assertEqual(self.module.get_historical_period("SYNTH", "5d", "1d"), [])

    def test_provider_error_is_not_price_data(self):
        def raises(**_):
            raise RuntimeError("Provider unavailable")
        with patch.object(self.module.yf, "Ticker", return_value=types.SimpleNamespace(history=raises)):
            result = self.module.get_historical_period("SYNTH", "5d", "1d")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
