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

    def test_network_guard_is_restored(self):
        original_connect = socket.socket.connect
        original_create_connection = socket.create_connection
        run_all(SOURCE)
        self.assertIs(socket.socket.connect, original_connect)
        self.assertIs(socket.create_connection, original_create_connection)


if __name__ == "__main__":
    unittest.main()
