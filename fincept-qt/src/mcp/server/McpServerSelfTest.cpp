// McpServerSelfTest.cpp — see McpServerSelfTest.h.

#include "mcp/server/McpServerSelfTest.h"

#include "mcp/McpInit.h"
#include "mcp/McpProvider.h"
#include "mcp/server/EssentialTools.h"
#include "mcp/server/McpHttpServer.h"
#include "services/markets/MarketDataService.h"
#include "services/markets/HistoryIntegrity.h"
#include "storage/cache/CacheManager.h"
#include "storage/sqlite/CacheDatabase.h"

#include <QElapsedTimer>
#include <QEventLoop>
#include <QFileInfo>
#include <QProcess>
#include <QProcessEnvironment>
#include <QHash>
#include <QHostAddress>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRandomGenerator>
#include <QRegularExpression>
#include <QSet>
#include <QTcpSocket>
#include <QTimer>

#include <algorithm>
#include <cstdio>
#include <functional>

namespace fincept::mcp {

namespace mcp_server_selftest_detail {

using HeaderList = QList<QPair<QByteArray, QByteArray>>;

void out(const QString& line) {
    std::fprintf(stdout, "%s\n", line.toUtf8().constData());
    std::fflush(stdout);
}

QString clip(const QString& s, int max_chars = 90) {
    const QString flat = s.simplified();
    return flat.size() <= max_chars ? flat : flat.left(max_chars) + QStringLiteral("…");
}

struct Report {
    int pass = 0;
    int fail = 0;
    void check(bool ok, const QString& what, const QString& detail = {}) {
        if (ok)
            ++pass;
        else
            ++fail;
        out(QStringLiteral("  [%1] %2%3")
                .arg(ok ? QStringLiteral("PASS") : QStringLiteral("FAIL"), what,
                     detail.isEmpty() ? QString() : QStringLiteral("  (") + detail + QLatin1Char(')')));
    }
};

/// Run the event loop until `done()` or the timeout. The self-test runs before
/// QApplication::exec(), so this is the only loop serving the server's sockets.
bool pump_until(const std::function<bool()>& done, int timeout_ms) {
    QElapsedTimer timer;
    timer.start();
    while (!done()) {
        if (timer.elapsed() > timeout_ms)
            return false;
        QEventLoop loop;
        QTimer::singleShot(5, &loop, &QEventLoop::quit);
        loop.exec();
    }
    return true;
}

struct HttpReply {
    bool ok = false; // a complete response arrived
    int status = 0;
    QHash<QByteArray, QByteArray> headers; // lower-case names
    QByteArray body;
};

QByteArray to_json_bytes(const QJsonObject& o) {
    return QJsonDocument(o).toJson(QJsonDocument::Compact);
}

bool connect_socket(QTcpSocket& sock, quint16 port) {
    sock.connectToHost(QHostAddress::LocalHost, port);
    return pump_until([&sock]() { return sock.state() == QAbstractSocket::ConnectedState; }, 5000);
}

/// Send `raw` on an open socket and read exactly one Content-Length-framed response.
HttpReply exchange(QTcpSocket& sock, const QByteArray& raw, int timeout_ms = 15000) {
    HttpReply r;
    QByteArray buf;
    qsizetype body_start = -1;
    qint64 need = -1;
    sock.write(raw);
    const bool done = pump_until(
        [&]() {
            buf += sock.readAll();
            if (body_start < 0) {
                const qsizetype end = buf.indexOf("\r\n\r\n");
                if (end < 0)
                    return false;
                body_start = end + 4;
                const QList<QByteArray> lines = buf.left(end).split('\n');
                r.status = lines.value(0).trimmed().split(' ').value(1).toInt();
                for (qsizetype i = 1; i < lines.size(); ++i) {
                    const QByteArray line = lines.at(i).trimmed();
                    const qsizetype colon = line.indexOf(':');
                    if (colon > 0)
                        r.headers.insert(line.left(colon).trimmed().toLower(), line.mid(colon + 1).trimmed());
                }
                need = r.headers.value("content-length", "-1").toLongLong();
            }
            if (need >= 0)
                return buf.size() - body_start >= need;
            return sock.state() == QAbstractSocket::UnconnectedState;
        },
        timeout_ms);
    if (body_start >= 0)
        r.body = need >= 0 ? buf.mid(body_start, need) : buf.mid(body_start);
    r.ok = done && body_start >= 0;
    return r;
}

QByteArray build_request(const QByteArray& method, const QByteArray& path, quint16 port, const HeaderList& headers,
                         const QByteArray& body, bool keep_alive = false) {
    QByteArray raw = method + ' ' + path + " HTTP/1.1\r\n";
    bool has_host = false;
    for (const auto& h : headers) {
        if (h.first.toLower() == "host")
            has_host = true;
        raw += h.first + ": " + h.second + "\r\n";
    }
    if (!has_host)
        raw += "Host: 127.0.0.1:" + QByteArray::number(port) + "\r\n";
    if (!body.isEmpty() || method == "POST")
        raw += "Content-Length: " + QByteArray::number(body.size()) + "\r\n";
    raw += keep_alive ? "Connection: keep-alive\r\n" : "Connection: close\r\n";
    raw += "\r\n";
    raw += body;
    return raw;
}

HttpReply http_request(quint16 port, const QByteArray& method, const QByteArray& path, const HeaderList& headers,
                       const QByteArray& body = {}) {
    QTcpSocket sock;
    if (!connect_socket(sock, port))
        return {};
    HttpReply r = exchange(sock, build_request(method, path, port, headers, body));
    sock.abort();
    return r;
}

HeaderList auth_headers(const QString& token) {
    return {{QByteArrayLiteral("Authorization"), QByteArrayLiteral("Bearer ") + token.toUtf8()},
            {QByteArrayLiteral("Content-Type"), QByteArrayLiteral("application/json")},
            {QByteArrayLiteral("Accept"), QByteArrayLiteral("application/json, text/event-stream")},
            {QByteArrayLiteral("MCP-Protocol-Version"), QByteArrayLiteral("2025-06-18")}};
}

struct RpcReply {
    HttpReply http;
    QJsonDocument doc;
};

RpcReply rpc(quint16 port, const QString& token, const QJsonDocument& message) {
    RpcReply r;
    r.http = http_request(port, "POST", "/mcp", auth_headers(token), message.toJson(QJsonDocument::Compact));
    r.doc = QJsonDocument::fromJson(r.http.body);
    return r;
}

QJsonObject request(const QString& method, int id, const QJsonObject& params = {}) {
    QJsonObject m{{QStringLiteral("jsonrpc"), QStringLiteral("2.0")},
                  {QStringLiteral("id"), id},
                  {QStringLiteral("method"), method}};
    if (!params.isEmpty())
        m.insert(QStringLiteral("params"), params);
    return m;
}

QJsonObject call_tool(quint16 port, const QString& token, const QString& name, const QJsonObject& args, int id) {
    const QJsonObject params{{QStringLiteral("name"), name}, {QStringLiteral("arguments"), args}};
    return rpc(port, token, QJsonDocument(request(QStringLiteral("tools/call"), id, params))).doc.object();
}

QString first_text(const QJsonObject& call_result) {
    return call_result.value(QStringLiteral("content")).toArray().at(0).toObject().value(QStringLiteral("text")).toString();
}

int error_code(const QJsonDocument& doc) {
    return doc.object().value(QStringLiteral("error")).toObject().value(QStringLiteral("code")).toInt();
}

} // namespace mcp_server_selftest_detail

int run_mcp_server_selftest() {
    using namespace mcp_server_selftest_detail;
    QElapsedTimer total;
    total.start();
    out(QStringLiteral("\n══════════════════════════════════════════════════════════════"));
    out(QStringLiteral("  MCP SERVER SELF-TEST (external agents · Streamable HTTP)"));
    out(QStringLiteral("══════════════════════════════════════════════════════════════"));
    Report rep;
    static const QRegularExpression name_rx(QStringLiteral("^[a-zA-Z0-9_-]{1,50}$"));

    // main() defers initialize_all_tools() to the first event-loop turn; give it that turn.
    auto& provider = McpProvider::instance();
    if (provider.tool_count() == 0)
        pump_until([&provider]() { return provider.tool_count() > 0; }, 8000);
    if (provider.tool_count() == 0)
        initialize_all_tools();
    rep.check(provider.tool_count() > 0, QStringLiteral("internal tool catalogue registered"),
              QStringLiteral("%1 tools").arg(provider.tool_count()));

    auto& server = McpHttpServer::instance();
    server.stop(); // in case "start with the terminal" already started it on the real port
    const QString token = QString::number(QRandomGenerator::system()->generate64(), 16) +
                          QString::number(QRandomGenerator::system()->generate64(), 16);
    server.set_selftest_overrides(0, token, /*allow_actions=*/false);
    const bool started = server.start();
    const quint16 port = server.port();
    rep.check(started && server.is_running() && port != 0, QStringLiteral("listens on an OS-assigned loopback port"),
              server.url());
    if (!started || port == 0) {
        server.clear_selftest_overrides();
        out(QStringLiteral("  ABORT: %1").arg(server.last_error()));
        return 1;
    }
    rep.check(server.url() == QStringLiteral("http://127.0.0.1:%1/mcp").arg(port),
              QStringLiteral("url() reports the bound port"));

    // ── /health ──
    {
        const HttpReply r = http_request(port, "GET", "/health", {});
        const QJsonObject o = QJsonDocument::fromJson(r.body).object();
        rep.check(r.ok && r.status == 200 && o.value(QStringLiteral("ok")).toBool() &&
                      o.value(QStringLiteral("name")).toString() == QLatin1String("fincept-terminal"),
                  QStringLiteral("GET /health answers without a token"), QString::number(r.status));
    }

    // ── initialize / notifications ──
    {
        const QJsonObject client{{QStringLiteral("name"), QStringLiteral("fincept-selftest")},
                                 {QStringLiteral("version"), QStringLiteral("1.0")}};
        const RpcReply r = rpc(port, token,
                               QJsonDocument(request(QStringLiteral("initialize"), 1,
                                                     {{QStringLiteral("protocolVersion"), QStringLiteral("2025-06-18")},
                                                      {QStringLiteral("capabilities"), QJsonObject{}},
                                                      {QStringLiteral("clientInfo"), client}})));
        const QJsonObject res = r.doc.object().value(QStringLiteral("result")).toObject();
        rep.check(r.http.status == 200 &&
                      res.value(QStringLiteral("protocolVersion")).toString() == QLatin1String("2025-06-18") &&
                      res.value(QStringLiteral("serverInfo")).toObject().value(QStringLiteral("name")).toString() ==
                          QLatin1String("fincept-terminal") &&
                      res.value(QStringLiteral("capabilities")).toObject().contains(QStringLiteral("tools")) &&
                      !res.value(QStringLiteral("instructions")).toString().isEmpty(),
                  QStringLiteral("initialize negotiates 2025-06-18 and describes the server"));
        const RpcReply older = rpc(port, token,
                                   QJsonDocument(request(QStringLiteral("initialize"), 2,
                                                         {{QStringLiteral("protocolVersion"),
                                                           QStringLiteral("2024-11-05")},
                                                          {QStringLiteral("clientInfo"), client}})));
        rep.check(older.doc.object().value(QStringLiteral("result")).toObject().value(QStringLiteral("protocolVersion"))
                          .toString() == QLatin1String("2024-11-05"),
                  QStringLiteral("initialize echoes an older supported protocol version"));
        const RpcReply future = rpc(
            port, token,
            QJsonDocument(request(QStringLiteral("initialize"), 3,
                                  {{QStringLiteral("protocolVersion"), QStringLiteral("2099-01-01")}})));
        rep.check(future.doc.object().value(QStringLiteral("result")).toObject().value(QStringLiteral("protocolVersion"))
                          .toString() == QLatin1String("2025-06-18"),
                  QStringLiteral("initialize answers 2025-06-18 to an unknown version"));
        rep.check(server.connected_client_count() >= 1, QStringLiteral("connected_client_count() counts the client"),
                  QString::number(server.connected_client_count()));
        const RpcReply note = rpc(port, token,
                                  QJsonDocument(QJsonObject{{QStringLiteral("jsonrpc"), QStringLiteral("2.0")},
                                                            {QStringLiteral("method"),
                                                             QStringLiteral("notifications/initialized")}}));
        rep.check(note.http.status == 202 && note.http.body.isEmpty(),
                  QStringLiteral("notification → 202 with an empty body"), QString::number(note.http.status));
    }

    // ── tools/list ──
    {
        const RpcReply r = rpc(port, token, QJsonDocument(request(QStringLiteral("tools/list"), 4)));
        const QJsonObject res = r.doc.object().value(QStringLiteral("result")).toObject();
        const QJsonArray tools = res.value(QStringLiteral("tools")).toArray();
        QSet<QString> listed;
        bool names_ok = !tools.isEmpty();
        bool schemas_ok = true;
        bool read_only = true;
        for (const QJsonValue& v : tools) {
            const QJsonObject t = v.toObject();
            const QString name = t.value(QStringLiteral("name")).toString();
            listed.insert(name);
            names_ok = names_ok && name_rx.match(name).hasMatch();
            const QJsonObject schema = t.value(QStringLiteral("inputSchema")).toObject();
            schemas_ok = schemas_ok && schema.value(QStringLiteral("type")).toString() == QLatin1String("object") &&
                         schema.value(QStringLiteral("properties")).isObject();
            read_only = read_only &&
                        !t.value(QStringLiteral("annotations")).toObject().value(QStringLiteral("destructiveHint")).toBool();
        }
        rep.check(r.http.status == 200 && !tools.isEmpty(), QStringLiteral("tools/list returns the essentials"),
                  QStringLiteral("%1 tools").arg(tools.size()));
        rep.check(names_ok, QStringLiteral("every advertised name matches ^[a-zA-Z0-9_-]{1,50}$"));
        rep.check(schemas_ok, QStringLiteral("every inputSchema is an object schema with properties"));
        rep.check(read_only, QStringLiteral("essentials advertise no destructive tool"));
        QStringList missing;
        for (const QString& meta : essential_meta_tool_names()) {
            if (provider.has_tool(meta) && provider.is_tool_enabled(meta) && !listed.contains(meta))
                missing << meta;
        }
        rep.check(missing.isEmpty(), QStringLiteral("every registered meta tool is advertised"), missing.join(QStringLiteral(", ")));
    }

    // Deterministic picks from the live catalogue.
    auto catalogue = provider.list_tools();
    std::sort(catalogue.begin(), catalogue.end(),
              [](const UnifiedTool& a, const UnifiedTool& b) { return a.name < b.name; });
    QString destructive_tool;
    QString live_read_tool;
    for (const auto& t : catalogue) {
        if (destructive_tool.isEmpty() && t.is_destructive && t.category != QLatin1String("live-trading"))
            destructive_tool = t.name;
        if (live_read_tool.isEmpty() && !t.is_destructive && t.category == QLatin1String("live-trading"))
            live_read_tool = t.name;
    }
    if (provider.has_tool(QStringLiteral("delete_watchlist")))
        destructive_tool = QStringLiteral("delete_watchlist"); // harmless even if the policy were broken

    // ── tools/call ──
    {
        const QJsonObject res = call_tool(port, token, QStringLiteral("tool_list"),
                                          {{QStringLiteral("query"), QStringLiteral("latest stock quote")},
                                           {QStringLiteral("top_k"), 3}},
                                          5)
                                    .value(QStringLiteral("result"))
                                    .toObject();
        rep.check(!res.value(QStringLiteral("isError")).toBool(true) && !first_text(res).isEmpty() &&
                      res.value(QStringLiteral("structuredContent")).toObject().contains(QStringLiteral("tools")),
                  QStringLiteral("tools/call tool_list returns content + structuredContent"), clip(first_text(res)));
    }
    // Provider response integrity: the same strict decoder used by the
    // production MarketDataService must never normalize invalid data to zero.
    // This is structural QA only; it does not certify source timestamps.
    {
        namespace integrity = fincept::services::history_integrity;
        const qint64 test_now = 1704412800; // 2024-01-05 UTC, deterministic
        const QJsonObject a{{"timestamp", 1704067200}, {"open", 100.0}, {"high", 105.0},
                            {"low", 99.0}, {"close", 103.0}, {"volume", 1000}};
        const QJsonObject b{{"timestamp", 1704153600}, {"open", 103.0}, {"high", 108.0},
                            {"low", 102.0}, {"close", 107.0}, {"volume", 1250}};
        const auto decode = [test_now](const QJsonArray& bars) {
            return integrity::decode(QJsonDocument(bars), test_now);
        };
        const auto valid = decode(QJsonArray{a, b});
        rep.check(valid.has_value() && valid->size() == 2 && valid->at(1).close == 107.0,
                  QStringLiteral("provider history integrity accepts valid OHLCV UTC bars"));
        QJsonObject missing_close = a;
        missing_close.remove(QStringLiteral("close"));
        rep.check(!decode(QJsonArray{missing_close}).has_value(),
                  QStringLiteral("provider history integrity rejects missing close"));
        QJsonObject missing_volume = a;
        missing_volume.insert(QStringLiteral("volume"), QJsonValue::Null);
        rep.check(!decode(QJsonArray{missing_volume}).has_value(),
                  QStringLiteral("provider history integrity rejects unknown volume, not zero"));
        rep.check(!decode(QJsonArray{a, a}).has_value(),
                  QStringLiteral("provider history integrity rejects duplicate timestamp"));
        rep.check(!decode(QJsonArray{b, a}).has_value(),
                  QStringLiteral("provider history integrity rejects nonmonotonic timestamps"));
        QJsonObject fractional_time = a;
        fractional_time.insert(QStringLiteral("timestamp"), 1704067200.5);
        rep.check(!decode(QJsonArray{fractional_time}).has_value(),
                  QStringLiteral("provider history integrity rejects fractional UTC epoch"));
        QJsonObject future_time = a;
        future_time.insert(QStringLiteral("timestamp"), test_now + 100000);
        rep.check(!decode(QJsonArray{future_time}).has_value(),
                  QStringLiteral("provider history integrity rejects future timestamp"));
        QJsonObject inverted = a;
        inverted.insert(QStringLiteral("low"), 104.0);
        rep.check(!decode(QJsonArray{inverted}).has_value(),
                  QStringLiteral("provider history integrity rejects inconsistent OHLC envelope"));
        QJsonObject negative_open = a;
        negative_open.insert(QStringLiteral("open"), -1.0);
        rep.check(!decode(QJsonArray{negative_open}).has_value(),
                  QStringLiteral("provider history integrity rejects negative OHLC price"));
        QJsonObject fractional_volume = a;
        fractional_volume.insert(QStringLiteral("volume"), 1000.5);
        rep.check(!decode(QJsonArray{fractional_volume}).has_value(),
                  QStringLiteral("provider history integrity rejects noninteger volume"));
    }

    // F1.2: test-only in-memory historical bars. The friend-scope fixture is
    // armed BEFORE the external KAIROS child so both C++ and Python can use the
    // genuine get_history handler without reaching PythonRunner or yfinance.
    // Even an unmatched period/symbol fails closed while this fixture is armed.
    auto& markets = services::MarketDataService::instance();
    const QString history_symbol = QStringLiteral("KAIROSHISTORYQA");
    markets.history_selftest_fixture_ = services::MarketDataService::HistorySelftestFixture{
        history_symbol, QStringLiteral("1mo"), QStringLiteral("1d"),
        QVector<services::HistoryPoint>{
            {1704067200, 100.0, 105.0, 99.0, 103.0, 1000},
            {1704153600, 103.0, 108.0, 102.0, 107.0, 1250},
            {1704240000, 107.0, 109.0, 104.0, 105.0, 950},
        }};
    rep.check(markets.history_selftest_fixture_.has_value() &&
                  markets.history_selftest_fixture_->bars.size() == 3,
              QStringLiteral("synthetic history fixture armed without Python/provider access"));

    // ── F1: real get_quote handler, synthetic ONLY in the isolated SQLite cache ──
    // The original MarketDataService reads a valid cache hit synchronously,
    // before reaching yfinance_data.py. NEVER call get_quote if seeding failed:
    // that would otherwise dispatch to an external provider.
    {
        const QString symbol = QStringLiteral("KAIROSQA");
        const QString key = QStringLiteral("market:") + symbol;
        const QString receipt = QStringLiteral("2000-01-01T00:00:00.000Z");
        const QJsonObject fixture{{"symbol", symbol}, {"name", "SYNTHETIC - NOT MARKET DATA"},
                                  {"price", 111.5}, {"change", 1.0}, {"change_pct", 0.91},
                                  {"high", 114.0}, {"low", 110.0}, {"volume", 1000.0},
                                  {"_fincept_local_received_at_utc", receipt}};
        const QString payload = QString::fromUtf8(QJsonDocument(fixture).toJson(QJsonDocument::Compact));
        auto& cache = fincept::CacheManager::instance();
        const bool cache_open = fincept::CacheDatabase::instance().is_open();
        rep.check(cache_open, QStringLiteral("synthetic quote test cache database is open"));
        if (cache_open) {
            cache.put(key, payload, 30, QStringLiteral("mcp_selftest_synthetic"));
            const bool cache_seeded = cache.get(key).toString() == payload;
            rep.check(cache_seeded, QStringLiteral("synthetic quote was seeded without provider calls"));
            if (cache_seeded) {
                const QJsonObject result = call_tool(port, token, QStringLiteral("get_quote"),
                                                     {{"symbol", symbol}}, 50)
                                               .value(QStringLiteral("result")).toObject();
                const QJsonObject data = result.value(QStringLiteral("structuredContent")).toObject();
                const QJsonObject provenance = data.value(QStringLiteral("quote_provenance")).toObject();
                rep.check(!result.value(QStringLiteral("isError")).toBool(true) &&
                              data.value(QStringLiteral("symbol")).toString() == symbol &&
                              data.value(QStringLiteral("price")).toDouble() == 111.5,
                          QStringLiteral("real get_quote MCP handler returns cached synthetic quote"));
                rep.check(provenance.value(QStringLiteral("delivery_origin")).toString() ==
                                  QLatin1String("unexpired_cache_hit") &&
                              provenance.value(QStringLiteral("local_received_at_utc")).toString() == receipt &&
                              provenance.contains(QStringLiteral("market_as_of_utc")) &&
                              provenance.value(QStringLiteral("market_as_of_utc")).isNull() &&
                              provenance.contains(QStringLiteral("market_age_seconds")) &&
                              provenance.value(QStringLiteral("market_age_seconds")).isNull(),
                          QStringLiteral("real get_quote preserves local receipt; market as-of remains unknown"));
                bool no_authority = true;
                for (const QString& field : {QStringLiteral("market_as_of_verified"),
                                             QStringLiteral("freshness_verified"),
                                             QStringLiteral("receipt_clock_verified"),
                                             QStringLiteral("execution_eligible"),
                                             QStringLiteral("scientific_claim")}) {
                    if (!provenance.contains(field) || provenance.value(field).toBool(true))
                        no_authority = false;
                }
                rep.check(no_authority,
                          QStringLiteral("real get_quote denies clock, freshness, science and execution authority"));

                // Opt-in cross-process test: execute the independently
                // maintained KAIROS Python MCP client while THIS original
                // Fincept HTTP server is listening. No test configuration =
                // no child process. The cache preflight above MUST succeed
                // before enabling a request, so no provider fallback occurs.
                const QString qa_script = qEnvironmentVariable("FINCEPT_KAIROS_QA_CLIENT_SCRIPT");
                const QString qa_python = qEnvironmentVariable("FINCEPT_KAIROS_QA_PYTHON");
                if (!qa_script.isEmpty() || !qa_python.isEmpty()) {
                    const QFileInfo script_file(qa_script);
                    const QFileInfo python_file(qa_python);
                    if (!script_file.isAbsolute() || !script_file.isFile() ||
                        !python_file.isAbsolute() || !python_file.isExecutable()) {
                        rep.check(false, QStringLiteral("external KAIROS client paths require explicit absolute files"));
                    } else {
                        QProcess child;
                        QProcessEnvironment clean;
                        clean.insert(QStringLiteral("HOME"), qEnvironmentVariable("HOME"));
                        clean.insert(QStringLiteral("TMPDIR"), qEnvironmentVariable("TMPDIR"));
                        clean.insert(QStringLiteral("PATH"), QStringLiteral("/usr/bin:/bin:/usr/local/bin:/opt/local/bin"));
                        clean.insert(QStringLiteral("PYTHONDONTWRITEBYTECODE"), QStringLiteral("1"));
                        clean.insert(QStringLiteral("KAIROS_QA_MCP_PORT"), QString::number(port));
                        // This is a one-process, random, selftest-only token,
                        // never the user's stored Fincept/Broker credentials.
                        clean.insert(QStringLiteral("KAIROS_QA_MCP_TEST_TOKEN"), token);
                        child.setProcessEnvironment(clean);
                        child.setProgram(qa_python);
                        child.setArguments({qa_script, QStringLiteral("--client-probe")});
                        child.start();
                        const bool completed = pump_until(
                            [&child]() { return child.state() == QProcess::NotRunning; }, 20000);
                        if (!completed) {
                            child.kill();
                            child.waitForFinished(2000);
                        }
                        const QByteArray evidence = child.readAllStandardOutput();
                        rep.check(completed && child.exitStatus() == QProcess::NormalExit &&
                                      child.exitCode() == 0 &&
                                      evidence.contains("KAIROS_ORIGINAL_FINCEPT_MCP_CLIENT_PASS"),
                                  QStringLiteral("external KAIROS Python client authenticated to real Fincept MCP"));
                    }
                }
            } else {
                rep.check(false, QStringLiteral("real quote MCP test refused: cannot seed cache"));
            }
            cache.remove(key);
        }
    }
    // F1.2: exercise the ORIGINAL get_history MCP handler and its latest-bar
    // truncation, then reject a mismatched window without provider fallback.
    {
        const QJsonObject r = call_tool(port, token, QStringLiteral("get_history"),
                                        {{"symbol", history_symbol}, {"period", "1mo"},
                                         {"interval", "1d"}, {"limit", 2}}, 52)
                                  .value(QStringLiteral("result")).toObject();
        const QJsonObject data = r.value(QStringLiteral("structuredContent")).toObject();
        const QJsonArray bars = data.value(QStringLiteral("bars")).toArray();
        const QJsonObject last = bars.size() == 2 ? bars.at(1).toObject() : QJsonObject{};
        rep.check(!r.value(QStringLiteral("isError")).toBool(true) &&
                      data.value(QStringLiteral("symbol")).toString() == history_symbol &&
                      data.value(QStringLiteral("period")).toString() == QLatin1String("1mo") &&
                      data.value(QStringLiteral("interval")).toString() == QLatin1String("1d") &&
                      data.value(QStringLiteral("count")).toInt() == 2 &&
                      data.value(QStringLiteral("total_bars")).toInt() == 3 &&
                      data.value(QStringLiteral("truncated")).toBool(false) &&
                      last.value(QStringLiteral("timestamp")).toVariant().toLongLong() == 1704240000 &&
                      last.value(QStringLiteral("open")).toDouble() == 107.0 &&
                      last.value(QStringLiteral("high")).toDouble() == 109.0 &&
                      last.value(QStringLiteral("low")).toDouble() == 104.0 &&
                      last.value(QStringLiteral("close")).toDouble() == 105.0 &&
                      last.value(QStringLiteral("volume")).toDouble() == 950.0,
                  QStringLiteral("original get_history MCP returns latest synthetic OHLCV bars only"));
        const QJsonObject mismatch = call_tool(port, token, QStringLiteral("get_history"),
                                               {{"symbol", history_symbol}, {"period", "3mo"},
                                                {"interval", "1d"}, {"limit", 2}}, 53)
                                         .value(QStringLiteral("result")).toObject();
        rep.check(mismatch.value(QStringLiteral("isError")).toBool(false) &&
                      mismatch.value(QStringLiteral("structuredContent")).toObject().isEmpty(),
                  QStringLiteral("synthetic history mismatched window fails closed without provider"));
    }
    markets.history_selftest_fixture_.reset();
    rep.check(!markets.history_selftest_fixture_.has_value(),
              QStringLiteral("synthetic history fixture cleared before end of selftest"));

    if (!destructive_tool.isEmpty()) {
        const QString advertised = McpHttpServer::advertised_name(destructive_tool);
        const QJsonObject res = call_tool(port, token, advertised,
                                          {{QStringLiteral("id"), QStringLiteral("selftest-does-not-exist")}}, 6)
                                    .value(QStringLiteral("result"))
                                    .toObject();
        rep.check(res.value(QStringLiteral("isError")).toBool() &&
                      first_text(res).contains(QStringLiteral("has not allowed external agents")),
                  QStringLiteral("destructive tool refused while actions are not allowed"), destructive_tool);
        if (provider.has_tool(QStringLiteral("tool_invoke"))) {
            const QJsonObject inv = call_tool(port, token, QStringLiteral("tool_invoke"),
                                              {{QStringLiteral("tool"), destructive_tool},
                                               {QStringLiteral("arguments"), QJsonObject{}}},
                                              7)
                                        .value(QStringLiteral("result"))
                                        .toObject();
            rep.check(inv.value(QStringLiteral("isError")).toBool() &&
                          first_text(inv).contains(QStringLiteral("has not allowed external agents")),
                      QStringLiteral("tool_invoke is held to the inner tool's policy"), destructive_tool);
        }
        const auto activity = server.recent_activity();
        const bool logged = std::any_of(activity.cbegin(), activity.cend(), [&advertised](const ExternalCallRecord& r) {
            return r.denied && r.tool == advertised;
        });
        rep.check(logged, QStringLiteral("the refusal is recorded in recent_activity() as denied"),
                  QStringLiteral("%1 records").arg(activity.size()));
    } else {
        rep.check(false, QStringLiteral("a destructive tool exists to exercise the policy"));
    }
    if (!live_read_tool.isEmpty()) {
        QElapsedTimer t;
        t.start();
        const QJsonObject res = call_tool(port, token, McpHttpServer::advertised_name(live_read_tool), {}, 8)
                                    .value(QStringLiteral("result"))
                                    .toObject();
        rep.check(res.value(QStringLiteral("isError")).toBool() && first_text(res).contains(QStringLiteral("approve")) &&
                      t.elapsed() < 10000,
                  QStringLiteral("approval-gated tool is refused at once when no window can ask"),
                  QStringLiteral("%1, %2 ms").arg(live_read_tool).arg(t.elapsed()));
    }
    {
        const QJsonObject resp = call_tool(port, token, QStringLiteral("no_such_tool_selftest"), {}, 9);
        rep.check(resp.value(QStringLiteral("error")).toObject().value(QStringLiteral("code")).toInt() == -32602,
                  QStringLiteral("unknown tool → JSON-RPC -32602"));
        const RpcReply bad_args = rpc(port, token,
                                      QJsonDocument(request(QStringLiteral("tools/call"), 10,
                                                            {{QStringLiteral("name"), QStringLiteral("tool_list")},
                                                             {QStringLiteral("arguments"), QStringLiteral("x")}})));
        rep.check(error_code(bad_args.doc) == -32602, QStringLiteral("non-object arguments → -32602"));
    }

    // ── auth & origin ──
    {
        const QByteArray ping = to_json_bytes(request(QStringLiteral("ping"), 11));
        const HttpReply none = http_request(port, "POST", "/mcp", {{"Content-Type", "application/json"}}, ping);
        rep.check(none.status == 401 && none.headers.value("www-authenticate").startsWith("Bearer"),
                  QStringLiteral("missing token → 401 + WWW-Authenticate: Bearer"), QString::number(none.status));
        const HttpReply wrong = http_request(port, "POST", "/mcp", auth_headers(QStringLiteral("not-the-token")), ping);
        rep.check(wrong.status == 401, QStringLiteral("wrong token → 401"), QString::number(wrong.status));
        HeaderList evil_host = auth_headers(token);
        evil_host.append(qMakePair(QByteArrayLiteral("Host"),
                                   QByteArrayLiteral("evil.example.com:") + QByteArray::number(port)));
        const HttpReply host = http_request(port, "POST", "/mcp", evil_host, ping);
        rep.check(host.status == 403, QStringLiteral("non-loopback Host header → 403"), QString::number(host.status));
        HeaderList evil_origin = auth_headers(token);
        evil_origin.append(qMakePair(QByteArrayLiteral("Origin"), QByteArrayLiteral("http://evil.example.com")));
        const HttpReply origin = http_request(port, "POST", "/mcp", evil_origin, ping);
        rep.check(origin.status == 403, QStringLiteral("cross-site Origin → 403"), QString::number(origin.status));
    }

    // ── batch ──
    {
        const QJsonArray batch{request(QStringLiteral("ping"), 21),
                               QJsonObject{{QStringLiteral("jsonrpc"), QStringLiteral("2.0")},
                                           {QStringLiteral("method"), QStringLiteral("notifications/initialized")}},
                               request(QStringLiteral("tools/list"), 22)};
        const RpcReply r = rpc(port, token, QJsonDocument(batch));
        const QJsonArray arr = r.doc.array();
        rep.check(r.http.status == 200 && arr.size() == 2 &&
                      arr.at(0).toObject().value(QStringLiteral("id")).toInt() == 21 &&
                      arr.at(1).toObject().value(QStringLiteral("id")).toInt() == 22,
                  QStringLiteral("batch → one response per request, in order"));
        const QJsonArray mixed{request(QStringLiteral("ping"), 23),
                               request(QStringLiteral("tools/call"), 24,
                                       {{QStringLiteral("name"), QStringLiteral("tool_list")},
                                        {QStringLiteral("arguments"),
                                         QJsonObject{{QStringLiteral("query"), QStringLiteral("news")}}}})};
        const RpcReply m = rpc(port, token, QJsonDocument(mixed));
        rep.check(m.http.status == 200 && m.doc.array().size() == 2 &&
                      m.doc.array().at(1).toObject().contains(QStringLiteral("result")),
                  QStringLiteral("batch containing tools/call completes after the worker finishes"));
    }

    // ── protocol errors ──
    {
        const HttpReply garbage = http_request(port, "POST", "/mcp", auth_headers(token), "{not json");
        rep.check(garbage.status == 400 && error_code(QJsonDocument::fromJson(garbage.body)) == -32700,
                  QStringLiteral("malformed JSON → 400 + -32700"), QString::number(garbage.status));
        const RpcReply unknown = rpc(port, token, QJsonDocument(request(QStringLiteral("no/such/method"), 31)));
        rep.check(error_code(unknown.doc) == -32601, QStringLiteral("unknown method → -32601"));
        const HttpReply get = http_request(port, "GET", "/mcp", auth_headers(token));
        rep.check(get.status == 405 && get.headers.value("allow") == "POST", QStringLiteral("GET /mcp → 405 + Allow: POST"),
                  QString::number(get.status));
        const HttpReply missing = http_request(port, "GET", "/nope", {});
        rep.check(missing.status == 404, QStringLiteral("unknown path → 404"), QString::number(missing.status));
    }

    // ── chunked body + keep-alive on one connection ──
    {
        QTcpSocket sock;
        if (connect_socket(sock, port)) {
            const QByteArray body = to_json_bytes(request(QStringLiteral("tools/list"), 41));
            const qsizetype half = body.size() / 2;
            QByteArray raw = "POST /mcp HTTP/1.1\r\nHost: 127.0.0.1:" + QByteArray::number(port) +
                             "\r\nAuthorization: Bearer " + token.toUtf8() +
                             "\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n";
            raw += QByteArray::number(half, 16) + "\r\n" + body.left(half) + "\r\n";
            raw += QByteArray::number(body.size() - half, 16) + "\r\n" + body.mid(half) + "\r\n0\r\n\r\n";
            const HttpReply first = exchange(sock, raw);
            rep.check(first.status == 200 &&
                          QJsonDocument::fromJson(first.body).object().value(QStringLiteral("id")).toInt() == 41,
                      QStringLiteral("chunked request body is decoded"), QString::number(first.status));
            const HttpReply second =
                exchange(sock, build_request("POST", "/mcp", port, auth_headers(token),
                                             to_json_bytes(request(QStringLiteral("ping"), 42)), /*keep_alive=*/true));
            rep.check(second.status == 200 &&
                          QJsonDocument::fromJson(second.body).object().value(QStringLiteral("id")).toInt() == 42,
                      QStringLiteral("keep-alive: a second request on the same connection"),
                      QString::number(second.status));
            sock.abort();
        } else {
            rep.check(false, QStringLiteral("connect for the chunked / keep-alive test"));
        }
    }

    // ── advertised-name aliasing ──
    {
        const QString long_name = QStringLiteral("x").repeated(70);
        const QString alias = McpHttpServer::advertised_name(long_name);
        rep.check(name_rx.match(alias).hasMatch() && alias == McpHttpServer::advertised_name(long_name) &&
                      alias != McpHttpServer::advertised_name(long_name + QStringLiteral("y")),
                  QStringLiteral("over-long names get a stable, distinct ≤50-char alias"), alias);
        const QString dotted = McpHttpServer::advertised_name(QStringLiteral("report.add.section"));
        rep.check(name_rx.match(dotted).hasMatch() && dotted != QLatin1String("report_add_section"),
                  QStringLiteral("names with invalid characters get a hashed alias"), dotted);
        rep.check(McpHttpServer::advertised_name(QStringLiteral("get_quote")) == QLatin1String("get_quote"),
                  QStringLiteral("valid names are advertised unchanged"));
    }

    // ── snippets ──
    {
        const QString url = server.url();
        rep.check(server.claude_code_add_command().contains(url) &&
                      server.claude_code_add_command().contains(QStringLiteral("Authorization: Bearer ") + token),
                  QStringLiteral("claude_code_add_command() carries the URL and token"));
        const QJsonObject generic = QJsonDocument::fromJson(server.generic_http_json().toUtf8())
                                        .object()
                                        .value(QStringLiteral("mcpServers"))
                                        .toObject()
                                        .value(QStringLiteral("fincept_terminal"))
                                        .toObject();
        rep.check(generic.value(QStringLiteral("url")).toString() == url &&
                      generic.value(QStringLiteral("headers")).toObject().value(QStringLiteral("Authorization")).toString() ==
                          QStringLiteral("Bearer ") + token,
                  QStringLiteral("generic_http_json() is valid JSON with the URL and header"));
        const QJsonObject env_cfg = server.claude_mcp_config_env()
                                        .value(QStringLiteral("mcpServers"))
                                        .toObject()
                                        .value(QStringLiteral("fincept"))
                                        .toObject();
        rep.check(env_cfg.value(QStringLiteral("headers")).toObject().value(QStringLiteral("Authorization")).toString() ==
                      QLatin1String("Bearer ${FINCEPT_MCP_TOKEN}"),
                  QStringLiteral("claude_mcp_config_env() uses ${FINCEPT_MCP_TOKEN} expansion"));
        rep.check(server.codex_config_toml().contains(QStringLiteral("url = \"") + url + QLatin1Char('"')) &&
                      server.codex_config_overrides().size() == 4,
                  QStringLiteral("codex_config_toml() / codex_config_overrides()"));
    }

    server.stop();
    rep.check(!server.is_running() && server.port() == 0 && server.url().isEmpty(),
              QStringLiteral("stop() releases the port"));
    server.clear_selftest_overrides();

    out(QStringLiteral("──────────────────────────────────────────────────────────────"));
    out(QStringLiteral("  %1 passed, %2 failed — %3 ms").arg(rep.pass).arg(rep.fail).arg(total.elapsed()));
    return rep.fail == 0 ? 0 : 1;
}

} // namespace fincept::mcp
