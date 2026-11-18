"""One PUBLIC read-only provider smoke against the ORIGINAL Python adapter.

Never contacts Yahoo by default. An operator must set the exact explicit opt-in
value and run the process with a separate timeout/ephemeral HOME. This is NOT a
scientific feed attestation, KAIROS authorisation or native Qt/MCP integration.
"""
from datetime import datetime, timezone
import importlib.util
import math
import os
from pathlib import Path
import sys
import unittest

ORIGINAL_SCRIPT = Path(__file__).resolve().parents[2] / "fincept-qt/scripts/yfinance_data.py"
OPT_IN = "FINCEPT_PUBLIC_YAHOO_HISTORY_QA"
APPROVAL = "SPY_5D_SINGLE_PUBLIC_READ"


@unittest.skipUnless(os.environ.get(OPT_IN) == APPROVAL, "Public Yahoo read not explicitly opted in")
class OriginalFinceptPublicHistorySmoke(unittest.TestCase):
    def test_original_adapter_one_spy_history_read(self):
        self.assertTrue(ORIGINAL_SCRIPT.is_file())
        sys.path.insert(0, str(ORIGINAL_SCRIPT.parent))
        try:
            spec = importlib.util.spec_from_file_location("fincept_public_history_qa_original", ORIGINAL_SCRIPT)
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            original = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(original)
        finally:
            sys.path.remove(str(ORIGINAL_SCRIPT.parent))

        original._NET_TIMEOUT = 6.0
        real_ticker = original.yf.Ticker
        calls = []

        def single_public_ticker(symbol):
            self.assertEqual(symbol, "SPY")
            self.assertFalse(calls, "Only one public Ticker request is authorized")
            calls.append(symbol)
            return real_ticker(symbol)

        original.yf.Ticker = single_public_ticker
        # ONE public SPY 5d/1d request; no retries, other symbols or brokers.
        bars = original.get_historical_period("SPY", "5d", "1d")
        self.assertEqual(calls, ["SPY"])
        self.assertIsInstance(bars, list, "Provider returned no supported series")
        self.assertTrue(1 <= len(bars) <= 7, "Missing/oversized period response")
        now = datetime.now(timezone.utc).timestamp()
        previous = 0
        for bar in bars:
            self.assertIsInstance(bar, dict)
            self.assertEqual(set(bar), {"timestamp", "open", "high", "low", "close", "volume"})
            t, o, h, l, c, v = (bar[name] for name in
                              ("timestamp", "open", "high", "low", "close", "volume"))
            self.assertTrue(all(type(x) in (int, float) and math.isfinite(x)
                                for x in (t, o, h, l, c, v)))
            self.assertTrue(t == int(t) and previous < t <= now + 86400)
            self.assertTrue(min(o, h, l, c) > 0 and l <= min(o, c) and h >= max(o, c))
            self.assertTrue(v >= 0 and v == int(v))
            previous = t
        self.assertGreater(previous, now - 14 * 86400, "Public data is too old even for smoke")
        print("PUBLIC_PROVIDER_STRUCTURAL_QA_PASS: n=%d last_day_utc=%s "
              "market_as_of_verified=false execution_authority=false" % (
                  len(bars), datetime.fromtimestamp(previous, timezone.utc).date().isoformat()))


if __name__ == "__main__":
    unittest.main()
