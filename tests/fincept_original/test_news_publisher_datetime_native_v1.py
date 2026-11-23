"""Offline source contract for native original Fincept publisher-date provenance.

Native behavior is independently exercised by the real --selftest-feeds
NewsSourceDateQA fixture. These source assertions are NOT a C++ runtime pass.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2] / "fincept-qt" / "src"


class PublisherDateContract(unittest.TestCase):
    def test_distinct_publisher_fields_are_not_sort_timestamp(self):
        h = (ROOT / "services/news/NewsService.h").read_text()
        self.assertIn("int64_t publisher_datetime_ts = 0;", h)
        self.assertIn("QString publisher_datetime_field;", h)
        self.assertIn("int64_t sort_ts = 0;", h)

    def test_news_feed_parser_never_labels_fallback_now_as_publication(self):
        s = (ROOT / "services/news/NewsService_Parsing.cpp").read_text()
        self.assertEqual(s.count("current.publisher_datetime_ts = current.sort_ts;"), 1)
        self.assertNotIn("current.publisher_datetime_ts = parsed_ts;", s)
        self.assertIn("source_clock_explicit && dt.isValid()", s)
        self.assertIn("parse_feed_datetime(text, display)", s)
        self.assertIn("current.publisher_datetime_ts = 0;", s)
        self.assertIn("current.publisher_datetime_field.clear();", s)
        self.assertIn("kNewsMaxFutureSkewSec", s)
        self.assertIn("parsed_ts > 0 &&", s)

    def test_cache_retains_provenance_and_legacy_remains_unknown(self):
        s = (ROOT / "services/news/NewsService.cpp").read_text()
        self.assertIn('o["publisher_datetime_ts"] =', s)
        self.assertIn('o["publisher_datetime_field"] =', s)
        self.assertIn('o["publisher_datetime_ts"].toVariant().toLongLong()', s)
        self.assertIn('o["publisher_datetime_field"].toString()', s)
        self.assertIn('source_field == "pubDate"', s)
        self.assertIn('source_field == "updated"', s)

    def test_original_mcp_default_unchanged_explicit_opt_in_only(self):
        s = (ROOT / "mcp/tools/NewsTools.cpp").read_text()
        self.assertIn('.boolean("include_publisher_datetime"', s)
        self.assertIn('.default_bool(false)', s)
        self.assertIn('if (include_publisher_datetime)', s)
        self.assertIn('publisher_datetime_unix', s)
        self.assertIn('publisher_datetime_field', s)
        self.assertIn('publisher_datetime_attested', s)
        self.assertIn('QJsonValue(QJsonValue::Null)', s)

    def test_native_feed_selftest_inspects_real_rss_parser_cache(self):
        s = (ROOT / "services/feeds/FeedSelfTest.cpp").read_text()
        self.assertIn("NewsService::parse_rss_xml", s)
        self.assertIn("NewsService::serialize_articles", s)
        self.assertIn("NewsService::deserialize_articles", s)
        self.assertIn('NewsSourceDateQA::run()', s)
        self.assertIn('Future publisher date', s)
        self.assertIn("2025-06-04Tnot-a-time", s)
        self.assertIn("Date only has no UTC clock", s)
        self.assertIn('Legacy persisted articles', s)
        self.assertIn("FINCEPT_QA_PUBLIC_RSS_FILE", s)
        self.assertIn("NewsSourceDateQA::run_public_rss_file()", s)
        self.assertIn("recent_24h_https", s)
        self.assertIn("file.size() > 200000", s)


if __name__ == "__main__":
    unittest.main()
