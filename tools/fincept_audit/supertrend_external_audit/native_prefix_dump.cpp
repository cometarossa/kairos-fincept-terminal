// Diagnostic only. Emit synthetic candidate Supertrend from original C++ source.
// No broker, I/O to disk, account, GUI or network; fixture is integer-cent synthetic.
#include "algo_engine/IndicatorEngine.h"
#include <QCoreApplication>
#include <QJsonObject>
#include <QVector>
#include <algorithm>
#include <clocale>
#include <cmath>
#include <cstdio>

using fincept::algo::IndicatorEngine;
using fincept::algo::OhlcvCandle;

static QVector<OhlcvCandle> candles(const QString& kind) {
    QVector<OhlcvCandle> out;
    out.reserve(200);
    int close = 10000;
    for (int i = 0; i < 200; ++i) {
        int open = 0, high = 0, low = 0;
        if (kind == QStringLiteral("reversals")) {
            int delta = 0;
            if (i < 35) delta = 48 + 5 * (i % 3);
            else if (i < 75) delta = -(85 + 7 * (i % 5));
            else if (i < 115) delta = 110 + 5 * (i % 5);
            else if (i < 155) delta = -(90 + 9 * (i % 4));
            else delta = 75 + 3 * (i % 6);
            close += delta;
            open = close - 15 + (i % 5) * 5;
            high = close + 125 + (i % 4) * 7;
            low = close - 135 - (i % 3) * 9;
        } else if (kind == QStringLiteral("shock")) {
            const int mod = i % 31;
            const int delta = mod < 8 ? 220 : mod < 16 ? -150 : mod < 23 ? 85 : -45;
            close += delta;
            open = close - 10;
            const int span = i % 9 < 4 ? 30 : 270;
            high = close + span;
            low = close - span;
        } else {
            return {};
        }
        OhlcvCandle c;
        c.open_time = i;
        c.close_time = i;
        c.open = open / 100.0;
        c.high = high / 100.0;
        c.low = low / 100.0;
        c.close = close / 100.0;
        c.volume = 1000 + i;
        c.is_closed = true;
        out.append(c);
    }
    return out;
}

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    // The host may use a locale where printf writes a comma decimal separator.
    // Force machine-readable numeric output independent of host language.
    if (!std::setlocale(LC_NUMERIC, "C")) return 5;
    const QStringList args = app.arguments();
    if (args.size() != 2) {
        std::fprintf(stderr, "USAGE: supertrend_candidate_prefix_dump reversals|shock\n");
        return 2;
    }
    const QVector<OhlcvCandle> series = candles(args[1]);
    if (series.size() != 200) return 3;
    const QJsonObject params{{"period", 10}, {"multiplier", 3.0}};
    std::puts("#schema=fincept_synthetic_supertrend_candidate_prefix_v1");
    for (int n = 11; n <= series.size(); ++n) {
        const auto observed = IndicatorEngine::compute(
            QStringLiteral("SUPERTREND"), series.mid(0, n), params, QStringLiteral("value"));
        const double line = observed.current.value(QStringLiteral("value"));
        const double direction = observed.current.value(QStringLiteral("direction"));
        if (!observed.valid || !std::isfinite(line) ||
            (direction != 1.0 && direction != -1.0)) {
            std::fprintf(stderr, "INVALID_OUTPUT_PREFIX_%d\n", n);
            return 4;
        }
        std::printf("%d,%.17g,%d\n", n - 1, line, static_cast<int>(direction));
    }
    return 0;
}
