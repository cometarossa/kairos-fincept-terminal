// Native source-real QA of Fincept's unmodified ScreenerCriteriaBuilder.
// Synthetic local catalog only; no Fincept app, provider, storage, account or broker.
#include "screens/screener/ScreenerCriteriaBuilder.h"
#include <QApplication>
#include <QJsonArray>
#include <QJsonObject>
#include <QLineEdit>
#include <QSignalSpy>
#include <QString>
#include <QWidget>
#include <cstdio>

using fincept::screens::ScreenerCriteriaBuilder;
using fincept::services::ScreenerQuery;

static int checks = 0;
static int failures = 0;
#define CHECK(cond, description) do { \
  ++checks; \
  if (!(cond)) { std::fprintf(stderr, "FAIL: %s\n", description); ++failures; } \
} while (false)

static QJsonObject field(const char* id, const char* label, const char* unit = "money") {
    return QJsonObject{{"id", id}, {"label", label},
                       {"category", "Fundamental"}, {"unit", unit},
                       {"description", "Synthetic field"}};
}

static QJsonObject catalog() {
    return QJsonObject{
        {"categories", QJsonArray{"Fundamental"}},
        {"fields", QJsonArray{field("market_cap", "Market Cap", "mcap"),
                              field("price", "Price", "price")}},
        {"regions", QJsonArray{QJsonObject{{"code", "us"}, {"name", "United States"}}}},
        {"exchanges", QJsonObject{{"us", QJsonArray{
            QJsonObject{{"label", "US major exchanges"},
                        {"codes", QJsonArray{"NMS", "NGM", "NCM", "NYQ", "ASE"}}}
        }}}},
        {"sectors", QJsonArray{"Technology"}},
        {"industries", QJsonObject{{"Technology", QJsonArray{"Software", "Hardware"}}}},
        {"peer_groups", QJsonArray{"Software & Services"}}
    };
}

static QJsonArray filters_of(const ScreenerQuery& q) {
    return q.criteria.value("filters").toArray();
}

static QList<QLineEdit*> last_row_inputs(ScreenerCriteriaBuilder& builder) {
    const auto rows = builder.findChildren<QWidget*>("screenerCriterionRow");
    if (rows.isEmpty())
        return {};
    return rows.last()->findChildren<QLineEdit*>();
}

static void run_baseline() {
    ScreenerCriteriaBuilder builder;
    QString error;
    ScreenerQuery out;
    CHECK(!builder.has_catalog(), "no catalog before initialization");
    CHECK(!builder.build_query(&out, &error), "empty form refuses a query");
    CHECK(!error.isEmpty(), "empty-form error is visible");

    QSignalSpy changes(&builder, &ScreenerCriteriaBuilder::edited);
    builder.set_catalog(catalog());
    CHECK(builder.has_catalog(), "synthetic local catalog accepted");
    CHECK(changes.count() == 0, "programmatic reset suppresses edited");
    CHECK(builder.field_label("market_cap") == "Market Cap", "catalog label");
    CHECK(builder.field_label("unknown") == "unknown", "unknown label fallback");
    out.count = 200;
    out.offset = 37;
    error.clear();
    CHECK(builder.build_query(&out, &error), "default screen produces query");
    CHECK(out.count == 200 && out.offset == 37, "builder preserves paging");
    CHECK(out.predefined_id.isEmpty(), "default is a custom query");
    CHECK(out.criteria.value("region").toArray() == QJsonArray{"us"}, "default US region");
    CHECK(out.criteria.value("exchange").toArray().size() == 5, "default five exchanges");
    CHECK(out.sort_field == "market_cap" && !out.sort_asc, "default market-cap descending");
    CHECK(filters_of(out).size() == 1, "default one numeric filter");
    CHECK(filters_of(out).at(0).toObject().value("value").toDouble() == 2e9,
          "default market-cap cutoff is 2 billion");

    ScreenerQuery custom;
    custom.criteria = QJsonObject{
        {"region", QJsonArray{"us"}},
        {"sector", QJsonArray{"Technology"}},
        {"industry", QJsonArray{"Software"}},
        {"exchange", QJsonArray{"NMS", "NGM", "NCM", "NYQ", "ASE"}},
        {"filters", QJsonArray{
            QJsonObject{{"field", "market_cap"}, {"op", "gte"}, {"value", 1.5e9}},
            QJsonObject{{"field", "price"}, {"op", "btwn"},
                        {"value", QJsonArray{8.25, 19.75}}}
        }}
    };
    custom.sort_field = "price";
    custom.sort_asc = true;
    const int edits_before = changes.count();
    builder.load_query(custom);
    CHECK(changes.count() == edits_before, "load does not emit user edit events");
    ScreenerQuery rebuilt;
    rebuilt.count = 75;
    rebuilt.offset = 25;
    error.clear();
    CHECK(builder.build_query(&rebuilt, &error), "custom numeric + range query builds");
    CHECK(rebuilt.criteria == custom.criteria, "custom query canonical round-trip");
    CHECK(rebuilt.sort_field == "price" && rebuilt.sort_asc, "ascending sort round-trip");
    CHECK(rebuilt.count == 75 && rebuilt.offset == 25, "custom query paging retained");

    auto inputs = last_row_inputs(builder);
    CHECK(inputs.size() == 2, "latest criterion has two edit controls");
    if (inputs.size() == 2) {
        inputs.at(0)->setText("not-a-number");
        ScreenerQuery untouched;
        untouched.sort_field = "sentinel";
        untouched.count = 44;
        error.clear();
        CHECK(!builder.build_query(&untouched, &error), "bad numeric text rejected");
        CHECK(!error.isEmpty(), "bad numeric text has diagnostic");
        CHECK(inputs.at(0)->property("invalid").toBool(), "bad numeric cell marked");
        CHECK(untouched.sort_field == "sentinel" && untouched.count == 44,
              "failed build never partly overwrites output");
        inputs.at(0)->setText("8.25");
        inputs.at(1)->setText("");
        error.clear();
        CHECK(!builder.build_query(&untouched, &error), "missing BETWEEN high rejected");
        CHECK(inputs.at(1)->property("invalid").toBool(), "missing high cell marked");
        inputs.at(1)->setText("19.75");
        error.clear();
        CHECK(builder.build_query(&untouched, &error), "corrected range builds");
    }

    ScreenerQuery empty;
    builder.load_query(empty);
    error.clear();
    CHECK(!builder.build_query(&out, &error), "no universe or numeric filters rejected");
    CHECK(!error.isEmpty(), "no-filter query supplies diagnostic");
    ScreenerQuery predefined;
    predefined.predefined_id = "synthetic-predefined";
    builder.load_query(predefined);
    error.clear();
    CHECK(!builder.build_query(&out, &error), "predefined query not imported as criteria");
}

static void probe_defects() {
    // These strict probes are NOT registered as passing CTest assertions:
    // suspected source defects must be verified natively before classifying.
    ScreenerCriteriaBuilder builder;
    builder.set_catalog(catalog());
    auto inputs = last_row_inputs(builder);
    if (inputs.size() == 2) {
        inputs.at(0)->setText("1e308T");
        ScreenerQuery q;
        QString error;
        CHECK(!builder.build_query(&q, &error),
              "overflow after T multiplier must fail closed");
    }
    builder.reset_to_default();
    builder.set_catalog(QJsonObject{{"fields", QJsonArray{}}});
    ScreenerQuery q;
    QString error;
    CHECK(!builder.has_catalog(), "empty replacement catalog is unusable");
    CHECK(!builder.build_query(&q, &error),
          "stale criteria must not survive removal of catalog fields");
}

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    const bool strict = argc > 1 && QString::fromUtf8(argv[1]) == "--probe-defects";
    if (strict)
        probe_defects();
    else
        run_baseline();
    std::printf("%s: %d checks, %d failures\n", strict ? "STRICT" : "BASELINE",
                checks, failures);
    return failures == 0 ? 0 : 1;
}
