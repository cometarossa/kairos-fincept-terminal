"""Original Fincept worker QA readiness metadata: offline, bounded and test-only."""
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "fincept-qt/scripts/yfinance_data.py"
CPP = Path(__file__).resolve().parents[2] / "fincept-qt/src/python/PythonWorker.cpp"
QA_ENV = {"FINCEPT_PUBLIC_MCP_HISTORY_QA": "SPY_5D_PUBLIC_READ",
          "FINCEPT_PUBLIC_QA_SANDBOX_VERIFIED": "EPERM_EXTERNAL"}


class WorkerRuntimeEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stub = types.ModuleType("yfinance")
        stub.__version__ = "0.2.66"
        stub.Ticker = lambda *_: (_ for _ in ()).throw(AssertionError("NETWORK_NOT_AUTHORIZED"))
        cls.old = sys.modules.get("yfinance")
        sys.modules["yfinance"] = stub
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            spec = importlib.util.spec_from_file_location("original_worker_qa_runtime", SCRIPT)
            cls.mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.mod)
        finally:
            sys.path.remove(str(SCRIPT.parent))

    @classmethod
    def tearDownClass(cls):
        if cls.old is None: sys.modules.pop("yfinance", None)
        else: sys.modules["yfinance"] = cls.old

    def _ready(self, env):
        response = io.BytesIO()
        stdin = types.SimpleNamespace(buffer=io.BytesIO())
        stdout = types.SimpleNamespace(buffer=response)
        with patch.dict(os.environ, env, clear=True):
            with patch.object(self.mod.sys, "stdin", stdin), patch.object(self.mod.sys, "stdout", stdout):
                self.mod.run_daemon()
        b = response.getvalue()
        count = struct.unpack(">I", b[:4])[0]
        self.assertEqual(len(b), count + 4)
        return json.loads(b[4:])

    def test_no_opt_in_leaves_original_ready_frame_unchanged(self):
        self.assertEqual(set(self._ready({})), {"ready", "pid"})
        self.assertNotIn("qa_runtime", self._ready({"FINCEPT_PUBLIC_MCP_HISTORY_QA": "SPY_5D_PUBLIC_READ"}))

    def test_exact_opt_in_returns_sanitized_loaded_versions_without_paths(self):
        with patch("importlib.metadata.version", return_value="0.13.0"):
            ready = self._ready(QA_ENV)
        runtime = ready["qa_runtime"]
        self.assertEqual(runtime["yfinance_loaded"], "0.2.66")
        self.assertEqual(runtime["curl_cffi_distribution"], "0.13.0")
        self.assertEqual(runtime["python"], "%s.%s" % sys.version_info[:2])
        self.assertIn("pandas_loaded", runtime)
        self.assertEqual(set(runtime), {"python", "yfinance_loaded", "curl_cffi_distribution", "pandas_loaded"})
        for token in ("path", "proxy", "cookie", "token", "key", "http"):
            self.assertNotIn(token, str(ready).lower())

    def test_raw_version_metadata_never_echoes_sensitive_values(self):
        with patch.object(self.mod.yf, "__version__", "URL_SECRET=ABC"):
            with patch.object(self.mod.pd, "__version__", "7.8.9?crumb=SECRET"):
                with patch("importlib.metadata.version", return_value="cookie/secret"):
                    result = self._ready(QA_ENV)["qa_runtime"]
        self.assertEqual(result["yfinance_loaded"], "UNKNOWN")
        self.assertEqual(result["pandas_loaded"], "UNKNOWN")
        self.assertEqual(result["curl_cffi_distribution"], "UNKNOWN")
        self.assertNotIn("SECRET", str(result))

    def test_no_installed_curl_distribution_is_not_inferred(self):
        with patch("importlib.metadata.version", side_effect=Exception("private host URL")):
            result = self._ready(QA_ENV)["qa_runtime"]
        self.assertEqual(result["curl_cffi_distribution"], "UNKNOWN")

    def test_cpp_output_is_selftest_only_and_allowlist_validated(self):
        source = CPP.read_text()
        self.assertIn('QStringLiteral("--selftest-mcp-server")', source)
        self.assertIn('FINCEPT_PUBLIC_MCP_HISTORY_QA', source)
        self.assertIn('FINCEPT_PUBLIC_QA_SANDBOX_VERIFIED', source)
        self.assertIn('QA_YAHOO_WORKER_VERSION_', source)
        self.assertIn('QRegularExpression', source)
        self.assertNotIn('qa_runtime.toVariantMap()', source)


if __name__ == "__main__":
    unittest.main()
