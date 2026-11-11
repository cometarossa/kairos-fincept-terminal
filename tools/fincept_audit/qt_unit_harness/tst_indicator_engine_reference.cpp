// KAIROS QA-LOCAL reference test for src/algo_engine/IndicatorEngine.{h,cpp}.
//
// The upstream suite (fincept-qt/tests/tst_indicator_engine.cpp) checks that the
// indicators return finite values. This one checks the VALUES: every number in
// kExpected was computed outside C++ by tools/fincept_audit/indicator_reference_v1.py
// from the textbook definition with exact rational arithmetic, on the integer
// fixture that fixture() below rebuilds with the same formula.
//
// No Fincept source is modified; the engine is compiled as is. Synthetic data
// only: a pass says the arithmetic follows the stated definitions on this
// fixture, nothing about any strategy or market.

#include "algo_engine/AlgoEngineTypes.h"
#include "algo_engine/IndicatorEngine.h"

#include <QJsonDocument>
#include <QJsonObject>
#include <QString>
#include <QTest>
#include <QVector>

#include <algorithm>
#include <cmath>

using fincept::algo::IndicatorEngine;
using fincept::algo::IndicatorResult;
using fincept::algo::OhlcvCandle;

namespace {

struct Expected {
    const char* indicator;
    const char* params_json;
    const char* key;
    double current;
    double previous;
};

// BEGIN GENERATED REFERENCE (tools/fincept_audit/indicator_reference_v1.py)
// bars=120  schema=kairos_fincept_indicator_reference_v1
static const Expected kExpected[] = {
    {"SMA", "{\"period\":14}", "value", 110.045, 110.07285714285715},
    {"EMA", "{\"period\":14}", "value", 110.03510767939771, 109.99127809161274},
    {"WMA", "{\"period\":14}", "value", 110.21219047619047, 110.17923809523809},
    {"DEMA", "{\"period\":10}", "value", 110.59261351072256, 110.62801264322533},
    {"TEMA", "{\"period\":10}", "value", 110.60239077043937, 110.70054340748422},
    {"RSI", "{\"period\":14}", "value", 52.04019665054855, 55.309832652257796},
    {"MACD", "{\"fast\":12,\"signal\":9,\"slow\":26}", "line", 0.6146028156031352, 0.6435178611803288},
    {"MACD", "{\"fast\":12,\"signal\":9,\"slow\":26}", "signal_line", 0.6212780829055258, 0.6229468997311234},
    {"MACD", "{\"fast\":12,\"signal\":9,\"slow\":26}", "histogram", -0.006675267302390511, 0.020570961449205467},
    {"STOCHASTIC", "{\"d_period\":3,\"k_period\":14}", "k", 53.333333333333336, 86.41975308641975},
    {"STOCHASTIC", "{\"d_period\":3,\"k_period\":14}", "d", 59.934922002105466, 64.98229495645516},
    {"CCI", "{\"period\":20}", "value", 41.15930174192709, 137.64002553833652},
    {"WILLIAMS_R", "{\"period\":14}", "value", -46.666666666666664, -13.580246913580247},
    {"MFI", "{\"period\":14}", "value", 36.4240255964145, 43.802356595580925},
    {"ROC", "{\"period\":10}", "value", 0.9516837481698389, 1.0132078885471323},
    {"AROON", "{\"period\":14}", "up", 92.85714285714286, 100.0},
    {"AROON", "{\"period\":14}", "down", 14.285714285714286, 21.428571428571427},
    {"ATR", "{\"period\":14}", "value", 1.9713076430151717, 1.9929466924778771},
    {"BOLLINGER", "{\"period\":20,\"std_dev\":2.0}", "upper", 111.97501153297067, 111.99585530527959},
    {"BOLLINGER", "{\"period\":20,\"std_dev\":2.0}", "middle", 109.8615, 109.7455},
    {"BOLLINGER", "{\"period\":20,\"std_dev\":2.0}", "lower", 107.74798846702934, 107.49514469472041},
    {"BOLLINGER", "{\"period\":20,\"std_dev\":2.0}", "width", 0.038475927107688546, 0.04101043423702276},
    {"BOLLINGER", "{\"period\":20,\"std_dev\":2.0}", "pct_b", 0.6084687717212387, 0.9253772716486957},
    {"KELTNER", "{\"multiplier\":1.5,\"period\":20}", "upper", 112.71525940483711, 112.70054986850418},
    {"KELTNER", "{\"multiplier\":1.5,\"period\":20}", "middle", 109.77292180178425, 109.71533462302469},
    {"KELTNER", "{\"multiplier\":1.5,\"period\":20}", "lower", 106.83058419873139, 106.73011937754521},
    {"DONCHIAN", "{\"period\":20}", "upper", 112.21, 112.21},
    {"DONCHIAN", "{\"period\":20}", "lower", 107.35, 107.35},
    {"OBV", "{}", "value", -28866.0, -27599.0},
    {"CMF", "{\"period\":20}", "value", -0.12890443174209684, -0.13901640435600282},
    {"VWAP", "{}", "value", 105.31390461038043, 105.26744355573314},
    {"VOL_WIN_CHG", "{\"window\":10}", "value", -0.8485362749257531, 0.858000858000858},
    {"ICHIMOKU", "{\"kijun\":26,\"senkou\":52,\"tenkan\":9}", "tenkan_sen", 110.215, 110.215},
    {"ICHIMOKU", "{\"kijun\":26,\"senkou\":52,\"tenkan\":9}", "kijun_sen", 109.44, 109.44},
    {"ICHIMOKU", "{\"kijun\":26,\"senkou\":52,\"tenkan\":9}", "senkou_a", 109.8275, 109.8275},
    {"ICHIMOKU", "{\"kijun\":26,\"senkou\":52,\"tenkan\":9}", "senkou_b", 108.23, 108.23},
};
// END GENERATED REFERENCE

constexpr int kBars = 120;

// Same integer-cent formula as fixture() in indicator_reference_v1.py.
QVector<OhlcvCandle> fixture() {
    QVector<OhlcvCandle> out;
    out.reserve(kBars);
    for (int i = 0; i < kBars; ++i) {
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

// Relative 1e-9 with an absolute floor for values near zero (MACD histogram, CMF).
bool close_enough(double got, double want) {
    if (!std::isfinite(got))
        return false;
    return std::abs(got - want) <= 1e-9 * std::max(1.0, std::abs(want));
}

} // namespace

class TstIndicatorEngineReference : public QObject {
    Q_OBJECT

  private slots:
    void fixture_is_the_documented_one();
    void every_indicator_matches_the_exact_reference_data();
    void every_indicator_matches_the_exact_reference();
    void a_shifted_fixture_does_not_match();
};

void TstIndicatorEngineReference::fixture_is_the_documented_one() {
    const auto candles = fixture();
    QCOMPARE(candles.size(), kBars);
    // Spot values worked out by hand from the formula (i = 0, 1, 119).
    QCOMPARE(candles[0].close, 98.11);   // 10000 - 165 - 24
    QCOMPARE(candles[0].open, 97.86);
    QCOMPARE(candles[0].high, 98.31);
    QCOMPARE(candles[0].low, 97.71);
    QCOMPARE(candles[0].volume, 1000.0);
    QCOMPARE(candles[1].close, 100.38);  // 10009 + (14-11)*15 + (1-3)*8
    QCOMPARE(candles[119].volume, 1267.0); // 1000 + (6307 % 200) + 4*40
    for (const auto& c : candles) {
        QVERIFY(c.high >= std::max(c.open, c.close));
        QVERIFY(c.low <= std::min(c.open, c.close));
        QVERIFY(c.volume > 0);
    }
}

void TstIndicatorEngineReference::every_indicator_matches_the_exact_reference_data() {
    QTest::addColumn<QString>("indicator");
    QTest::addColumn<QString>("params_json");
    QTest::addColumn<QString>("key");
    QTest::addColumn<double>("current");
    QTest::addColumn<double>("previous");
    for (const Expected& e : kExpected) {
        const QByteArray tag = QByteArray(e.indicator) + "." + e.key;
        QTest::newRow(tag.constData()) << QString::fromLatin1(e.indicator) << QString::fromLatin1(e.params_json)
                                       << QString::fromLatin1(e.key) << e.current << e.previous;
    }
}

void TstIndicatorEngineReference::every_indicator_matches_the_exact_reference() {
    QFETCH(QString, indicator);
    QFETCH(QString, params_json);
    QFETCH(QString, key);
    QFETCH(double, current);
    QFETCH(double, previous);

    const QJsonObject params = QJsonDocument::fromJson(params_json.toUtf8()).object();
    const IndicatorResult r = IndicatorEngine::compute(indicator, fixture(), params, key);
    QVERIFY2(r.valid, qPrintable(r.error));
    QVERIFY2(r.current.contains(key), qPrintable(QStringLiteral("missing current key ") + key));
    QVERIFY2(r.previous.contains(key), qPrintable(QStringLiteral("missing previous key ") + key));

    const double got_current = r.current.value(key);
    const double got_previous = r.previous.value(key);
    QVERIFY2(close_enough(got_current, current),
             qPrintable(QStringLiteral("current: engine %1, reference %2")
                            .arg(got_current, 0, 'g', 17).arg(current, 0, 'g', 17)));
    QVERIFY2(close_enough(got_previous, previous),
             qPrintable(QStringLiteral("previous: engine %1, reference %2")
                            .arg(got_previous, 0, 'g', 17).arg(previous, 0, 'g', 17)));
}

// The comparison must be able to fail: move one close by a cent and the
// close-based references no longer hold.
void TstIndicatorEngineReference::a_shifted_fixture_does_not_match() {
    auto candles = fixture();
    candles[kBars - 1].close += 0.01;
    int mismatches = 0;
    for (const Expected& e : kExpected) {
        const QJsonObject params = QJsonDocument::fromJson(QByteArray(e.params_json)).object();
        const IndicatorResult r =
            IndicatorEngine::compute(QString::fromLatin1(e.indicator), candles, params, QString::fromLatin1(e.key));
        if (!r.valid || !close_enough(r.current.value(QString::fromLatin1(e.key)), e.current))
            ++mismatches;
    }
    // Donchian, Aroon, Ichimoku and the volume-window change do not read the last close.
    QVERIFY2(mismatches >= 25, qPrintable(QStringLiteral("only %1 references noticed the change").arg(mismatches)));
}

QTEST_GUILESS_MAIN(TstIndicatorEngineReference)
#include "tst_indicator_engine_reference.moc"
