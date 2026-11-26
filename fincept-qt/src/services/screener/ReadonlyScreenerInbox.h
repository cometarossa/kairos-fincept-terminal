#pragma once
// F2 candidate: local bounded research snapshot only. No provider/refresh.
#include "services/markets/ReadonlyQuoteInbox.h"
#include <QJsonArray>
#include <QRegularExpression>
#include <QSet>
#include <limits>

namespace fincept::services::readonly_screener {
inline constexpr qsizetype max_payload = 16384, max_envelope = 32768;
inline bool request_allowed(const QJsonObject& args) {
    return args.size() == 2 && args.value("screen_id").toString() == QLatin1String("day_gainers")
        && args.value("limit").toInteger(-1) == 20;
}
inline std::optional<QJsonObject> decode(const QByteArray& raw, qint64 now) {
    using namespace readonly_quote;
    if (now <= 0 || raw.isEmpty() || raw.size() > max_envelope) return std::nullopt;
    const auto env = flat_object(raw, 3);
    if (!env || env->value("schema").toString() != QLatin1String("FINCEPT_SCREENER_INBOX_V1")) return std::nullopt;
    const auto encoded = env->value("payload_base64").toString().toLatin1();
    const auto bytes = QByteArray::fromBase64(encoded);
    if (bytes.isEmpty() || bytes.size() > max_payload || bytes.toBase64() != encoded ||
        env->value("payload_sha256").toString().toLatin1() != QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())
        return std::nullopt;
    // Restricted ASCII schema: no escapes or duplicate JSON keys. Count all
    // object fields before Qt parsing (which otherwise collapses duplicates).
    bool quoted = false; int depth = 0, colons = 0;
    for (char c : bytes) {
        if (static_cast<unsigned char>(c) > 127 || c == '\\') return std::nullopt;
        if (c == '"') { quoted = !quoted; continue; }
        if (quoted) continue;
        if (c == '{' || c == '[') { if (++depth > 3) return std::nullopt; }
        if (c == '}' || c == ']') { if (--depth < 0) return std::nullopt; }
        if (c == ':') ++colons;
    }
    QJsonParseError err;
    const auto doc = QJsonDocument::fromJson(bytes,&err);
    if (quoted || depth != 0 || err.error != QJsonParseError::NoError || !doc.isObject()) return std::nullopt;
    const auto o = doc.object();
    const auto rows = o.value("rows").toArray();
    const auto count = o.value("count").toInteger(-1), total = o.value("total").toInteger(-1);
    const auto cap = o.value("captured_at_unix").toInteger(-1), exp = o.value("valid_until_unix").toInteger(-1);
    if (o.size() != 13 || count < 1 || count > 20 || rows.size() != count ||
        colons != 13 + 5*count || total < count || total > 9007199254740991LL ||
        cap <= 0 || cap > now || exp <= now || exp-cap != 600 ||
        o.value("schema").toString() != QLatin1String("FINCEPT_SCREENER_SNAPSHOT_V1") ||
        o.value("source").toString() != QLatin1String("Yahoo Finance screener") ||
        o.value("screen_id").toString() != QLatin1String("day_gainers") ||
        !flag(o,"research_only",true) || !flag(o,"market_as_of_verified",false) ||
        !flag(o,"scientific_claim",false) || !flag(o,"execution_authority",false) ||
        o.value("broker_calls").toInteger(-1) != 0) return std::nullopt;
    QSet<QString> seen;
    const QRegularExpression ticker(QStringLiteral("\\A[A-Z0-9.^=_-]{1,32}\\z"));
    for (const auto& value : rows) {
        const auto row = value.toObject();
        const auto symbol = row.value("symbol").toString();
        const auto price = row.value("price").toDouble(-1);
        const auto stamp = row.value("market_time").toInteger(-1);
        const auto delay = row.value("delay_min").toInteger(-1);
        if (!value.isObject() || row.size()!=5 || !ticker.match(symbol).hasMatch() || seen.contains(symbol) ||
            !std::isfinite(price) || price<=0 || row.value("currency").toString()!=QLatin1String("USD") ||
            stamp<=0 || stamp>cap || delay<0 || delay>9007199254740991LL) return std::nullopt;
        seen.insert(symbol);
    }
    return o;
}
inline std::optional<QJsonObject> read(const QString& directory, qint64 now) {
#if !defined(Q_OS_UNIX)
    Q_UNUSED(directory); Q_UNUSED(now); return std::nullopt;
#else
    if (::geteuid()==0) return std::nullopt;
    const auto path = QFile::encodeName(directory);
    const int parent = ::open(path.constData(), O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if (parent<0) return std::nullopt;
    struct stat ds {}, st {};
    if (::fstat(parent,&ds)!=0 || !S_ISDIR(ds.st_mode) || ds.st_uid!=::geteuid() || (ds.st_mode&0777)!=0700) {
        ::close(parent); return std::nullopt;
    }
    const int fd = ::openat(parent,"snapshot.json",O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
    ::close(parent);
    if (fd<0) return std::nullopt;
    if (::fstat(fd,&st)!=0 || !S_ISREG(st.st_mode) || st.st_uid!=::geteuid() || (st.st_mode&0777)!=0600 ||
        st.st_nlink!=1 || st.st_size<=0 || st.st_size>max_envelope) {
        ::close(fd); return std::nullopt;
    }
    QFile file;
    if (!file.open(fd,QIODevice::ReadOnly,QFileDevice::AutoCloseHandle)) { ::close(fd); return std::nullopt; }
    const auto raw=file.read(max_envelope+1);
    if (raw.size()!=st.st_size) return std::nullopt;
    return decode(raw,now);
#endif
}
} // namespace fincept::services::readonly_screener
