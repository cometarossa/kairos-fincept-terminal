#include "services/feeds/FeedSelfTest.h"

#include "services/feeds/FeedParseUtil.h"
#include "services/feeds/FeedScraper.h"
#include "services/feeds/FeedTypes.h"
#include "services/news/NewsService.h"

#include <QDateTime>
#include <QFile>
#include <QString>

#include <cstdio>
#include <cstdint>
#include <algorithm>

namespace fincept::services {

// Friend-only offline regression of the actual original NewsService RSS
// parser and cache; cannot start a provider, GUI, MCP or network request.
struct NewsSourceDateQA {
    static bool run() {
        RSSFeed feed{"qa-publisher", "QA", "https://example.invalid/rss",
                     "MARKETS", "GLOBAL", "TEST", 2};
        const QByteArray rss =
            "<rss><channel>"
            "<item><title>Known publisher date</title><link>https://example.invalid/a</link>"
            "<pubDate>Wed, 04 Jun 2025 10:00:00 GMT</pubDate></item>"
            "<item><title>Missing publisher date</title><link>https://example.invalid/b</link></item>"
            "<item><title>Invalid publisher date</title><link>https://example.invalid/c</link>"
            "<pubDate>not-a-real-date</pubDate></item>"
            "<item><title>Future publisher date</title><link>https://example.invalid/d</link>"
            "<pubDate>Wed, 04 Jun 2099 10:00:00 GMT</pubDate></item>"
            "<item><title>Updated is not published</title><link>https://example.invalid/e</link>"
            "<updated>2025-06-04T10:00:00Z</updated></item>"
            "<item><title>Malformed ISO date contains a valid substring</title>"
            "<link>https://example.invalid/f</link>"
            "<pubDate>2025-06-04Tnot-a-time</pubDate></item>"
            "<item><title>Date only has no UTC clock</title>"
            "<link>https://example.invalid/g</link>"
            "<pubDate>2025-06-04</pubDate></item>"
            "</channel></rss>";
        const auto a = NewsService::parse_rss_xml(rss, feed);
        const qint64 expected = QDateTime::fromString(
            "2025-06-04T10:00:00Z", Qt::ISODate).toSecsSinceEpoch();
        if (a.size() != 7 || a[0].publisher_datetime_ts != expected ||
            a[0].publisher_datetime_field != "pubDate" ||
            a[1].publisher_datetime_ts != 0 || !a[1].publisher_datetime_field.isEmpty() ||
            a[2].publisher_datetime_ts != 0 || !a[2].publisher_datetime_field.isEmpty() ||
            a[3].publisher_datetime_ts != 0 || !a[3].publisher_datetime_field.isEmpty() ||
            a[4].publisher_datetime_ts != expected ||
            a[4].publisher_datetime_field != "updated" ||
            a[5].publisher_datetime_ts != 0 || !a[5].publisher_datetime_field.isEmpty() ||
            a[6].publisher_datetime_ts != 0 || !a[6].publisher_datetime_field.isEmpty()) {
            return false;
        }
        // Only sorting falls back to now; it MUST NOT promote the guessed
        // arrival clock to source-claimed publication clock.
        if (a[1].sort_ts <= 0 || a[2].sort_ts <= 0 || a[3].sort_ts <= 0)
            return false;
        const auto restored = NewsService::deserialize_articles(NewsService::serialize_articles(a));
        if (restored.size() != 7 || restored[0].publisher_datetime_ts != expected ||
            restored[0].publisher_datetime_field != "pubDate" ||
            restored[1].publisher_datetime_ts != 0 ||
            restored[4].publisher_datetime_field != "updated" ||
            restored[5].publisher_datetime_ts != 0 ||
            restored[6].publisher_datetime_ts != 0) {
            return false;
        }
        // Legacy persisted articles cannot acquire a publisher clock from
        // their synthetic sort_ts when the new fields are absent.
        const QString legacy = R"([{"headline":"Old story","sort_ts":1795000000}])";
        const auto old = NewsService::deserialize_articles(legacy);
        return old.size() == 1 && old[0].publisher_datetime_ts == 0 &&
               old[0].publisher_datetime_field.isEmpty();
    }

    // Explicit offline QA only: consume an operator-captured public RSS XML
    // file as input to the ORIGINAL parser; no app-side HTTP, credentials or
    // generic KAIROS tool invocation. Prints counts/timestamps, not headlines.
    static bool run_public_rss_file() {
        const QString path = qEnvironmentVariable("FINCEPT_QA_PUBLIC_RSS_FILE");
        if (path.isEmpty())
            return true; // zero side effects in normal --selftest-feeds
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly) || file.size() <= 0 || file.size() > 200000)
            return false;
        const QByteArray xml = file.readAll();
        RSSFeed feed{"qa-public-news", "Public QA", "https://search.cnbc.com/",
                     "MARKETS", "GLOBAL", "CNBC", 2};
        const auto articles = NewsService::parse_rss_xml(xml, feed);
        const qint64 now = QDateTime::currentSecsSinceEpoch();
        int parsed_dates = 0;
        int recent_dates = 0;
        int64_t newest_publisher_time = 0; // same C++ type as NewsArticle::publisher_datetime_ts
        for (const auto& a : articles) {
            if (a.publisher_datetime_ts <= 0 || a.publisher_datetime_field != "pubDate")
                continue;
            ++parsed_dates;
            newest_publisher_time = std::max(newest_publisher_time, a.publisher_datetime_ts);
            if (a.publisher_datetime_ts >= now - 24 * 3600 &&
                a.publisher_datetime_ts <= now + 300 && a.link.startsWith("https://"))
                ++recent_dates;
        }
        std::printf("[NewsDateQA] external_rss_items=%d parsed_publisher_dates=%d "
                    "recent_24h_https=%d latest_publisher_epoch=%lld\n",
                    static_cast<int>(articles.size()), parsed_dates, recent_dates,
                    static_cast<long long>(newest_publisher_time));
        return !articles.isEmpty() && parsed_dates > 0 && recent_dates > 0;
    }
};

} // namespace fincept::services

namespace fincept::feeds {

int run_feed_selftest() {
    int failures = 0;
    auto check = [&](const char* label, bool ok) {
        std::printf("[%s] %s\n", ok ? "PASS" : "FAIL", label);
        if (!ok)
            ++failures;
    };

    { // RSS 2.0 auto
        FeedSubscription s;
        s.id = "t1";
        s.name = "RSS";
        s.format = FeedFormat::Auto;
        const QByteArray rss = "<?xml version=\"1.0\"?><rss version=\"2.0\"><channel>"
                               "<item><title>Hello</title><link>http://x/1</link>"
                               "<description>&lt;b&gt;Body&lt;/b&gt;</description>"
                               "<pubDate>Wed, 04 Jun 2025 10:00:00 GMT</pubDate></item>"
                               "<item><title>World</title><link>http://x/2</link></item>"
                               "</channel></rss>";
        const auto items = FeedScraper::parse(rss, s);
        check("rss: 2 items", items.size() == 2);
        check("rss: title", !items.isEmpty() && items[0].title == "Hello");
        check("rss: html stripped", !items.isEmpty() && items[0].summary == "Body");
    }
    { // Atom auto
        FeedSubscription s;
        s.id = "t2";
        s.name = "Atom";
        s.format = FeedFormat::Auto;
        const QByteArray atom = "<?xml version=\"1.0\"?><feed xmlns=\"http://www.w3.org/2005/Atom\">"
                                "<entry><title>AT</title><link rel=\"alternate\" href=\"http://a/1\"/>"
                                "<summary>S</summary><updated>2025-06-04T10:00:00Z</updated></entry></feed>";
        const auto items = FeedScraper::parse(atom, s);
        check("atom: 1 item", items.size() == 1);
        check("atom: link href", !items.isEmpty() && items[0].link == "http://a/1");
    }
    { // JSON auto (items[] container)
        FeedSubscription s;
        s.id = "t3";
        s.name = "JSON";
        s.format = FeedFormat::Auto;
        const QByteArray json = R"({"items":[{"title":"J1","url":"http://j/1"},{"title":"J2"}]})";
        const auto items = FeedScraper::parse(json, s);
        check("json: 2 items", items.size() == 2);
        check("json: link from url", !items.isEmpty() && items[0].link == "http://j/1");
    }
    { // CSV auto
        FeedSubscription s;
        s.id = "t4";
        s.name = "CSV";
        s.format = FeedFormat::Csv;
        const QByteArray csv = "name,price\nAAPL,200\nMSFT,410\n";
        const auto items = FeedScraper::parse(csv, s);
        check("csv: 2 rows", items.size() == 2);
        check("csv: field price", !items.isEmpty() && items[0].fields.value("price") == "200");
    }
    { // CSV: quoted fields containing the delimiter, CRLF line endings
        FeedSubscription s;
        s.id = "t4q";
        s.name = "CSVQ";
        s.format = FeedFormat::Csv;
        const QByteArray csv = "name,price\r\n\"Apple, Inc.\",200\r\n\"Say \"\"hi\"\"\",410\r\n";
        const auto items = FeedScraper::parse(csv, s);
        check("csv quoted: 2 rows", items.size() == 2);
        check("csv quoted: comma kept inside field",
              !items.isEmpty() && items[0].fields.value("name") == "Apple, Inc." &&
                  items[0].fields.value("price") == "200");
        check("csv quoted: escaped quote", items.size() > 1 && items[1].fields.value("name") == "Say \"hi\"");
        check("csv crlf: last header trimmed", !items.isEmpty() && items[0].fields.contains("price"));
    }
    { // Item links are publisher-supplied: only web URLs may survive
        FeedSubscription s;
        s.id = "t4l";
        s.name = "Links";
        s.format = FeedFormat::Auto;
        const QByteArray rss = "<?xml version=\"1.0\"?><rss version=\"2.0\"><channel>"
                               "<item><title>Evil</title><link>file:///C:/Windows/System32/calc.exe</link></item>"
                               "<item><title>Good</title><link>https://example.com/a</link></item>"
                               "</channel></rss>";
        const auto items = FeedScraper::parse(rss, s);
        check("link: non-web scheme dropped", items.size() == 2 && items[0].link.isEmpty());
        check("link: https kept", items.size() == 2 && items[1].link == "https://example.com/a");
    }
    const QByteArray custom_xml = "<data><record><headline>H1</headline><url>http://m/1</url><sym>ABC</sym></record>"
                                  "<record><headline>H2</headline><url>http://m/2</url><sym>XYZ</sym></record></data>";

    { // Manual XML mapping (role-based field list)
        FeedSubscription s;
        s.id = "t5";
        s.name = "Manual";
        s.format = FeedFormat::Xml;
        s.parse_mode = ParseMode::Manual;
        s.mapping.item_selector = "record";
        s.mapping.fields = {
            {"Title", "headline", "title"},
            {"Link", "url", "link"},
            {"Ticker", "sym", ""},
        };
        const auto items = FeedScraper::parse(custom_xml, s);
        check("manual: 2 records", items.size() == 2);
        check("manual: mapped title role", !items.isEmpty() && items[0].title == "H1");
        check("manual: mapped link role", !items.isEmpty() && items[0].link == "http://m/1");
        check("manual: extra column", !items.isEmpty() && items[0].fields.value("Ticker") == "ABC");
    }
    { // Field discovery on the same custom XML
        FeedSubscription s;
        s.id = "t5d";
        s.format = FeedFormat::Xml;
        const auto schema = FeedScraper::discover(custom_xml, s);
        check("discover: ok", schema.ok);
        check("discover: item selector", schema.item_selector == "record");
        QStringList paths;
        for (const auto& f : schema.fields)
            paths << f.path;
        check("discover: found headline", paths.contains("headline"));
        check("discover: found sym", paths.contains("sym"));
    }
    { // Field discovery on JSON
        FeedSubscription s;
        s.id = "t5j";
        s.format = FeedFormat::Json;
        const QByteArray json = R"({"results":[{"hl":"X","u":"http://k/1","t":"2025-01-01"}]})";
        const auto schema = FeedScraper::discover(json, s);
        check("discover json: ok", schema.ok);
        check("discover json: array path", schema.item_selector == "results");
        QStringList paths;
        for (const auto& f : schema.fields)
            paths << f.path;
        check("discover json: keys", paths.contains("hl") && paths.contains("u"));
    }
    { // HTML access-denied guard
        FeedSubscription s;
        s.id = "t6";
        s.name = "HTML";
        s.format = FeedFormat::Auto;
        const auto items = FeedScraper::parse("<!doctype html><html><body>nope</body></html>", s);
        check("html: zero items (guarded)", items.isEmpty());
    }
    { // Date/time parsing across real-world pubDate formats
        const qint64 ref = QDateTime::fromString("2025-06-04T10:00:00Z", Qt::ISODate).toSecsSinceEpoch();
        QString disp;
        check("date rfc822 GMT", parse_feed_datetime("Wed, 04 Jun 2025 10:00:00 GMT", disp) == ref);
        check("date rfc822 +0000", parse_feed_datetime("Wed, 04 Jun 2025 10:00:00 +0000", disp) == ref);
        check("date rfc822 no-day", parse_feed_datetime("04 Jun 2025 10:00:00 +0000", disp) == ref);
        check("date iso Z", parse_feed_datetime("2025-06-04T10:00:00Z", disp) == ref);
        check("date iso ms Z", parse_feed_datetime("2025-06-04T10:00:00.000Z", disp) == ref);
        check("date iso offset", parse_feed_datetime("2025-06-04T15:30:00+05:30", disp) == ref);
        check("date rfc822 EDT", parse_feed_datetime("Wed, 04 Jun 2025 06:00:00 EDT", disp) == ref);
        check("date epoch sec", parse_feed_datetime("1717495200", disp) == 1717495200);
        check("date epoch ms", parse_feed_datetime("1717495200000", disp) == 1717495200);
        check("date space sep (parsed)", parse_feed_datetime("2025-06-04 10:00:00", disp) != 0);
        check("date date-only (parsed)", parse_feed_datetime("2025-06-04", disp) != 0);
        check("date dd-MMM-yyyy HH:mm:ss", parse_feed_datetime("05-Jun-2026 14:35:36", disp) != 0);
        check("date dd/MMM/yyyy", parse_feed_datetime("05/Jun/2026", disp) != 0);
        check("date garbage -> 0", parse_feed_datetime("not a date", disp) == 0);
    }

    check("news: RSS publisher date never replaced by arrival / survives cache",
          fincept::services::NewsSourceDateQA::run());

    if (!qEnvironmentVariableIsEmpty("FINCEPT_QA_PUBLIC_RSS_FILE")) {
        check("news: saved real public RSS parsed and dated by ORIGINAL NewsService",
              fincept::services::NewsSourceDateQA::run_public_rss_file());
    }

    std::printf("\nfeed selftest: %s (%d failures)\n", failures == 0 ? "OK" : "FAILED", failures);
    return failures == 0 ? 0 : 1;
}

} // namespace fincept::feeds
