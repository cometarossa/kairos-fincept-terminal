import importlib.util
from pathlib import Path

import pandas as pd
import pytest

SOURCE = Path(__file__).resolve().parents[2] / "fincept-qt/scripts/Analytics/backtesting/fasttrade/ft_indicators.py"
spec = importlib.util.spec_from_file_location("fincept_original_ft_indicators", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_original_module_normalizes_and_preserves_input():
    source = pd.DataFrame({"Open": [1], "Close": [2], "volume": [3], "extra": [4]})
    result = module._ensure_ohlcv(source)
    assert list(result.columns) == ["open", "close", "volume", "extra"]
    assert list(source.columns) == ["Open", "Close", "volume", "extra"]


@pytest.mark.parametrize("columns", [
    ["Close", "close"], ["Close", "CLOSE"], ["close", "close"]
])
def test_original_module_rejects_ambiguous_labels(columns):
    source = pd.DataFrame([[1, 2]], columns=columns)
    with pytest.raises(ValueError, match="Ambiguous OHLCV"):
        module._ensure_ohlcv(source)
    assert list(source.columns) == columns


def test_original_module_preserves_nonstring_labels():
    source = pd.DataFrame([[1, 2, 3]], columns=[2026, ("meta", "x"), "Close"])
    result = module._ensure_ohlcv(source)
    assert list(result.columns) == [2026, ("meta", "x"), "close"]


def test_sma_wrapper_passes_normalized_data_to_original_call_path(monkeypatch):
    """Synthetic fixture: exercise the original SMA wrapper without fast_trade."""
    calls = []

    class SyntheticTA:
        @staticmethod
        def SMA(frame, period, column):
            calls.append((frame.copy(), period, column))
            return frame[column].rolling(period).mean()

    monkeypatch.setattr(module, "_get_ta", lambda: SyntheticTA)
    source = pd.DataFrame({"Open": [1., 2., 3.], "Close": [2., 4., 6.], "Volume": [10., 11., 12.]})
    actual = module.sma(source, period=2)
    pd.testing.assert_series_equal(actual, pd.Series([float("nan"), 3., 5.], name="close"))
    assert len(calls) == 1
    assert calls[0][1:] == (2, "close")
    assert list(calls[0][0].columns) == ["open", "close", "volume"]
    assert "Close" in source.columns


def test_sma_wrapper_rejects_collision_before_indicator_invocation(monkeypatch):
    """No downstream indicator call on ambiguous OHLCV input."""
    calls = []

    class SyntheticTA:
        @staticmethod
        def SMA(*args, **kwargs):
            calls.append(True)
            raise AssertionError("Indicator must not be invoked")

    monkeypatch.setattr(module, "_get_ta", lambda: SyntheticTA)
    source = pd.DataFrame([[1., 2.]], columns=["Close", "close"])
    with pytest.raises(ValueError, match="Ambiguous OHLCV"):
        module.sma(source, period=2)
    assert not calls
    assert list(source.columns) == ["Close", "close"]


def test_ema_wrapper_preserves_extra_mixed_labels_and_blocks_ambiguous_input(monkeypatch):
    """Synthetic EMA path: preserve metadata and reject ambiguous OHLCV before TA.EMA."""
    seen = []

    class SyntheticTA:
        @staticmethod
        def EMA(frame, period, column):
            seen.append((frame.copy(), period, column))
            return frame[column].ewm(span=period, adjust=False).mean()

    monkeypatch.setattr(module, "_get_ta", lambda: SyntheticTA)
    source = pd.DataFrame([[1., 2., 99], [3., 4., 98]], columns=["Open", "Close", 2026])
    actual = module.ema(source, period=2)
    pd.testing.assert_series_equal(actual, pd.Series([2., 10. / 3.], name="close"))
    assert list(seen[0][0].columns) == ["open", "close", 2026]
    assert seen[0][1:] == (2, "close")
    assert list(source.columns) == ["Open", "Close", 2026]

    collision = pd.DataFrame([[1., 2.]], columns=["Close", "close"])
    with pytest.raises(ValueError, match="Ambiguous OHLCV"):
        module.ema(collision, period=2)
    assert len(seen) == 1


def test_unrelated_duplicate_metadata_labels_are_preserved():
    """Only OHLCV collisions are rejected; do not alter original metadata semantics."""
    source = pd.DataFrame([[1, 2, 3]], columns=["Close", "metadata", "metadata"])
    result = module._ensure_ohlcv(source)
    assert list(result.columns) == ["close", "metadata", "metadata"]
    assert list(source.columns) == ["Close", "metadata", "metadata"]
