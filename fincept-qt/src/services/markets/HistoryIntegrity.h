#pragma once

// Fincept original market history boundary: structurally valid provider OHLCV
// is required before supplying any bar to Qt/MCP. This is NOT a guarantee of
// market provenance, exchange time, provider freshness or scientific quality.
// Zero tolerance for missing/invalid bars: no implicit Qt JSON 0.0 defaults.
#include "services/markets/MarketDataService.h"

#include <QDateTime>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonValue>

#include <cmath>
#include <optional>

namespace fincept::services::history_integrity {

inline std::optional<QVector<HistoryPoint>> decode(
    const QJsonDocument& document, qint64 now_utc_seconds = QDateTime::currentSecsSinceEpoch()) {
    if (!document.isArray())
        return std::nullopt;
    const QJsonArray input = document.array();
    // A missing/oversized series is unavailable, not an empty successful price series.
    if (input.isEmpty() || input.size() > 20000 || now_utc_seconds <= 0)
        return std::nullopt;

    QVector<HistoryPoint> decoded;
    decoded.reserve(input.size());
    qint64 previous_timestamp = 0;

    const auto field = [](const QJsonObject& row, const char* key) -> std::optional<double> {
        const QJsonValue value = row.value(QLatin1String(key));
        if (!value.isDouble())
            return std::nullopt;
        const double number = value.toDouble();
        if (!std::isfinite(number))
            return std::nullopt;
        return number;
    };

    for (const QJsonValue& item : input) {
        if (!item.isObject())
            return std::nullopt;
        const QJsonObject row = item.toObject();
        const auto timestamp = field(row, "timestamp");
        const auto open = field(row, "open");
        const auto high = field(row, "high");
        const auto low = field(row, "low");
        const auto close = field(row, "close");
        const auto volume = field(row, "volume");
        if (!timestamp || !open || !high || !low || !close || !volume)
            return std::nullopt;
        // UTC epoch-seconds only; reject fractional, duplicated, unordered and
        // future-dated bars. Never relabel this time as verified exchange as-of.
        if (*timestamp <= 0 || *timestamp > static_cast<double>(now_utc_seconds) + 86400.0 ||
            std::floor(*timestamp) != *timestamp ||
            *timestamp <= static_cast<double>(previous_timestamp))
            return std::nullopt;
        if (*open <= 0 || *high <= 0 || *low <= 0 || *close <= 0 ||
            *low > *open || *low > *close || *high < *open ||
            *high < *close || *high < *low)
            return std::nullopt;
        // JSON numbers are IEEE754 doubles. Keep volume inside exact integer
        // precision and never reinterpret absent volume as a known zero.
        if (*volume < 0 || *volume > 9007199254740991.0 ||
            std::floor(*volume) != *volume)
            return std::nullopt;
        HistoryPoint bar;
        bar.timestamp = static_cast<qint64>(*timestamp);
        bar.open = *open;
        bar.high = *high;
        bar.low = *low;
        bar.close = *close;
        bar.volume = static_cast<qint64>(*volume);
        decoded.append(bar);
        previous_timestamp = bar.timestamp;
    }
    return decoded;
}

} // namespace fincept::services::history_integrity
