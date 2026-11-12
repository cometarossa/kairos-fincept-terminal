// Strict C++ as-of temporal regression tests for proposed fix only.
// No XFAIL masking: all ADX/Supertrend properties must hold.
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

struct ReversalExpected {
    int bars;
    double current;
    double previous;
    int direction;
    int previous_direction;
};

// BEGIN GENERATED SUPERTREND REVERSAL ORACLE
static const ReversalExpected kReversals[] = {
    {11, 97.407363636363641, 96.918999999999997, 1, 1},
    {12, 97.864206611570253, 97.407363636363641, 1, 1},
    {20, 102.14150618797838, 101.68406311864024, 1, 1},
    {35, 110.11260823337419, 109.62096561856845, 1, 1},
    {42, 110.11260823337419, 110.11260823337419, 1, 1},
    {55, 107.07892201949079, 108.11479357937763, -1, -1},
    {75, 87.244538775169346, 88.307769614095861, -1, -1},
    {85, 82.499392640399634, 81.092035449377335, 1, 1},
    {100, 100.53765006111395, 99.115461185805941, 1, 1},
    {115, 118.56107580344037, 117.10520375976044, 1, 1},
    {125, 124.80919540475469, 125.92234993914462, -1, -1},
    {150, 99.004796240255246, 99.969195404756405, -1, -1},
    {155, 93.837512236439593, 94.899181622315055, -1, -1},
    {165, 93.837512236439593, 93.837512236439593, -1, -1},
    {180, 97.692035442913067, 96.912487763560407, 1, 1},
    {200, 114.16906202098615, 113.46107580342752, 1, 1},
};
// END GENERATED SUPERTREND REVERSAL ORACLE

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

QVector<OhlcvCandle> reversal_candles() {
    QVector<OhlcvCandle> out;
    out.reserve(200);
    int close = 10000;
    for (int i = 0; i < 200; ++i) {
        int delta = 0;
        if (i < 35)
            delta = 48 + 5 * (i % 3);
        else if (i < 75)
            delta = -(85 + 7 * (i % 5));
        else if (i < 115)
            delta = 110 + 5 * (i % 5);
        else if (i < 155)
            delta = -(90 + 9 * (i % 4));
        else
            delta = 75 + 3 * (i % 6);
        close += delta;
        OhlcvCandle c;
        c.open_time = i;
        c.close_time = i;
        c.open = (close - 15 + (i % 5) * 5) / 100.0;
        c.high = (close + 125 + (i % 4) * 7) / 100.0;
        c.low = (close - 135 - (i % 3) * 9) / 100.0;
        c.close = close / 100.0;
        c.volume = 1000 + i;
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
    void supertrend_reversals_match_independent_fraction_oracle();
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
    QCOMPARE(masked_crossovers, 0);
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
    QCOMPARE(long_line_falls, 0);
}

void TstIndicatorTemporalContracts::supertrend_reversals_match_independent_fraction_oracle() {
    const auto candles = reversal_candles();
    QCOMPARE(candles.size(), 200);
    const QJsonObject params{{"period", 10}, {"multiplier", 3.0}};
    for (const ReversalExpected& want : kReversals) {
        const IndicatorResult actual =
            IndicatorEngine::compute("SUPERTREND", candles.mid(0, want.bars), params, "value");
        QVERIFY2(actual.valid, qPrintable(actual.error));
        QVERIFY2(near(actual.current.value("value"), want.current), "reversal reference current line differs");
        QVERIFY2(near(actual.previous.value("value"), want.previous), "reversal reference previous line differs");
        QCOMPARE(static_cast<int>(actual.current.value("direction")), want.direction);
        QCOMPARE(static_cast<int>(actual.previous.value("direction")), want.previous_direction);
    }
    int reversals = 0;
    for (int bars = 12; bars <= candles.size(); ++bars) {
        const IndicatorResult current =
            IndicatorEngine::compute("SUPERTREND", candles.mid(0, bars), params, "value");
        const IndicatorResult prior =
            IndicatorEngine::compute("SUPERTREND", candles.mid(0, bars - 1), params, "value");
        QVERIFY2(current.valid && prior.valid, "reversal fixture unexpectedly invalid");
        QVERIFY2(near(current.previous.value("value"), prior.current.value("value")),
                 "Supertrend previous line not equal to prior prefix current line");
        const int direction = static_cast<int>(current.current.value("direction"));
        const int prior_direction = static_cast<int>(prior.current.value("direction"));
        QCOMPARE(static_cast<int>(current.previous.value("direction")), prior_direction);
        if (direction != prior_direction)
            ++reversals;
    }
    QCOMPARE(reversals, 4);
}

QTEST_GUILESS_MAIN(TstIndicatorTemporalContracts)
#include "tst_indicator_temporal_contracts.moc"
