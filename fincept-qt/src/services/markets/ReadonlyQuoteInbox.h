#pragma once
// F2 public quote inbox: strict independent consumer, no provider or cache fallback.
#include <QByteArray>
#include <QCryptographicHash>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QString>
#include <cmath>
#include <optional>
#if defined(Q_OS_UNIX)
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace fincept::services::readonly_quote {
inline bool allowed(const QString& symbol) {
    return symbol == QLatin1String("SPY") || symbol == QLatin1String("EURUSD=X");
}
// Both envelopes are flat ASCII records with fixed keys and values. Reject
// escape aliases, nesting and duplicate keys before relying on Qt's object.
inline std::optional<QJsonObject> flat_object(const QByteArray& raw, int count) {
    bool quoted = false;
    int depth = 0, colons = 0;
    for (char c : raw) {
        if (static_cast<unsigned char>(c) > 127 || c == '\\') return std::nullopt;
        if (c == '"') { quoted = !quoted; continue; }
        if (quoted) continue;
        if (c == '{') { if (++depth != 1) return std::nullopt; }
        if (c == '}') { if (--depth != 0) return std::nullopt; }
        if (c == '[' || c == ']') return std::nullopt;
        if (c == ':') ++colons;
    }
    QJsonParseError error;
    const auto doc = QJsonDocument::fromJson(raw, &error);
    if (quoted || depth != 0 || colons != count || error.error != QJsonParseError::NoError ||
        !doc.isObject() || doc.object().size() != count) return std::nullopt;
    return doc.object();
}
inline bool flag(const QJsonObject& obj, const char* key, bool expected) {
    const auto v = obj.value(QLatin1String(key));
    return v.isBool() && v.toBool() == expected;
}
inline std::optional<QJsonObject> decode(const QByteArray& raw, const QString& symbol, qint64 now) {
    if (!allowed(symbol) || now <= 0 || raw.isEmpty() || raw.size() > 8192) return std::nullopt;
    const auto env = flat_object(raw, 6);
    if (!env || env->value("schema").toString() != QLatin1String("YAHOO_QUOTE_SNAPSHOT_V1") ||
        env->value("provider").toString() != QLatin1String("Yahoo Finance via original yfinance") ||
        env->value("symbol").toString() != symbol) return std::nullopt;
    const qint64 captured = env->value("captured_at_unix").toInteger(-1);
    const QByteArray encoded = env->value("quote_base64").toString().toLatin1();
    const QByteArray payload = QByteArray::fromBase64(encoded);
    if (captured <= 0 || captured > now || now - captured > 60 || payload.isEmpty() ||
        payload.size() > 4096 || payload.toBase64() != encoded ||
        env->value("quote_sha256").toString().toLatin1() != QCryptographicHash::hash(payload, QCryptographicHash::Sha256).toHex())
        return std::nullopt;
    auto q = flat_object(payload, 18);
    if (!q || q->value("schema").toString() != QLatin1String("YAHOO_PROVIDER_CLAIMED_QUOTE_V1") ||
        q->value("provider").toString() != QLatin1String("Yahoo Finance via original yfinance") ||
        q->value("symbol").toString() != symbol ||
        !flag(*q, "research_only", true) || !flag(*q, "market_as_of_verified", false) ||
        !flag(*q, "freshness_verified", false) || !flag(*q, "execution_authority", false) ||
        !flag(*q, "scientific_claim", false) || q->value("broker_calls").toInteger(-1) != 0)
        return std::nullopt;
    const qint64 claimed = q->value("provider_claimed_market_time_unix").toInteger(-1);
    const qint64 received = q->value("local_received_at_unix").toInteger(-1);
    if (claimed <= 0 || claimed > received || received > captured ||
        now - claimed > 900 || now - received > 60) return std::nullopt;
    for (const auto* key : {"price","previous_close","high","low","volume","change","change_percent"}) {
        const auto v = q->value(QLatin1String(key));
        if (!v.isDouble() || !std::isfinite(v.toDouble())) return std::nullopt;
    }
    const double p = q->value("price").toDouble(), prev = q->value("previous_close").toDouble(),
        hi = q->value("high").toDouble(), lo = q->value("low").toDouble(),
        vol = q->value("volume").toDouble(), change = q->value("change").toDouble(),
        pct = q->value("change_percent").toDouble();
    if (!(0 < lo && lo <= p && p <= hi && prev > 0 && vol >= 0 && vol <= 9007199254740991.0 &&
        std::floor(vol) == vol && change == p - prev && pct == 100 * (change / prev))) return std::nullopt;
    q->insert("captured_at_unix", captured);
    return q;
}
inline std::optional<QJsonObject> read(const QString& directory, const QString& symbol, qint64 now) {
#if !defined(Q_OS_UNIX)
    Q_UNUSED(directory); Q_UNUSED(symbol); Q_UNUSED(now);
    return std::nullopt;
#else
    if (!allowed(symbol) || ::geteuid() == 0) return std::nullopt;
    const auto path = QFile::encodeName(directory);
    int parent = ::open(path.constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (parent < 0) return std::nullopt;
    struct stat st {};
    const auto private_dir = [](int fd) {
        struct stat ds {};
        return ::fstat(fd, &ds) == 0 && S_ISDIR(ds.st_mode) &&
            ds.st_uid == ::geteuid() && (ds.st_mode & 0777) == 0700;
    };
    if (!private_dir(parent)) { ::close(parent); return std::nullopt; }
    int child = ::openat(parent, symbol.toLatin1().constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    ::close(parent);
    if (child < 0) return std::nullopt;
    if (!private_dir(child)) { ::close(child); return std::nullopt; }
    int fd = ::openat(child, "snapshot.json", O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    ::close(child);
    if (fd < 0) return std::nullopt;
    if (::fstat(fd, &st) != 0 || !S_ISREG(st.st_mode) || st.st_uid != ::geteuid() ||
        (st.st_mode & 0777) != 0600 || st.st_nlink != 1 || st.st_size <= 0 || st.st_size > 8192) {
        ::close(fd); return std::nullopt;
    }
    QFile file;
    if (!file.open(fd, QIODevice::ReadOnly, QFileDevice::AutoCloseHandle)) { ::close(fd); return std::nullopt; }
    const auto raw = file.read(8193);
    if (raw.size() != st.st_size) return std::nullopt;
    return decode(raw, symbol, now);
#endif
}
} // namespace fincept::services::readonly_quote
