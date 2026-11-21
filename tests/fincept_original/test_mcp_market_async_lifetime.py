"""F0/F1 Fincept MCP market-data callback lifetime regression.

Compiles the *actual new standard-library-only header* under a native C++
compiler and runs a deterministic asynchronous fake callback harness. The
original Qt app/MarketDataService cannot be compiled in this standalone test;
static wiring checks on original MarketsTools.cpp supplement, not replace,
the native app build and full Qt QA.
No broker, HTTP, credentials, data providers or fixture uploads.
"""
import pathlib
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "fincept-qt" / "src"
TOOLS = SRC / "mcp" / "tools" / "MarketsTools.cpp"
HEADER = SRC / "mcp" / "tools" / "BoundedAsyncResult.h"
CPP_TEST = pathlib.Path(__file__).with_name("mcp_async_lifetime_native.cpp")


class MarketAsyncLifetimeTest(unittest.TestCase):
    def test_quote_and_history_callback_capture_heap_state_only(self):
        text = TOOLS.read_text(encoding="utf-8")
        self.assertIn('#include "mcp/tools/BoundedAsyncResult.h"', text)
        quote_section = text.split('// ── get_quote', 1)[1].split('// ── lookup_symbol', 1)[0]
        history_section = text.split('// ── get_history', 1)[1]
        self.assertIn("std::make_shared<detail::BoundedAsyncResult<services::QuoteData>>", quote_section)
        self.assertIn("[svc, symbol, state](auto signal_done)", quote_section)
        self.assertIn("[state, symbol, signal_done]", quote_section)
        self.assertIn("auto [ok, q] = state->take()", quote_section)
        self.assertIn("std::make_shared<detail::BoundedAsyncResult<QVector<services::HistoryPoint>>>()", history_section)
        self.assertIn("[svc, symbol, period, interval, state](auto signal_done)", history_section)
        self.assertIn("[state, signal_done]", history_section)
        self.assertIn("auto [ok, points] = state->take()", history_section)
        for forbidden in ("&ok", "&q", "&points"):
            self.assertNotIn(forbidden, quote_section + history_section)

    def test_source_still_calls_original_market_service(self):
        text = TOOLS.read_text(encoding="utf-8")
        self.assertIn('svc->fetch_quotes(', text)
        self.assertIn('svc->fetch_history(', text)
        self.assertEqual(text.count('detail::run_async_wait(svc,'), 2)
        # This change deliberately doesn't add a second market-data client.
        self.assertNotIn("ig.com", text.lower())
        self.assertNotIn("place_order", text.lower())

    def test_native_header_lifecycle_and_race_harness(self):
        compiler = shutil.which("clang++") or shutil.which("g++") or shutil.which("c++")
        if not compiler:
            self.skipTest("Native C++ compiler unavailable; Qt app not claimed tested")
        self.assertTrue(HEADER.is_file())
        self.assertTrue(CPP_TEST.is_file())
        with tempfile.TemporaryDirectory(prefix="fincept-async-lifetime-") as tmp:
            binary = pathlib.Path(tmp) / "test_mcp_async_lifetime"
            build = subprocess.run(
                [compiler, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror",
                 "-pthread", "-I", str(SRC), str(CPP_TEST), "-o", str(binary)],
                check=False, capture_output=True, text=True, timeout=35,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], check=False, capture_output=True,
                                 text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr or run.stdout)


if __name__ == "__main__":
    unittest.main()
