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

    def test_missing_close_is_retained_as_null_and_empty_data_is_empty(self):
        idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], tz="UTC")
        frame = pd.DataFrame({"Open": [100, 101], "High": [102, 103], "Low": [99, 100],
                              "Close": [float("nan"), 102], "Volume": [100, 110]}, index=idx)
        with patch.object(self.module.yf, "Ticker", return_value=types.SimpleNamespace(history=lambda **_: frame)):
            result = self.module.get_historical_period("SYNTH", "5d", "1d")
        self.assertEqual(len(result), 2)
        self.assertIsNone(result[0]["close"])
        self.assertEqual(result[1]["volume"], 110)
        self.assertIn('"close": null', json.dumps(result))
        with patch.object(self.module.yf, "Ticker", return_value=types.SimpleNamespace(history=lambda **_: frame.iloc[:0])):
            self.assertEqual(self.module.get_historical_period("SYNTH", "5d", "1d"), [])

    def test_adjustment_is_explicit_for_both_original_history_paths(self):
        # These are the ORIGINAL yfinance_data functions, not a replacement
        # provider. Capture their actual kwargs with an in-memory fake Ticker.
        # Never call Yahoo, a broker or a market API in this regression.
        idx = pd.DatetimeIndex(["2024-01-02"], tz="America/New_York")
        adjusted_ohlcv = pd.DataFrame({
            "Open": [100.0], "High": [103.0], "Low": [99.0],
            "Close": [102.0], "Volume": [5000]}, index=idx)
        actual_kwargs = []

        def history(**kwargs):
            actual_kwargs.append(dict(kwargs))
            return adjusted_ohlcv

        with patch.object(self.module.yf, "Ticker",
                          return_value=types.SimpleNamespace(history=history)) as ticker:
            period_result = self.module.get_historical_period("SPY", "5d", "1d")
            date_result = self.module.get_historical("SPY", "2024-01-01", "2024-01-04", "1d")
        self.assertEqual(ticker.call_count, 2)
        self.assertEqual(len(actual_kwargs), 2)
        for kwargs in actual_kwargs:
            with self.subTest(kwargs=kwargs):
                self.assertIs(kwargs.get("auto_adjust"), True)
                self.assertIs(kwargs.get("back_adjust"), False)
        self.assertEqual(period_result[0]["close"], 102.0)
        self.assertEqual(date_result[0]["close"], 102.0)

    def test_research_rejects_before_rounding_can_mask_invalid_bar(self):
        idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], tz="UTC")
        frame = pd.DataFrame({"Open": [1.10001, 1.10], "High": [1.12, 1.12],
                              "Low": [1.10002, 1.09], "Close": [1.11, 1.11],
                              "Volume": [0, 0]}, index=idx)
        with patch.object(self.module.yf, "Ticker",
                          return_value=types.SimpleNamespace(history=lambda **_: frame)):
            legacy = self.module.get_historical_period("EURUSD=X", "6mo", "1d")
            self.assertEqual(legacy[0]["open"], legacy[0]["low"])
            strict = self.module.get_historical_period("EURUSD=X", "6mo", "1d", strict_research=True)
        self.assertEqual(strict, {"error": "RESEARCH_RAW_INVALID_BAR"})

    def test_research_valid_rows_preserve_existing_conversion(self):
        idx = pd.DatetimeIndex(["2024-01-02"], tz="UTC")
        frame = pd.DataFrame({"Open": [1.10002], "High": [1.12], "Low": [1.10],
                              "Close": [1.11], "Volume": [0]}, index=idx)
        with patch.object(self.module.yf, "Ticker",
                          return_value=types.SimpleNamespace(history=lambda **_: frame)):
            self.assertEqual(self.module.get_historical_period("EURUSD=X", "5d", "1d", strict_research=True),
                             self.module.get_historical_period("EURUSD=X", "5d", "1d"))

    def test_research_rejects_missing_and_fractional_provider_values(self):
        idx = pd.DatetimeIndex(["2024-01-02"], tz="UTC")
        for field, value in (("Volume", 0.5), ("Volume", float("nan")), ("Close", float("inf")),
                             ("High", 0), ("Low", 2), ("Open", float("nan"))):
            fields = {"Open": [1.1], "High": [1.2], "Low": [1.0], "Close": [1.15], "Volume": [0]}
            fields[field] = [value]
            frame = pd.DataFrame(fields, index=idx)
            with self.subTest(field=field, value=value), patch.object(
                    self.module.yf, "Ticker", return_value=types.SimpleNamespace(history=lambda **_: frame)):
                self.assertEqual(self.module.get_historical_period("SPY", "5d", "1d", strict_research=True),
                                 {"error": "RESEARCH_RAW_INVALID_BAR"})

    def test_opt_in_precision_preserves_valid_raw_prices_only_in_strict_mode(self):
        idx = pd.DatetimeIndex(["2024-01-02"], tz="UTC")
        frame = pd.DataFrame({"Open": [1.08001], "High": [1.08004],
                              "Low": [1.07999], "Close": [1.08002], "Volume": [0]}, index=idx)
        with patch.object(self.module.yf, "Ticker",
                          return_value=types.SimpleNamespace(history=lambda **_: frame)) as ticker:
            legacy = self.module.get_historical_period("EURUSD=X", "1y", "1h", strict_research=True)
            precise = self.module.get_historical_period("EURUSD=X", "1y", "1h", strict_research=True, preserve_research_precision=True)
            self.assertEqual(legacy[0]["close"], 1.08)
            for key in ("open", "high", "low", "close"):
                self.assertEqual(precise[0][key], float(frame.iloc[0][key.capitalize()]))
            before = ticker.call_count
            self.assertEqual(self.module.get_historical_period("EURUSD=X", "1y", "1h", preserve_research_precision=True),
                             {"error": "RESEARCH_PRECISION_REQUIRES_STRICT"})
            self.assertEqual(ticker.call_count, before)
            frame.loc[idx[0], "Low"] = 1.09
            self.assertEqual(self.module.get_historical_period("EURUSD=X", "1y", "1h", strict_research=True, preserve_research_precision=True),
                             {"error": "RESEARCH_RAW_INVALID_BAR"})

    def test_fixed_raw_failure_classes_preserve_strict_rejection(self):
        idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], tz="UTC")
        cases = [
            ("Volume", float("nan"), "MISSING_OR_BOOLEAN"),
            ("Close", float("inf"), "NONFINITE"),
            ("Low", 0, "NONPOSITIVE_PRICE"),
            ("Low", 2, "OHLC_ORDER"),
            ("Volume", -1, "VOLUME_RANGE"),
            ("Volume", 9007199254740992, "VOLUME_RANGE"),
            ("Volume", 0.5, "VOLUME_FRACTIONAL"),
            ("Open", "PRIVATE_PROVIDER_VALUE", "CELL_CONVERSION"),
        ]
        for field, value, reason in cases:
            row = {"Open": 1.1, "High": 1.2, "Low": 1.0, "Close": 1.15, "Volume": 0}
            frame = pd.DataFrame([row, dict(row, **{field: value})], index=idx)
            with self.subTest(reason=reason), patch.object(
                    self.module.yf, "Ticker", return_value=types.SimpleNamespace(history=lambda **_: frame)):
                plain = self.module.get_historical_period("SPY", "5d", "1d", strict_research=True)
                detailed = self.module.get_historical_period(
                    "SPY", "5d", "1d", strict_research=True, diagnose_research_raw_bar=True)
                self.assertEqual(plain, {"error": "RESEARCH_RAW_INVALID_BAR"})
                self.assertEqual(detailed, {"error": "RESEARCH_RAW_INVALID_BAR",
                                            "raw_bar_failure_class": reason})
                self.assertNotIn("PRIVATE_PROVIDER_VALUE", json.dumps(detailed))

    def test_diagnostic_opt_in_requires_strict_before_provider(self):
        with patch.object(self.module.yf, "Ticker") as ticker:
            for flag in (True, "yes", 1):
                result = self.module.get_historical_period("SPY", diagnose_research_raw_bar=flag)
                self.assertEqual(result, {"error": "RESEARCH_DIAGNOSTICS_REQUIRES_STRICT"})
            ticker.assert_not_called()

    def test_provider_error_is_not_price_data(self):
        def raises(**_):
            raise RuntimeError("Provider unavailable")
        with patch.object(self.module.yf, "Ticker", return_value=types.SimpleNamespace(history=raises)):
            result = self.module.get_historical_period("SYNTH", "5d", "1d")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
