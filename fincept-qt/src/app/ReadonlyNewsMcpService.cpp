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
#include "services/news/NewsService.h"
#include "storage/cache/CacheManager.h"
#include "storage/sqlite/CacheDatabase.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonObject>
#include <QTimer>

#include <cstdio>
#include <csignal>
#include <utility>

#if defined(Q_OS_UNIX)
#include <sys/stat.h>
#include <unistd.h>
#endif

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
        auto original_handler = std::move(tool.handler);
        tool.handler = [original_handler](const QJsonObject& args) -> fincept::mcp::ToolResult {
            if (args.value(QStringLiteral("force")).toBool(false) ||
                fincept::CacheManager::instance().get(QStringLiteral("news:articles")).isNull())
                return fincept::mcp::ToolResult::fail(QStringLiteral("FINCEPT_UNAVAILABLE"));
            return original_handler(args);
        };
        fincept::mcp::McpProvider::instance().register_tool(std::move(tool));
        registered = true;
    }
    if (!registered || fincept::mcp::McpProvider::instance().tool_count() != 1) {
        diagnostic("FINCEPT_F2_DENIED_TOOL_CATALOGUE_DRIFT");
        fincept::CacheDatabase::instance().close();
        return 1;
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
    std::printf("FINCEPT_F2_READONLY_NEWS_READY port=%u tools=1 actions=false provider_egress=false\n",
                static_cast<unsigned>(server.port()));
    std::fflush(stdout);
    const int rc = app.exec();
    stop_poll.stop();
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
