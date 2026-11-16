"""Execute original Fincept CacheManager SQL with a deterministic synthetic clock.

This tests the SQLite WHERE clause embedded in the original Qt source. It does
NOT execute CacheManager C++, prove host clock integrity, or attest freshness.
Uses only local Python stdlib, no network/IG/credentials.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "fincept-qt/src/storage/cache/CacheManager.cpp"
MARKET_H = ROOT / "fincept-qt/src/services/markets/MarketDataService.h"


def original_cache_select_sql():
    text = SRC.read_text()
    match = re.search(r'cdb\.execute\("(SELECT value FROM unified_cache[^"]+)"', text)
    if not match:
        raise AssertionError("Original cache SQL extraction failed closed")
    sql = match.group(1)
    assert sql == "SELECT value FROM unified_cache WHERE key = ? AND expires_at > datetime('now')"
    return sql


class OriginalSqliteCacheExpiryTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute(
            "CREATE TABLE unified_cache (key TEXT PRIMARY KEY, value TEXT, expires_at TEXT)"
        )
        self.now = datetime(2026, 11, 16, 19, 0, 0, tzinfo=timezone.utc)
        self.clock = self.now.strftime("%Y-%m-%d %H:%M:%S")
        # Same SQL as original, with only the clock substituted for testability.
        self.query = original_cache_select_sql().replace("datetime('now')", "datetime(?)")

    def put(self, key, value, seconds_from_now):
        expiry = (self.now + timedelta(seconds=seconds_from_now)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.db.execute(
            "INSERT INTO unified_cache(key,value,expires_at) VALUES(?,?,?)",
            (key, value, expiry),
        )

    def get(self, key):
        result = self.db.execute(self.query, (key, self.clock)).fetchone()
        return None if result is None else result[0]

    def test_valid_cache_and_expired_cache_are_distinct(self):
        self.put("market:FRESH", '{"received":"18:59:45Z"}', 1)
        self.put("market:EXPIRED", '{"received":"18:59:00Z"}', -1)
        self.assertEqual(self.get("market:FRESH"), '{"received":"18:59:45Z"}')
        self.assertIsNone(self.get("market:EXPIRED"))

    def test_exact_expiry_boundary_is_not_valid(self):
        self.put("market:EDGE", "some local quote", 0)
        self.assertIsNone(self.get("market:EDGE"))

    def test_old_receipt_time_is_not_rewritten_by_select(self):
        self.put("market:OLD", '{"_fincept_local_received_at_utc":"2026-11-16T18:59:31Z"}', 1)
        original = self.get("market:OLD")
        self.assertIn("18:59:31Z", original)
        self.assertNotIn("19:00:00", original)

    def test_parameter_binding_prevents_key_injection(self):
        self.put("market:NORMAL", "some quote", 1)
        self.assertIsNone(self.get("' OR 1=1 --"))

    def test_original_30_second_policy_and_wall_clock_limitation(self):
        self.assertIn("kQuoteCacheTtlSec = 30", MARKET_H.read_text())
        self.assertIn("datetime('now')", original_cache_select_sql())
        self.assertNotIn("CLOCK_MONOTONIC", original_cache_select_sql())


if __name__ == "__main__":
    unittest.main()
