// Strict guard tests on ACTUAL IndicatorEngine.cpp.
// A PASS does not authorize production deployment or trading.
#include "algo_engine/IndicatorEngine.h"
#include <QJsonObject>
#include <QTest>
#include <QVector>
#include <cmath>
#include <limits>

using fincept::algo::IndicatorEngine;
using fincept::algo::IndicatorResult;
using fincept::algo::OhlcvCandle;

namespace {
QVector<OhlcvCandle> candles(int n=60) {
    QVector<OhlcvCandle> r;
    for (int i=0; i<n; ++i) {
        OhlcvCandle c;
        c.open_time=i; c.close_time=i;
        c.open=100. + .2*i;
        c.high=c.open+1.; c.low=c.open-1.;
        c.close=c.open; c.volume=10.; c.is_closed=true;
        r.append(c);
    }
    return r;
}
IndicatorResult calc(const QVector<OhlcvCandle>& bars,
                    QJsonObject params={{"period",10},{"multiplier",3.0}}) {
    return IndicatorEngine::compute("SUPERTREND",bars,params,"value");
}
void require_rejected(const IndicatorResult& r) {
    QVERIFY2(!r.valid, "unsafe candle/parameter accepted as valid");
    QVERIFY2(!r.error.isEmpty(), "invalid input not associated with error");
}
void require_valid(const IndicatorResult& r) {
    QVERIFY2(r.valid && r.error.isEmpty(), "well-formed candle was rejected");
    QVERIFY(std::isfinite(r.current.value("value")));
    QVERIFY(r.current.value("direction")==1.0 || r.current.value("direction")==-1.0);
}
} // namespace

class SupertrendInputGuardQt : public QObject {
    Q_OBJECT
private slots:
    void valid_history_and_first_warmup();
    void nonfinite_prices_fail_closed();
    void structurally_invalid_candles_fail_closed();
    void malformed_period_and_multiplier_fail_closed();
    void flat_and_zero_volume_are_not_silently_marked_bad_prices();
    void asof_prefix_does_not_inspect_future_corruption();
};

void SupertrendInputGuardQt::valid_history_and_first_warmup() {
    require_rejected(calc(candles(9)));
    require_rejected(calc(candles(10)));
    require_valid(calc(candles(11)));
    require_valid(calc(candles(60)));
}

void SupertrendInputGuardQt::nonfinite_prices_fail_closed() {
    for (int which=0; which<6; ++which) {
        auto c = candles();
        const double bad = which<4?std::numeric_limits<double>::quiet_NaN()
                                   :std::numeric_limits<double>::infinity();
        if (which==0) c.last().close=bad;
        if (which==1) c[48].close=bad;
        if (which==2) c.last().open=bad;
        if (which==3) c.last().high=bad;
        if (which==4) c.last().close=bad;
        if (which==5) c.last().low=-bad;
        require_rejected(calc(c));
    }
}

void SupertrendInputGuardQt::structurally_invalid_candles_fail_closed() {
    for (int which=0; which<4; ++which) {
        auto c = candles();
        if (which==0) c.last().high=c.last().low-2.;
        if (which==1) c.last().close=c.last().high+25.;
        if (which==2) c.last().open=c.last().low-25.;
        if (which==3) c[20].close=c[20].low-2.;
        require_rejected(calc(c));
    }
}

void SupertrendInputGuardQt::malformed_period_and_multiplier_fail_closed() {
    require_rejected(calc(candles(),{{"period",0},{"multiplier",3.}}));
    require_rejected(calc(candles(),{{"period",-10},{"multiplier",3.}}));
    require_rejected(calc(candles(),{{"period",1},{"multiplier",3.}}));
    require_rejected(calc(candles(),{{"period","10"},{"multiplier",3.}}));
    require_rejected(calc(candles(),{{"period",2.5},{"multiplier",3.}}));
    require_rejected(calc(candles(),{{"period",10},{"multiplier",0.}}));
    require_rejected(calc(candles(),{{"period",10},{"multiplier",-3.}}));
    require_rejected(calc(candles(),{{"period",10},{"multiplier","3.0"}}));
    require_rejected(calc(candles(),{{"period",10},{"multiplier",false}}));
    require_valid(calc(candles(),{{"period",10}})); // documented default multiplier
}

void SupertrendInputGuardQt::flat_and_zero_volume_are_not_silently_marked_bad_prices() {
    auto c = candles();
    for (auto& bar:c) {
        bar.open=bar.high=bar.low=bar.close=100.;
        bar.volume=0.;
    }
    // Defined numeric output, but a separate research eligibility gate should
    // reject flat/zero-volume *signals*, not mislabel these as malformed OHLC.
    require_valid(calc(c));
}

void SupertrendInputGuardQt::asof_prefix_does_not_inspect_future_corruption() {
    auto c = candles();
    const auto prefix = c.mid(0,40);
    const auto expected = calc(prefix);
    require_valid(expected);
    c[45].close=std::numeric_limits<double>::quiet_NaN();
    const auto before = calc(c.mid(0,40));
    require_valid(before);
    QCOMPARE(before.current.value("value"),expected.current.value("value"));
    require_rejected(calc(c));
}

QTEST_GUILESS_MAIN(SupertrendInputGuardQt)
#include "tst_supertrend_input_guard.moc"
