"""Functional original technical indicator probe; intended for local Python env with pandas/ta.

This is NOT a Qt screen test. No original Fincept script modified.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import socket
import unittest

from tools.fincept_audit.technical_family_probe_v1 import (
    PINNED_MODULES, SOURCE_RELATIVE, TechnicalProbeError,
    run_all,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / SOURCE_RELATIVE


class OriginalTechnicalFunctionTests(unittest.TestCase):
    def test_all_five_original_indicator_families(self):
        result = run_all(SOURCE)
        self.assertEqual(result["schema"], "fincept_original_technicals_offline_probe_v1")
        self.assertEqual(result["bar_count"], 180)
        self.assertEqual(result["module_count"], 5)
        self.assertEqual(result["total_indicator_columns"], 82)
        self.assertEqual(set(item["module"] for item in result["modules"]), set(PINNED_MODULES))
        self.assertEqual(result["scientific_status"], "NOT_EVALUATED")
        self.assertIs(result["broker_authority"], False)
        self.assertEqual(
            [x["sparse_inactive_at_last_bar"] for x in result["modules"]],
            [[], [], ["psar_down"], [], []],
        )

    def test_mutating_original_ohlcv_denied(self):
        from unittest.mock import patch
        from types import SimpleNamespace

        def corrupt(data):
            data.loc[0, "close"] += 10
            return data.assign(fake_indicator=1.0)

        fake = SimpleNamespace(calculate_all_volatility_indicators=corrupt)
        with patch("tools.fincept_audit.technical_family_probe_v1._load_pinned_module", return_value=fake):
            with self.assertRaisesRegex(TechnicalProbeError, "ORIGINAL_OHLCV_VALUES_CHANGED:volatility"):
                run_all(SOURCE)

    def test_output_ohlcv_rewrite_denied(self):
        from unittest.mock import patch
        from types import SimpleNamespace

        def corrupt(data):
            result = data.copy(deep=True)
            result.loc[0, "close"] += 10
            return result.assign(fake_indicator=1.0)

        fake = SimpleNamespace(calculate_all_volatility_indicators=corrupt)
        with patch("tools.fincept_audit.technical_family_probe_v1._load_pinned_module", return_value=fake):
            with self.assertRaisesRegex(TechnicalProbeError, "ORIGINAL_OHLCV_VALUES_CHANGED:volatility"):
                run_all(SOURCE)

    def test_denied_network_restores_socket_guards(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        original_create_connection = socket.create_connection

        def attempt_network(data):
            socket.create_connection(("127.0.0.1", 1), timeout=0.01)

        fake = SimpleNamespace(calculate_all_volatility_indicators=attempt_network)
        with patch("tools.fincept_audit.technical_family_probe_v1._load_pinned_module", return_value=fake):
            with self.assertRaisesRegex(TechnicalProbeError, "NETWORK_ATTEMPT_DENIED"):
                run_all(SOURCE)

        self.assertIs(socket.socket.connect, original_connect)
        self.assertIs(socket.socket.connect_ex, original_connect_ex)
        self.assertIs(socket.create_connection, original_create_connection)

    def test_connect_ex_denied_and_guard_restored(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        original_connect_ex = socket.socket.connect_ex

        def attempt_network(data):
            # Use a socket API distinct from create_connection; no actual
            # connection is permitted by the probe's guard.
            with socket.socket() as sock:
                sock.connect_ex(("127.0.0.1", 1))

        fake = SimpleNamespace(calculate_all_volatility_indicators=attempt_network)
        with patch("tools.fincept_audit.technical_family_probe_v1._load_pinned_module", return_value=fake):
            with self.assertRaisesRegex(TechnicalProbeError, "NETWORK_ATTEMPT_DENIED"):
                run_all(SOURCE)
        self.assertIs(socket.socket.connect_ex, original_connect_ex)

    def test_historical_infinity_denied_even_when_last_bar_finite(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import numpy as np

        def corrupt(data):
            result = data.copy(deep=True)
            for i in range(21):
                result[f"indicator_{i}"] = 1.0
            result.loc[0, "indicator_0"] = np.inf
            return result

        fake = SimpleNamespace(calculate_all_volatility_indicators=corrupt)
        with patch("tools.fincept_audit.technical_family_probe_v1._load_pinned_module", return_value=fake):
            with self.assertRaisesRegex(TechnicalProbeError, "INFINITE_INDICATOR_HISTORY:volatility:indicator_0"):
                run_all(SOURCE)

    def test_source_pin_tamper_denied(self):
        with TemporaryDirectory() as dir:
            temp = Path(dir)
            for category in PINNED_MODULES:
                name = f"{category}_indicators.py"
                shutil.copyfile(SOURCE / name, temp / name)
            original = temp / "momentum_indicators.py"
            original.write_bytes(original.read_bytes() + b"\n# changed original\n")
            with self.assertRaisesRegex(TechnicalProbeError, "CHANGED_ORIGINAL_SOURCE_SHA256"):
                run_all(temp)

    def test_missing_script_denied(self):
        with TemporaryDirectory() as dir:
            with self.assertRaisesRegex(TechnicalProbeError, "MISSING_OR_INVALID_PINNED_ORIGINAL"):
                run_all(Path(dir))

    def test_source_pin_failure_restores_all_socket_guards(self):
        # A source-integrity rejection must not leave the process patched.
        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        original_create_connection = socket.create_connection
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                TechnicalProbeError, "MISSING_OR_INVALID_PINNED_ORIGINAL"
            ):
                run_all(Path(directory))
        self.assertIs(socket.socket.connect, original_connect)
        self.assertIs(socket.socket.connect_ex, original_connect_ex)
        self.assertIs(socket.create_connection, original_create_connection)

    def test_network_guard_is_restored(self):
        original_connect = socket.socket.connect
        original_create_connection = socket.create_connection
        run_all(SOURCE)
        self.assertIs(socket.socket.connect, original_connect)
        self.assertIs(socket.create_connection, original_create_connection)


if __name__ == "__main__":
    unittest.main()
