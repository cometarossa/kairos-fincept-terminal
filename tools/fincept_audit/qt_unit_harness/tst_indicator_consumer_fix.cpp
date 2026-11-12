// Real ConditionEvaluator + IndicatorEngine (QtCore/QtGui, synthetic data).
// No application, broker, profile, deployment, orders or network.
#include "algo_engine/ConditionEvaluator.h"
#include "algo_engine/IndicatorEngine.h"
#include <QJsonObject>
#include <QTest>
#include <QVector>
#include <algorithm>

using fincept::algo::ConditionEvaluator;
using fincept::algo::IndicatorEngine;
using fincept::algo::OhlcvCandle;
using fincept::services::algo::ConditionDef;

namespace {
QVector<OhlcvCandle> fixture() {
    QVector<OhlcvCandle> out;
    out.reserve(120);
    for (int i = 0; i < 120; ++i) {
        const int close = 10000 + 9 * i + (((i * 37) % 23) - 11) * 15 + (((i * i) % 7) - 3) * 8;
        const int open = close - 25 + (i % 6) * 10;
        const int high = std::max(open, close) + 20 + (i % 4) * 10;
        const int low = std::min(open, close) - 15 - (i % 3) * 10;
        OhlcvCandle c;
        c.open_time = i;
        c.close_time = i;
        c.open = open / 100.0;
        c.high = high / 100.0;
        c.low = low / 100.0;
        c.close = close / 100.0;
        c.volume = 1000 + ((i * 53) % 200) + (i % 5) * 40;
        c.is_closed = true;
        out.append(c);
    }
    return out;
}
}

class TstIndicatorConsumer : public QObject {
    Q_OBJECT
private slots:
    void adx_crossing_reads_two_prefixes_not_previous_map();
    void supertrend_falling_is_false_across_consecutive_long_bars();
};

void TstIndicatorConsumer::adx_crossing_reads_two_prefixes_not_previous_map() {
    const auto candles = fixture();
    const QJsonObject params{{"period", 14}};
    ConditionDef above;
    above.indicator = "ADX";
    above.params = params;
    above.field = "plus_di";
    above.op = "crosses_above";
    above.compare_mode = "indicator";
    above.compare_indicator = "ADX";
    above.compare_params = params;
    above.compare_field = "minus_di";
    ConditionDef below = above;
    below.op = "crosses_below";
    int up_crossings = 0, down_crossings = 0;
    for (int n = 40; n <= candles.size(); ++n) {
        const auto prefix = candles.mid(0, n);
        const auto now = IndicatorEngine::compute("ADX", prefix, params, "plus_di");
        const auto prior = IndicatorEngine::compute("ADX", candles.mid(0, n - 1), params, "plus_di");
        QVERIFY(now.valid && prior.valid);
        const double current_plus = now.current.value("plus_di");
        const double current_minus = now.current.value("minus_di");
        const double prior_plus = prior.current.value("plus_di");
        const double prior_minus = prior.current.value("minus_di");
        const bool expected_up = prior_plus <= prior_minus && current_plus > current_minus;
        const bool expected_down = prior_plus >= prior_minus && current_plus < current_minus;

        // This is what the original ConditionEvaluator does: recompute the last
        // operand on a shorter candle prefix rather than consume result.previous.
        const auto evaluated_up = ConditionEvaluator::evaluate_single(above, prefix);
        const auto evaluated_down = ConditionEvaluator::evaluate_single(below, prefix);
        QVERIFY2(evaluated_up.error.isEmpty(), qPrintable(evaluated_up.error));
        QVERIFY2(evaluated_down.error.isEmpty(), qPrintable(evaluated_down.error));
        QCOMPARE(evaluated_up.met, expected_up);
        QCOMPARE(evaluated_down.met, expected_down);
        up_crossings += evaluated_up.met;
        down_crossings += evaluated_down.met;
    }
    qInfo("ConditionEvaluator ADX: crosses_above=%d crosses_below=%d total=%d",
          up_crossings, down_crossings, up_crossings + down_crossings);
    QCOMPARE(up_crossings + down_crossings, 20);
}

void TstIndicatorConsumer::supertrend_falling_is_false_across_consecutive_long_bars() {
    const auto candles = fixture();
    const QJsonObject params{{"period", 10}, {"multiplier", 3.0}};
    ConditionDef condition;
    condition.indicator = "SUPERTREND";
    condition.params = params;
    condition.field = "value";
    condition.op = "falling";
    int eligible = 0, forbidden_triggers = 0;
    for (int n = 15; n <= candles.size(); ++n) {
        const auto prefix = candles.mid(0, n);
        const auto now = IndicatorEngine::compute("SUPERTREND", prefix, params, "value");
        const auto prior = IndicatorEngine::compute("SUPERTREND", candles.mid(0, n - 1), params, "value");
        QVERIFY(now.valid && prior.valid);
        if (now.current.value("direction") == 1 && prior.current.value("direction") == 1) {
            ++eligible;
            const auto evaluated = ConditionEvaluator::evaluate_single(condition, prefix);
            QVERIFY2(evaluated.error.isEmpty(), qPrintable(evaluated.error));
            forbidden_triggers += evaluated.met;
        }
    }
    qInfo("ConditionEvaluator Supertrend: consecutive long=%d falling_triggers=%d",
          eligible, forbidden_triggers);
    QVERIFY(eligible >= 100);
    QCOMPARE(forbidden_triggers, 0);
}

QTEST_GUILESS_MAIN(TstIndicatorConsumer)
#include "tst_indicator_consumer_fix.moc"
