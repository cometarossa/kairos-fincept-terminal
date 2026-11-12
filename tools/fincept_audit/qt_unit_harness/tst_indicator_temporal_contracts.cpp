// Original C++ engine property probes. No original Fincept sources changed.
// QEXPECT_FAIL documents a known engine defect: XPASS will require reviewing
// and retiring the sentinel if a future fix changes the numerical behaviour.
#include "algo_engine/IndicatorEngine.h"

#include <QJsonObject>
#include <QTest>
#include <QVector>

#include <algorithm>
#include <cmath>

using fincept::algo::IndicatorEngine;
using fincept::algo::IndicatorResult;
using fincept::algo::OhlcvCandle;

namespace {

QVector<OhlcvCandle> synthetic_candles() {
    QVector<OhlcvCandle> out;
    out.reserve(120);
    for (int i = 0; i < 120; ++i) {
        const int close = 10000 + 9 * i + (((i * 37) % 23) - 11) * 15 + (((i * i) % 7) - 3) * 8;
        const int open = close - 25 + (i % 6) * 10;
        const int high = std::max(open, close) + 20 + (i % 4) * 10;
        const int low = std::min(open, close) - 15 - (i % 3) * 10;
        const int volume = 1000 + ((i * 53) % 200) + (i % 5) * 40;
        OhlcvCandle c;
        c.open_time = i;
        c.close_time = i;
        c.open = open / 100.0;
        c.high = high / 100.0;
        c.low = low / 100.0;
        c.close = close / 100.0;
        c.volume = volume;
        c.is_closed = true;
        out.append(c);
    }
    return out;
}

bool near(double a, double b) {
    return std::isfinite(a) && std::isfinite(b)
        && std::abs(a - b) <= 1e-9 * std::max({1.0, std::abs(a), std::abs(b)});
}

bool crossed(double prev_plus, double prev_minus, double now_plus, double now_minus) {
    return (prev_plus <= prev_minus && now_plus > now_minus)
        || (prev_plus >= prev_minus && now_plus < now_minus);
}

} // namespace

class TstIndicatorTemporalContracts : public QObject {
    Q_OBJECT

  private slots:
    void adx_previous_di_is_the_prior_prefix_value();
    void supertrend_long_line_does_not_decrease_without_reversal();
};

void TstIndicatorTemporalContracts::adx_previous_di_is_the_prior_prefix_value() {
    const auto candles = synthetic_candles();
    const QJsonObject params{{"period", 14}};
    int compared = 0, broken_previous = 0, actual_crossovers = 0, masked_crossovers = 0;
    for (int n = 40; n <= candles.size(); ++n) {
        const IndicatorResult now =
            IndicatorEngine::compute("ADX", candles.mid(0, n), params, "plus_di");
        const IndicatorResult prior =
            IndicatorEngine::compute("ADX", candles.mid(0, n - 1), params, "plus_di");
        QVERIFY2(now.valid && prior.valid, "ADX fixture unexpectedly invalid");
        for (const QString& k : {QStringLiteral("plus_di"), QStringLiteral("minus_di")}) {
            QVERIFY(now.current.contains(k) && now.previous.contains(k) && prior.current.contains(k));
            ++compared;
            if (!near(now.previous.value(k), prior.current.value(k)))
                ++broken_previous;
        }
        const bool true_cross = crossed(prior.current.value("plus_di"), prior.current.value("minus_di"),
                                        now.current.value("plus_di"), now.current.value("minus_di"));
        const bool engine_cross = crossed(now.previous.value("plus_di"), now.previous.value("minus_di"),
                                          now.current.value("plus_di"), now.current.value("minus_di"));
        if (true_cross) {
            ++actual_crossovers;
            if (!engine_cross)
                ++masked_crossovers;
        }
    }
    qInfo("ADX previous DI: compared=%d mismatched=%d actual_crossovers=%d masked=%d",
          compared, broken_previous, actual_crossovers, masked_crossovers);
    QVERIFY(compared > 100);
    QVERIFY(actual_crossovers > 0);
    QVERIFY(masked_crossovers > 0); // Characterization of current defect.
    QEXPECT_FAIL("", "KNOWN BUG: original ADX previous DI repeats current rather than last bar; expected failure until corrected", Continue);
    QCOMPARE(broken_previous, 0);
}

void TstIndicatorTemporalContracts::supertrend_long_line_does_not_decrease_without_reversal() {
    const auto candles = synthetic_candles();
    const QJsonObject params{{"period", 10}, {"multiplier", 3.0}};
    int eligible_long_bars = 0, long_line_falls = 0;
    for (int n = 15; n <= candles.size(); ++n) {
        const IndicatorResult now =
            IndicatorEngine::compute("SUPERTREND", candles.mid(0, n), params, "value");
        const IndicatorResult prior =
            IndicatorEngine::compute("SUPERTREND", candles.mid(0, n - 1), params, "value");
        QVERIFY2(now.valid && prior.valid, "Supertrend fixture unexpectedly invalid");
        const bool long_both = near(now.current.value("direction"), 1.0)
                            && near(prior.current.value("direction"), 1.0);
        if (long_both) {
            ++eligible_long_bars;
            if (now.current.value("value") < prior.current.value("value") - 1e-9)
                ++long_line_falls;
        }
    }
    qInfo("Supertrend: same-direction long transitions=%d decreases=%d",
          eligible_long_bars, long_line_falls);
    QVERIFY(eligible_long_bars > 20);
    QEXPECT_FAIL("", "KNOWN BUG: long Supertrend trailing line can decrease in the unmodified engine", Continue);
    QCOMPARE(long_line_falls, 0);
}

QTEST_GUILESS_MAIN(TstIndicatorTemporalContracts)
#include "tst_indicator_temporal_contracts.moc"
