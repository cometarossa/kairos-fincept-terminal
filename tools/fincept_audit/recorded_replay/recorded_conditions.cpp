// Read-only offline signal comparison executable; consume filtered OHLCV on stdin.
// This program has no broker, account, networking, runtime service or trade path.
#include "algo_engine/ConditionEvaluator.h"
#include "algo_engine/IndicatorEngine.h"
#include <QDate>
#include <QJsonObject>
#include <QTextStream>
#include <QStringList>
#include <QVector>
#include <cmath>
#include <cstdio>
#include <limits>

using fincept::algo::OhlcvCandle;
using fincept::algo::ConditionEvaluator;
using fincept::services::algo::ConditionDef;

struct Rule {
    QString name;
    ConditionDef def;
};

static QVector<Rule> make_rules() {
    QVector<Rule> out;
    const QJsonObject adx{{"period", 14}};
    const QJsonObject st{{"period", 10}, {"multiplier", 3.0}};
    auto rule = [&](const QString& label, const QString& name, const QJsonObject& params,
                    const QString& field, const QString& op, double target = 0.0) {
        ConditionDef d;
        d.indicator = name;
        d.params = params;
        d.field = field;
        d.op = op;
        d.value = target;
        out.append({label, d});
        return out.size()-1;
    };
    for (const QString& crossing : {QStringLiteral("crosses_above"), QStringLiteral("crosses_below")}) {
        const int idx = rule(crossing == "crosses_above" ? "ADX_DI_CROSS_UP" : "ADX_DI_CROSS_DOWN",
                             "ADX", adx, "plus_di", crossing);
        out[idx].def.compare_mode = "indicator";
        out[idx].def.compare_indicator = "ADX";
        out[idx].def.compare_params = adx;
        out[idx].def.compare_field = "minus_di";
    }
    rule("ST_VALUE_FALLING", "SUPERTREND", st, "value", "falling");
    rule("ST_VALUE_RISING", "SUPERTREND", st, "value", "rising");
    rule("ST_DIRECTION_UP_CROSS", "SUPERTREND", st, "direction", "crosses_above", 0.);
    rule("ST_DIRECTION_DOWN_CROSS", "SUPERTREND", st, "direction", "crosses_below", 0.);
    rule("ST_LONG_STATE", "SUPERTREND", st, "direction", ">", 0.);
    for (const QString& relation : {QStringLiteral("<"), QStringLiteral(">")}) {
        const int idx = rule(relation == "<" ? "ST_LINE_BELOW_CLOSE" : "ST_LINE_ABOVE_CLOSE",
                            "SUPERTREND", st, "value", relation);
        out[idx].def.compare_mode = "indicator";
        out[idx].def.compare_indicator = "CLOSE";
        out[idx].def.compare_field = "value";
    }
    return out;
}

static bool parse_number(const QString& s, double* val) {
    bool ok = false;
    *val = s.toDouble(&ok);
    return ok && std::isfinite(*val);
}

int main() {
    QTextStream input(stdin);
    QTextStream output(stdout);
    QVector<OhlcvCandle> all;
    QVector<QDate> dates;
    all.reserve(1050);
    while (!input.atEnd()) {
        const QString line = input.readLine();
        if (line.trimmed().isEmpty()) continue;
        const QStringList fields = line.split(',');
        if (fields.size() != 6) {
            std::fprintf(stderr, "INVALID_SCHEMA\n");
            return 2;
        }
        const QDate date = QDate::fromString(fields[0], "yyyy-MM-dd");
        if (!date.isValid() || (!dates.isEmpty() && !(dates.back() < date)) ||
            date < QDate(2014, 1, 1) || date > QDate(2017, 11, 10)) {
            std::fprintf(stderr, "INVALID_DATE_OR_ORDER\n");
            return 3;
        }
        double o=0,h=0,l=0,c=0,v=0;
        if (!parse_number(fields[1], &o) || !parse_number(fields[2], &h) ||
            !parse_number(fields[3], &l) || !parse_number(fields[4], &c) ||
            !parse_number(fields[5], &v) || h < l || c > h || c < l ||
            o > h || o < l || v < 0) {
            std::fprintf(stderr, "INVALID_OHLCV\n");
            return 4;
        }
        OhlcvCandle candle;
        candle.open = o;
        candle.high = h;
        candle.low = l;
        candle.close = c;
        candle.volume = v;
        // UTC midnight without timezone/DST ambiguity: date is ISO calendar day.
        candle.open_time =
            static_cast<qint64>(date.toJulianDay() - QDate(1970, 1, 1).toJulianDay()) * 86400;
        candle.close_time = candle.open_time + 86400 - 1;
        candle.is_closed = true;
        all.append(candle);
        dates.append(date);
    }
    if (all.size() != 974 || dates.front() != QDate(2014, 1, 2) ||
        dates.back() != QDate(2017, 11, 10)) {
        std::fprintf(stderr, "EXPECTED_REPLAY_WINDOW_NOT_PRESENT n=%d\n", static_cast<int>(all.size()));
        return 5;
    }
    const auto rules = make_rules();
    if (rules.size() != 9) return 6;
    output << "#schema=fincept_recorded_signal_mask_v1;rules=";
    for (int i=0; i<rules.size(); ++i) {
        if (i) output << "|";
        output << rules[i].name;
    }
    output << "\n";
    for (int n=61; n<=all.size(); ++n) {
        if (dates[n - 1] < QDate(2015, 1, 1)) continue;
        const auto prefix = all.mid(0, n);
        unsigned mask=0;
        for (int k=0; k<rules.size(); ++k) {
            const auto check=ConditionEvaluator::evaluate_single(rules[k].def,prefix);
            if (!check.error.isEmpty()) {
                std::fprintf(stderr, "INVALID_CONDITION bar=%d rule=%d\n", n, k);
                return 7;
            }
            if (check.met) mask |= (1u << k);
        }
        output << dates[n - 1].toString("yyyy-MM-dd") << "," << mask << "\n";
    }
    output.flush();
    return 0;
}
