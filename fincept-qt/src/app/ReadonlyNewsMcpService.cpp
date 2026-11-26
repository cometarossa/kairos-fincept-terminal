// Original Fincept F2: isolated read-only NEWS MCP service process.
// No terminal GUI, broker/login bootstrap, Python setup, external MCP child
// managers, network ingest or market as-of assertion. All external calls must
// fail closed when the original news cache is empty or expired.

#include "app/ReadonlyNewsMcpService.h"

#include "core/config/AppPaths.h"
#include "core/config/ProfileManager.h"
#include "mcp/McpProvider.h"
#include "mcp/server/McpHttpServer.h"
#include "mcp/tools/NewsTools.h"
#include "mcp/tools/MarketsTools.h"
#include "services/markets/MarketDataService.h"
#include "services/markets/ReadonlyQuoteInbox.h"
#include "services/screener/ReadonlyScreenerInbox.h"
#include "services/news/NewsService.h"
#include "storage/cache/CacheManager.h"
#include "storage/sqlite/CacheDatabase.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonObject>
#include <QTimer>
#include <QCryptographicHash>
#include <QDateTime>
#include <QJsonDocument>
#include <QUrl>
#include <QXmlStreamReader>
#include <atomic>
#include <memory>

#include <cstdio>
#include <csignal>
#include <utility>

#if defined(Q_OS_UNIX)
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#endif

// Private, production-scoped access to the original parser and cache codec.
// No generic provider API, no synthetic timestamp and no network request.
namespace fincept::services {
struct ReadonlyNewsIngress {
    static QString parse_cnbc(const QByteArray& xml, qint64 now) {
        QXmlStreamReader reader(xml);
        int depth = 0, items = 0;
        bool root = false;
        while (!reader.atEnd()) {
            const auto token = reader.readNext();
            if (token == QXmlStreamReader::DTD || token == QXmlStreamReader::EntityReference)
                return {};
            if (token == QXmlStreamReader::StartElement) {
                if (++depth > 64)
                    return {};
                if (depth == 1) {
                    if (reader.name() != QLatin1String("rss"))
                        return {};
                    root = true;
                }
                if (reader.name() == QLatin1String("item") && ++items > 100)
                    return {};
            } else if (token == QXmlStreamReader::EndElement) {
                --depth;
            }
        }
        if (reader.hasError() || !root || depth != 0 || items < 1)
            return {};
        const RSSFeed feed{"cnbc-f2-ingress", "CNBC public finance",
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
            "MARKETS", "GLOBAL", "CNBC", 2};
        const auto parsed = NewsService::parse_rss_xml(xml, feed);
        if (parsed.size() > 100)
            return {};
        QVector<NewsArticle> selected;
        QSet<QString> seen;
        for (const auto& article : parsed) {
            const QUrl link(article.link, QUrl::StrictMode);
            if (article.publisher_datetime_field != QLatin1String("pubDate") ||
                article.publisher_datetime_ts < now - 86400 ||
                article.publisher_datetime_ts > now + 300 ||
                article.headline.isEmpty() || article.id.isEmpty() ||
                !link.isValid() || link.scheme() != QLatin1String("https") ||
                (link.host() != QLatin1String("www.cnbc.com") && link.host() != QLatin1String("cnbc.com")) ||
                !link.userInfo().isEmpty() || link.port(-1) != -1 ||
                seen.contains(article.id))
                continue;
            seen.insert(article.id);
            selected.append(article);
        }
        return selected.isEmpty() ? QString{} : NewsService::serialize_articles(selected);
    }
};
}

namespace fincept::app {
namespace {

constexpr const char* kAck = "FINCEPT_RESEARCH_ONLY_NO_BROKER_V1";
constexpr const char* kMarkerName = "/.fincept-readonly-service-v1";
constexpr const char* kTokenName = "/mcp.token";
volatile std::sig_atomic_t s_stop_requested = 0;

void handle_term(int) {
    s_stop_requested = 1; // POSIX signal-safe, observed by Qt timer.
}

#if defined(Q_OS_UNIX)
bool private_regular_file(const QString& path, uid_t owner) {
    struct stat st {};
    const QByteArray bytes = QFile::encodeName(path);
    if (::lstat(bytes.constData(), &st) != 0 || !S_ISREG(st.st_mode))
        return false; // Symlinks, devices and sockets are never accepted.
    return st.st_uid == owner && (st.st_mode & 0777) == 0600 &&
           st.st_nlink == 1;
}

bool private_service_home(const QString& path, uid_t owner) {
    struct stat st {};
    const QByteArray bytes = QFile::encodeName(path);
    if (!QDir::isAbsolutePath(path) || path == QLatin1String("/") ||
        ::lstat(bytes.constData(), &st) != 0 || !S_ISDIR(st.st_mode))
        return false;
    return st.st_uid == owner && (st.st_mode & 0777) == 0700 &&
           QDir(path).canonicalPath() == QDir::cleanPath(path);
}
#endif

void diagnostic(const char* code) {
    // Fixed codes only: never print the token, home, feed data or credentials.
    std::fprintf(stderr, "%s\n", code);
    std::fflush(stderr);
}

#if defined(Q_OS_UNIX)
// The file is written atomically by a separately admitted local capturer.
// Its hash detects corruption, not independent publisher truth or attestation.
constexpr qint64 kSnapshotTtl = 600;
constexpr qint64 kMaxEnvelope = 250000;
constexpr auto kIngressAck = "CNBC_SNAPSHOT_V1";
constexpr auto kSourceUrl =
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114";

class SnapshotInbox {
  public:
    explicit SnapshotInbox(QString directory) : directory_(std::move(directory)) {}

    qint64 expires_at() const { return expires_.load(); }

    bool ready() const {
        return expires_at() > QDateTime::currentSecsSinceEpoch();
    }

    void refresh() {
        if (!private_service_home(directory_, ::geteuid())) {
            deny();
            return;
        }
        const auto path = QFile::encodeName(directory_ + QLatin1String("/snapshot.json"));
        const int fd = ::open(path.constData(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0) {
            deny();
            return;
        }
        struct stat st {};
        if (::fstat(fd, &st) != 0 || !S_ISREG(st.st_mode) ||
            st.st_uid != ::geteuid() || (st.st_mode & 0777) != 0600 ||
            st.st_nlink != 1 || st.st_size <= 0 || st.st_size > kMaxEnvelope) {
            ::close(fd);
            deny();
            return;
        }
        QFile file;
        if (!file.open(fd, QIODevice::ReadOnly, QFileDevice::AutoCloseHandle)) {
            ::close(fd);
            deny();
            return;
        }
        const QByteArray raw = file.read(kMaxEnvelope + 1);
        QJsonParseError error;
        const auto doc = QJsonDocument::fromJson(raw, &error);
        if (raw.size() > kMaxEnvelope || error.error != QJsonParseError::NoError || !doc.isObject()) {
            deny();
            return;
        }
        const auto envelope = doc.object();
        const auto now = QDateTime::currentSecsSinceEpoch();
        const auto captured = envelope.value("captured_at_unix").toInteger(-1);
        const QByteArray encoded = envelope.value("rss_base64").toString().toLatin1();
        const QByteArray xml = QByteArray::fromBase64(encoded);
        const QByteArray digest = QCryptographicHash::hash(xml, QCryptographicHash::Sha256).toHex();
        if (envelope.size() != 5 || envelope.value("schema").toString() != QLatin1String(kIngressAck) ||
            envelope.value("source_url").toString() != QLatin1String(kSourceUrl) ||
            captured <= 0 || captured > now || captured <= now - kSnapshotTtl ||
            xml.isEmpty() || xml.size() > 180000 || xml.toBase64() != encoded ||
            envelope.value("rss_sha256").toString().toLatin1() != digest ||
            captured < last_capture_ || (captured == last_capture_ && digest != last_digest_)) {
            deny();
            return;
        }
        if (captured == last_capture_)
            return; // Same capture never extends expiry or re-admits after invalidation.
        const QString payload = fincept::services::ReadonlyNewsIngress::parse_cnbc(xml, now);
        const auto remaining = captured + kSnapshotTtl - QDateTime::currentSecsSinceEpoch();
        if (payload.isEmpty() || remaining <= 0) {
            deny();
            return;
        }
        auto& cache = fincept::CacheManager::instance();
        expires_.store(0);
        cache.put("news:articles", payload, static_cast<int>(remaining), "f2_public_rss_ingress");
        if (cache.get("news:articles").toString() != payload) {
            deny();
            return;
        }
        last_capture_ = captured;
        last_digest_ = digest;
        expires_.store(captured + kSnapshotTtl);
        diagnostic("FINCEPT_F2_INGRESS_ACCEPTED");
    }

  private:
    void deny() {
        if (expires_.exchange(0) != 0)
            diagnostic("FINCEPT_F2_INGRESS_UNAVAILABLE");
        fincept::CacheManager::instance().remove("news:articles");
    }
    QString directory_;
    qint64 last_capture_ = 0;
    QByteArray last_digest_;
    std::atomic<qint64> expires_{0};
};
#endif

} // namespace

int run_readonly_news_mcp_service(int argc, char* argv[]) {
#if !defined(Q_OS_UNIX)
    (void)argc;
    (void)argv;
    diagnostic("FINCEPT_F2_UNSUPPORTED_PLATFORM");
    return 2;
#else
    if (argc != 2 || ::geteuid() == 0 || ::getuid() != ::geteuid() ||
        qgetenv("FINCEPT_READONLY_NEWS_SERVICE_ACK") != kAck) {
        diagnostic("FINCEPT_F2_DENIED_NO_EXPLICIT_OPERATOR_GATE");
        return 2;
    }
    const QString home = QString::fromUtf8(qgetenv("HOME"));
    if (!private_service_home(home, ::geteuid()) ||
        QString::fromUtf8(qgetenv("FINCEPT_READONLY_NEWS_SERVICE_HOME")) != home) {
        diagnostic("FINCEPT_F2_DENIED_UNISOLATED_PROFILE");
        return 2;
    }
    const QString marker_path = home + QLatin1String(kMarkerName);
    const QString token_path = home + QLatin1String(kTokenName);
    if (!private_regular_file(marker_path, ::geteuid()) ||
        !private_regular_file(token_path, ::geteuid())) {
        diagnostic("FINCEPT_F2_DENIED_UNSAFE_CREDENTIAL_FILES");
        return 2;
    }
    QFile marker(marker_path);
    QFile credential(token_path);
    if (!marker.open(QIODevice::ReadOnly) || marker.read(128).trimmed() != kAck ||
        !credential.open(QIODevice::ReadOnly)) {
        diagnostic("FINCEPT_F2_DENIED_INVALID_GATE_FILES");
        return 2;
    }
    const QByteArray token_bytes = credential.read(130).trimmed();
    credential.close();
    const QString token = QString::fromLatin1(token_bytes);
    // No arbitrary Unicode, whitespace or weak tokens. The original server
    // rechecks the token, and never persists it to SecureStorage.
    if (token.size() < 64 || token.size() > 128 ||
        token_bytes.size() != token.size()) {
        diagnostic("FINCEPT_F2_DENIED_INVALID_TOKEN");
        return 2;
    }
    bool port_ok = false;
    const int port = QString::fromLatin1(qgetenv("FINCEPT_READONLY_NEWS_MCP_PORT"))
                         .toInt(&port_ok);
    if (!port_ok || port < 1024 || port > 65535) {
        diagnostic("FINCEPT_F2_DENIED_INVALID_PORT");
        return 2;
    }
    QCoreApplication app(argc, argv);
    QCoreApplication::setApplicationName(QStringLiteral("FinceptReadonlyNews"));
    QCoreApplication::setOrganizationName(QStringLiteral("Fincept"));
    fincept::ProfileManager::instance().set_active(QStringLiteral("f2_readonly_news"));
    fincept::AppPaths::ensure_all();

    // Original cache only. No Database::open, no TerminalShell, no GUI auth,
    // no McpService::initialize, no McpManager external child processes, no
    // MarketDataService provider, no broker or network feed bootstrap.
    auto opened = fincept::CacheDatabase::instance().open(
        fincept::AppPaths::data() + QStringLiteral("/cache.db"));
    if (opened.is_err()) {
        diagnostic("FINCEPT_F2_CACHE_OPEN_FAILED");
        return 1;
    }
    auto& news = fincept::services::NewsService::instance();
    news.enforce_cache_only_mode();

    // Opt-in only. The default installed cache-only service is unchanged.
    const auto ingress_ack = qgetenv("FINCEPT_READONLY_NEWS_INGRESS_ACK");
    std::shared_ptr<SnapshotInbox> inbox;
    QTimer ingress_poll;
    if (!ingress_ack.isEmpty()) {
        const QString directory = home + QLatin1String("/ingress");
        if (ingress_ack != kIngressAck || !private_service_home(directory, ::geteuid())) {
            diagnostic("FINCEPT_F2_DENIED_INGRESS_CONFIGURATION");
            fincept::CacheDatabase::instance().close();
            return 2;
        }
        // Never inherit previously seeded or synthetic cache when inbox mode starts.
        fincept::CacheManager::instance().remove("news:articles");
        inbox = std::make_shared<SnapshotInbox>(directory);
        inbox->refresh();
        ingress_poll.setInterval(5000);
        QObject::connect(&ingress_poll, &QTimer::timeout, &app, [inbox]() { inbox->refresh(); });
        ingress_poll.start();
    }

    // Expose EXACTLY the existing, original read-only get_news tool.
    // Its handler is wrapped only to reject force-refresh and no-cache; the
    // original NewsService independently denies network even in TOCTOU races.
    auto definitions = fincept::mcp::tools::get_news_tools();
    bool registered = false;
    for (auto& tool : definitions) {
        if (tool.name != QLatin1String("get_news"))
            continue;
        if (tool.is_destructive || tool.auth_required != fincept::mcp::AuthLevel::None ||
            !tool.handler || registered) {
            diagnostic("FINCEPT_F2_DENIED_ORIGINAL_TOOL_POLICY_DRIFT");
            fincept::CacheDatabase::instance().close();
            return 1;
        }
        tool.input_schema.properties.insert("include_local_snapshot_provenance", QJsonObject{
            {"type", "boolean"}, {"default", false}, {"description", "Local F2 inbox expiry, not market freshness"}});
        auto original_handler = std::move(tool.handler);
        tool.handler = [original_handler, inbox](const QJsonObject& args) -> fincept::mcp::ToolResult {
            const bool evidence = args.value("include_local_snapshot_provenance").toBool(false);
            const auto before = inbox ? inbox->expires_at() : 0;
            if ((inbox && !inbox->ready()) || (evidence && before <= QDateTime::currentSecsSinceEpoch()) ||
                args.value(QStringLiteral("force")).toBool(false) ||
                fincept::CacheManager::instance().get(QStringLiteral("news:articles")).isNull())
                return fincept::mcp::ToolResult::fail(QStringLiteral("FINCEPT_UNAVAILABLE"));
            auto result = original_handler(args);
            if (!evidence || !result.success)
                return result;
            // Refresh clears expiry before replacing cache and never re-admits
            // the same capture. Reject if a different generation intervened.
            if (!inbox || inbox->expires_at() != before || before <= QDateTime::currentSecsSinceEpoch() ||
                !result.data.isObject())
                return fincept::mcp::ToolResult::fail(QStringLiteral("FINCEPT_UNAVAILABLE"));
            auto data = result.data.toObject();
            data.insert("local_snapshot_provenance", QJsonObject{
                {"captured_at_unix", before - kSnapshotTtl}, {"valid_until_unix", before},
                {"local_clock_verified", false}, {"market_as_of_verified", false}});
            result.data = data;
            return result;
        };
        fincept::mcp::McpProvider::instance().register_tool(std::move(tool));
        registered = true;
    }
    if (!registered || fincept::mcp::McpProvider::instance().tool_count() != 1) {
        diagnostic("FINCEPT_F2_DENIED_TOOL_CATALOGUE_DRIFT");
        fincept::CacheDatabase::instance().close();
        return 1;
    }

    // Explicit second allowlisted original read-only tool. Default news-only
    // catalogue above remains unchanged without this separate opt-in.
    const auto history_ack = qgetenv("FINCEPT_READONLY_HISTORY_INGRESS_ACK");
    std::size_t expected_tools = 1;
    if (!history_ack.isEmpty()) {
        const QString directory = home + QLatin1String("/history-ingress");
        const bool long_window = history_ack == "DUAL_WINDOW_YAHOO_HISTORY_SNAPSHOT_V1";
        const bool multi_asset = long_window || history_ack == "MULTI_YAHOO_HISTORY_SNAPSHOT_V1";
        if ((!multi_asset && history_ack != "SPY_YAHOO_HISTORY_SNAPSHOT_V1") ||
            !private_service_home(directory, ::geteuid()) ||
            !fincept::services::MarketDataService::instance().configure_readonly_history_inbox(directory)) {
            diagnostic("FINCEPT_F2_DENIED_HISTORY_CONFIGURATION");
            fincept::mcp::McpProvider::instance().clear();
            fincept::CacheDatabase::instance().close();
            return 2;
        }
        bool history_registered = false;
        for (auto& tool : fincept::mcp::tools::get_markets_tools()) {
            if (tool.name != QLatin1String("get_history"))
                continue;
            if (history_registered || tool.is_destructive ||
                tool.auth_required != fincept::mcp::AuthLevel::None || !tool.handler)
                break;
            tool.input_schema.properties.insert("include_local_snapshot_provenance", QJsonObject{
                {"type", "boolean"}, {"default", false}, {"description", "Local F2 inbox expiry, not market freshness"}});
            auto original = std::move(tool.handler);
            tool.handler = [original, multi_asset, long_window](const QJsonObject& args) -> fincept::mcp::ToolResult {
                const auto symbol = args.value("symbol").toString();
                const auto period = args.value("period").toString();
                const bool allowed_window = period == QLatin1String("5d") ||
                    (long_window && period == QLatin1String("6mo") &&
                     (symbol == QLatin1String("SPY") || symbol == QLatin1String("EURUSD=X")));
                if (!fincept::services::MarketDataService::readonly_history_symbol_allowed(args.value("symbol").toString(), multi_asset) ||
                    !allowed_window ||
                    args.value("interval").toString() != QLatin1String("1d"))
                    return fincept::mcp::ToolResult::fail(QStringLiteral("FINCEPT_UNAVAILABLE"));
                return original(args);
            };
            fincept::mcp::McpProvider::instance().register_tool(std::move(tool));
            history_registered = true;
        }
        expected_tools = 2;
        if (!history_registered || fincept::mcp::McpProvider::instance().tool_count() != expected_tools) {
            diagnostic("FINCEPT_F2_DENIED_HISTORY_TOOL_CATALOGUE_DRIFT");
            fincept::mcp::McpProvider::instance().clear();
            fincept::CacheDatabase::instance().close();
            return 1;
        }
    }

    // Separately opt in to exactly one original cache-only quote handler.
    const auto quote_ack = qgetenv("FINCEPT_READONLY_QUOTE_INGRESS_ACK");
    if (!quote_ack.isEmpty()) {
        const QString directory = home + QLatin1String("/quote-ingress");
        if (quote_ack != "PUBLIC_YAHOO_QUOTE_RESEARCH_V1" ||
            !private_service_home(directory, ::geteuid()) ||
            !fincept::services::MarketDataService::instance().configure_readonly_quote_inbox(directory)) {
            diagnostic("FINCEPT_F2_DENIED_QUOTE_CONFIGURATION");
            fincept::mcp::McpProvider::instance().clear();
            fincept::CacheDatabase::instance().close();
            return 2;
        }
        bool quote_registered = false;
        for (auto& tool : fincept::mcp::tools::get_markets_tools()) {
            if (tool.name != QLatin1String("get_quote")) continue;
            if (quote_registered || tool.is_destructive ||
                tool.auth_required != fincept::mcp::AuthLevel::None || !tool.handler) break;
            auto original = std::move(tool.handler);
            tool.description = "Read a short-lived public Yahoo research quote from a private inbox; provider time is unverified, no trading or refresh.";
            tool.handler = [original](const QJsonObject& args) -> fincept::mcp::ToolResult {
                if (args.size() != 1 || !args.value("symbol").isString() ||
                    !fincept::services::readonly_quote::allowed(args.value("symbol").toString()))
                    return fincept::mcp::ToolResult::fail(QStringLiteral("FINCEPT_UNAVAILABLE"));
                return original(args);
            };
            fincept::mcp::McpProvider::instance().register_tool(std::move(tool));
            quote_registered = true;
        }
        ++expected_tools;
        if (!quote_registered || fincept::mcp::McpProvider::instance().tool_count() != expected_tools) {
            diagnostic("FINCEPT_F2_DENIED_QUOTE_TOOL_CATALOGUE_DRIFT");
            fincept::mcp::McpProvider::instance().clear();
            fincept::CacheDatabase::instance().close();
            return 1;
        }
    }

    // Explicit, local inbox only. No ScreenerService::run, Python launch or provider refresh.
    const auto screener_ack = qgetenv("FINCEPT_READONLY_SCREENER_INGRESS_ACK");
    if (!screener_ack.isEmpty()) {
        const QString directory = home + QLatin1String("/screener-ingress");
        if (screener_ack != "FINCEPT_SCREENER_INBOX_V1" || !private_service_home(directory, ::geteuid())) {
            diagnostic("FINCEPT_F2_DENIED_SCREENER_CONFIGURATION");
            fincept::mcp::McpProvider::instance().clear();
            fincept::CacheDatabase::instance().close();
            return 2;
        }
        fincept::mcp::ToolDef tool;
        tool.name = "get_screener";
        tool.description = "Read one locally captured day_gainers screen, max 20 USD rows. Research only; no refresh or trade authority.";
        tool.category = "market-data";
        tool.input_schema.properties = QJsonObject{
            {"screen_id", QJsonObject{{"type", "string"}, {"enum", QJsonArray{"day_gainers"}}}},
            {"limit", QJsonObject{{"type", "integer"}, {"enum", QJsonArray{20}}}}};
        tool.input_schema.required = {"screen_id", "limit"};
        tool.auth_required = fincept::mcp::AuthLevel::None;
        tool.is_destructive = false;
        tool.handler = [directory](const QJsonObject& args) -> fincept::mcp::ToolResult {
            using namespace fincept::services::readonly_screener;
            if (!request_allowed(args))
                return fincept::mcp::ToolResult::fail(QStringLiteral("FINCEPT_UNAVAILABLE"));
            const auto snapshot = read(directory, QDateTime::currentSecsSinceEpoch());
            if (!snapshot)
                return fincept::mcp::ToolResult::fail(QStringLiteral("FINCEPT_UNAVAILABLE"));
            return fincept::mcp::ToolResult::ok_data(*snapshot);
        };
        fincept::mcp::McpProvider::instance().register_tool(std::move(tool));
        ++expected_tools;
        if (fincept::mcp::McpProvider::instance().tool_count() != expected_tools) {
            diagnostic("FINCEPT_F2_DENIED_SCREENER_TOOL_CATALOGUE_DRIFT");
            fincept::mcp::McpProvider::instance().clear();
            fincept::CacheDatabase::instance().close();
            return 1;
        }
    }

    auto& server = fincept::mcp::McpHttpServer::instance();
    if (!server.configure_readonly_news_service(static_cast<quint16>(port), token) ||
        !server.start() || server.allow_actions() ||
        server.port() != static_cast<quint16>(port)) {
        diagnostic("FINCEPT_F2_MCP_START_DENIED");
        server.stop();
        fincept::mcp::McpProvider::instance().clear();
        fincept::CacheDatabase::instance().close();
        return 1;
    }
    // The only signal handler action is an atomic flag. Qt closes the listener
    // on its own main thread with a bounded timer; never handle Qt in signals.
    s_stop_requested = 0;
    const auto previous_term = std::signal(SIGTERM, handle_term);
    const auto previous_int = std::signal(SIGINT, handle_term);
    QTimer stop_poll;
    stop_poll.setInterval(100);
    QObject::connect(&stop_poll, &QTimer::timeout, &app, [&]() {
        if (s_stop_requested)
            app.quit();
    });
    stop_poll.start();
    std::printf("FINCEPT_F2_READONLY_NEWS_READY port=%u tools=%zu actions=false provider_egress=false\n",
                static_cast<unsigned>(server.port()), expected_tools);
    std::fflush(stdout);
    const int rc = app.exec();
    stop_poll.stop();
    ingress_poll.stop();
    server.stop();
    fincept::mcp::McpProvider::instance().clear();
    fincept::CacheDatabase::instance().close();
    std::signal(SIGTERM, previous_term);
    std::signal(SIGINT, previous_int);
    diagnostic("FINCEPT_F2_READONLY_NEWS_STOPPED");
    return rc;
#endif
}
} // namespace fincept::app
