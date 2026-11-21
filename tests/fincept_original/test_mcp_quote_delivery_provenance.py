"""Offline original-source contract for conservative quote-delivery evidence.

Static source checks verify the Qt wiring; a native C++ harness tests the
actual zero-dependency enum and its non-authority invariants. These tests
do not claim a full Qt6 build, a provider fetch, or a fresh market price.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "fincept-qt" / "src"
SVC = SRC / "services" / "markets" / "MarketDataService.cpp"
SVC_H = SRC / "services" / "markets" / "MarketDataService.h"
MCP = SRC / "mcp" / "tools" / "MarketsTools.cpp"
CACHE = SRC / "storage" / "cache" / "CacheManager.cpp"
CPP = Path(__file__).with_name("mcp_quote_delivery_native.cpp")


class QuoteDeliveryContractTest(unittest.TestCase):
    def test_native_delivery_origin_is_never_market_asof_or_execution_proof(self):
        compiler = shutil.which("clang++") or shutil.which("g++") or shutil.which("c++")
        if not compiler:
            self.skipTest("No native compiler: full Qt still NOT_VERIFIED")
        with tempfile.TemporaryDirectory(prefix="fincept-origin-") as td:
            exe = Path(td) / "origin"
            build = subprocess.run(
                [compiler, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror",
                 "-I", str(SRC), str(CPP), "-o", str(exe)],
                capture_output=True, text=True, timeout=35, check=False,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            check = subprocess.run([str(exe)], capture_output=True,
                                   text=True, timeout=10, check=False)
            self.assertEqual(check.returncode, 0, check.stderr or check.stdout)

    def test_source_separates_received_timestamp_from_market_asof(self):
        hdr = SVC_H.read_text()
        svc = SVC.read_text()
        mcp = MCP.read_text()
        self.assertIn("QuoteDeliveryOrigin delivery_origin", hdr)
        self.assertIn("QString local_received_at_utc", hdr)
        self.assertIn('"_fincept_local_received_at_utc"', svc)
        self.assertIn("QuoteDeliveryOrigin::ProviderResponse", svc)
        self.assertIn("QuoteDeliveryOrigin::UnexpiredCacheHit", svc)
        self.assertIn("QuoteDeliveryOrigin::ProviderFailureCacheHit", svc)
        self.assertIn('"quote_provenance"', mcp)
        self.assertIn('"market_as_of_utc"', mcp)
        self.assertIn('"market_as_of_verified"', mcp)
        self.assertIn('"freshness_verified"', mcp)
        self.assertIn('"market_age_seconds"', mcp)
        self.assertIn('"receipt_clock_verified"', mcp)
        self.assertIn('"execution_eligible"', mcp)
        self.assertIn("quote_delivery_origin_name", mcp)
        self.assertIn("quote_market_asof_verified", mcp)
        self.assertIn("quote_execution_eligible", mcp)
        self.assertIn("QJsonValue::Null", mcp)

    def test_cache_reads_preserve_original_receipt_time_without_restamping(self):
        svc = SVC.read_text()
        cache_reader = svc.split("QuoteData read_cached_quote(", 1)[1].split(
            "void store_quote_in_cache(", 1
        )[0]
        self.assertIn("o.value(kQuoteLocalReceiptKey).toString()", cache_reader)
        self.assertNotIn("currentDateTime", cache_reader)
        self.assertNotIn("currentMSecsSinceEpoch", cache_reader)
        self.assertEqual(
            svc.count("local_received_at_utc = QDateTime::currentDateTimeUtc()"),
            2,
            "Timestamp must be stamped only after two original provider responses",
        )
        self.assertNotIn('o.value(kQuoteLocalReceiptKey).toString("now")', cache_reader)

    def test_provenance_missing_market_timestamp_stays_explicit_null(self):
        svc = SVC.read_text()
        mcp = MCP.read_text()
        self.assertIn("o.value(kQuoteLocalReceiptKey).toString()", svc)
        self.assertIn("q.local_received_at_utc.isEmpty()", mcp)
        self.assertIn("QJsonValue(QJsonValue::Null)", mcp)
        self.assertIn('{"market_as_of_utc", QJsonValue(QJsonValue::Null)}', mcp)
        self.assertIn('{"market_age_seconds", QJsonValue(QJsonValue::Null)}', mcp)
        self.assertIn('{"freshness_verified", false}', mcp)
        self.assertIn('{"receipt_clock_verified", false}', mcp)
        self.assertIn("quote_market_asof_verified(q.delivery_origin)", mcp)
        self.assertIn("quote_execution_eligible(q.delivery_origin)", mcp)

    def test_original_cache_get_rejects_expired_entries(self):
        src = CACHE.read_text()
        self.assertIn("expires_at > datetime('now')", src)
        self.assertIn("SELECT value FROM unified_cache", src)
        self.assertNotIn("get_stale(", src)
        self.assertIn("ProviderFailureCacheHit", SVC.read_text())

    def test_cache_helper_uses_caller_supplied_ttl_not_private_class_constant(self):
        svc = SVC.read_text()
        self.assertIn("void store_quote_in_cache(const QuoteData& quote, int ttl_seconds)", svc)
        self.assertIn('ttl_seconds, "market_data"', svc)
        self.assertIn("store_quote_in_cache(qd, kQuoteCacheTtlSec)", svc)
        self.assertIn("store_quote_in_cache(quote, kQuoteCacheTtlSec)", svc)

    def test_both_market_cache_writers_include_receipt_time(self):
        src = SVC.read_text()
        self.assertIn("store_quote_in_cache(qd, kQuoteCacheTtlSec)", src)
        self.assertIn("store_quote_in_cache(quote, kQuoteCacheTtlSec)", src)
        self.assertIn('"_fincept_local_received_at_utc"', src)
        self.assertIn("read_cached_quote(", src)


if __name__ == "__main__":
    unittest.main()
