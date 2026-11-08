"""Offline probe contract tests against fake providers only (no market data)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (Path(__file__).resolve().parents[2]
          / "tools" / "fincept_audit" / "offline_backtesting_probe.py")
PROVIDERS = ("vectorbt", "backtestingpy", "fasttrade", "zipline", "bt", "fincept")
BACKTESTINGPY = SCRIPT.with_name("backtestingpy_fixture_probe.py")

FAKE_PROVIDER = r"""
import json
import sys
command = sys.argv[1]
args = json.loads(sys.stdin.read())
if command == "get_strategies":
    result = {"success": True, "data": [{"type": "test_strategy"}]}
elif command == "get_indicators":
    result = {"indicators": {"Test Category": [{"id": "test_indicator"}]}}
elif command == "get_command_options":
    result = {"success": True, "data": {"dummy": ["test"]}}
elif command == "run_backtest":
    rows = args.get("brokerCandles", {}).get("KAIROS_FIXTURE", [])
    result = {
        "success": len(rows) == 320,
        "data": {"status": "completed", "dataSource": "synthetic-regression-fixture",
                 "usingSyntheticData": False},
    }
else:
    result = {"success": False}
print(json.dumps(result))
"""


class ProbeContractTests(unittest.TestCase):
    def test_second_provider_fails_closed_without_socket_guard(self):
        with tempfile.TemporaryDirectory(prefix="fincept-audit-no-guard-") as tmp:
            result = subprocess.run(
                [sys.executable, "-S", str(BACKTESTINGPY), "--scripts-root", tmp],
                capture_output=True, text=True, timeout=12,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
                     "PYTHONPATH": "", "PYTHONNOUSERSITE": "1"},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("network-deny guard not active", result.stderr)

    def test_fixture_probe_with_python_symlinks(self):
        with tempfile.TemporaryDirectory(prefix="fincept-qa-local-") as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            for name in PROVIDERS:
                folder = scripts / "Analytics" / "backtesting" / name
                folder.mkdir(parents=True)
                (folder / f"{name}_provider.py").write_text(FAKE_PROVIDER)
            venv_bin = root / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            python_link = venv_bin / "python"
            python_link.symlink_to(sys.executable)
            result = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--scripts-root", str(scripts),
                 "--venv1-python", str(python_link),
                 "--venv2-python", str(python_link)],
                capture_output=True, text=True, timeout=30,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                     "LANG": "C.UTF-8"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            doc = json.loads(result.stdout)
            self.assertTrue(doc["verified_network_guard"])
            self.assertTrue(doc["injected_vectorbt"]["ok"])
            self.assertEqual(doc["injected_vectorbt"]["fixture_candles"], 320)
            self.assertFalse(doc["injected_vectorbt"]["provider_usingSyntheticData"])
            for provider in PROVIDERS:
                for cmd in ("get_strategies", "get_indicators", "get_command_options"):
                    self.assertTrue(doc["providers"][provider][cmd]["ok"])
                    self.assertEqual(doc["providers"][provider][cmd]["count"], 1)


if __name__ == "__main__":
    unittest.main()
