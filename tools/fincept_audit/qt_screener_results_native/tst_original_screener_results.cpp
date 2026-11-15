// Source-real Fincept ScreenerResultsModel regression: synthetic rows only.
// QtCore+QtGui+QtTest, no window, storage, provider, network or broker.
#include "screens/screener/ScreenerResultsModel.h"
#include <QCoreApplication>
#include <QSignalSpy>
#include <QStringList>
#include <QVector>
#include <QAbstractItemModel>
#include <limits>
#include <cmath>
#include <cstdio>

using fincept::screens::ScreenerResultsModel;
using fincept::screens::ScreenerSortProxy;
using fincept::services::ScreenerRow;
using fincept::services::ScreenerColumn;

static int failures = 0;
static int checks = 0;
#define CHECK(C, MSG) do { ++checks; if (!(C)) { std::fprintf(stderr, "FAIL %s\n",MSG); ++failures; } } while(0)

static ScreenerRow make_row(const QString& symbol, const QString& name,
                           double price, double extra_value) {
    ScreenerRow r;
    r.symbol=symbol; r.name=name; r.sector="Technology";
    r.industry="Software"; r.currency="USD"; r.exchange="NMS";
    r.exchange_name="Nasdaq";
    r.price=price; r.change_pct=1.25; r.volume=1234567;
    r.market_cap=1200000000; r.pe=18.25;
    if (std::isfinite(extra_value)) r.fields.insert("growth",extra_value);
    return r;
}

int main(int argc, char** argv) {
    QCoreApplication app(argc,argv);
    ScreenerResultsModel model;
    QStringList headers={"Symbol","Name","Price","Change","Volume",
                         "Market Cap","P/E","Sector","Exchange","Currency"};
    model.set_base_headers(headers,headers);
    ScreenerColumn growth;
    growth.id="growth"; growth.field="revenue_growth";
    growth.label="Revenue Growth"; growth.unit="pct";
    growth.description="Synthetic revenue growth";
    const double nan=std::numeric_limits<double>::quiet_NaN();
    QVector<ScreenerRow> rows={
        make_row("AAA","Alpha Systems",100,11.5),
        make_row("BBB","Beta Labs",9.5,-2.5),
        make_row("CCC","Gamma Holdings",nan,nan),
    };
    model.set_result(rows,{growth});
    CHECK(model.rowCount()==3, "3 original synthetic rows");
    CHECK(model.columnCount()==11, "10 base + 1 dynamic column");
    CHECK(model.headerData(10,Qt::Horizontal).toString()=="REVENUE GROWTH", "dynamic header");
    CHECK(model.data(model.index(0,ScreenerResultsModel::ColPrice)).toString()=="100.00",
          "display price formatting");
    CHECK(model.data(model.index(1,ScreenerResultsModel::ColPrice)).toString()=="9.50",
          "decimal price formatting");
    CHECK(model.data(model.index(2,ScreenerResultsModel::ColPrice)).toString()=="—",
          "missing price marker");
    CHECK(!model.data(model.index(2,ScreenerResultsModel::ColPrice),ScreenerResultsModel::SortRole).isValid(),
          "missing price sorting sentinel");
    CHECK(model.data(model.index(0,10)).toString()=="+11.50%", "extra percent field");
    CHECK(model.data(model.index(1,10)).toString()=="-2.50%", "negative percentage field");
    CHECK(model.data(model.index(1,0),ScreenerResultsModel::SearchRole).toString().contains("Beta Labs"),
          "search role includes name");
    CHECK(model.index_of_key("AAA")==0 && model.row_for_key("BBB")!=nullptr,
          "stable key-based lookup");
    CHECK(model.is_numeric_column(2) && model.is_numeric_column(10) &&
          !model.is_numeric_column(0), "numeric column designation");

    ScreenerSortProxy proxy;
    proxy.setSourceModel(&model);
    proxy.setSortRole(ScreenerResultsModel::SortRole);
    auto symbol_at=[&](int pos) {
        return proxy.data(proxy.index(pos,ScreenerResultsModel::ColSymbol),Qt::DisplayRole).toString();
    };
    proxy.sort(ScreenerResultsModel::ColPrice,Qt::AscendingOrder);
    CHECK(symbol_at(0)=="BBB" && symbol_at(1)=="AAA" && symbol_at(2)=="CCC",
          "numeric ascending with missing last");
    proxy.sort(ScreenerResultsModel::ColPrice,Qt::DescendingOrder);
    CHECK(symbol_at(0)=="AAA" && symbol_at(1)=="BBB" && symbol_at(2)=="CCC",
          "numeric descending with missing last");

    QSignalSpy dataSpy(&model,&QAbstractItemModel::dataChanged);
    QSignalSpy resetSpy(&model,&QAbstractItemModel::modelReset);
    rows[1].price=10.75;
    model.set_result(rows,{growth});
    CHECK(model.index_of_key("BBB")==1, "stable model row key after single-tick update");
    CHECK(dataSpy.count()>0, "changed cell sends dataChanged signal");
    CHECK(resetSpy.count()==0, "same row keys do not reset entire table");
    CHECK(model.data(model.index(1,ScreenerResultsModel::ColPrice)).toString()=="10.75",
          "price new display after tick");

    ScreenerColumn ratio=growth;
    ratio.id="profit_margin"; ratio.label="Profit Margin";
    model.set_result(rows,{ratio});
    CHECK(model.rowCount()==3 && model.columnCount()==11, "replacement extra column schema");
    CHECK(resetSpy.count()>0, "dynamic column id change resets table");
    CHECK(model.headerData(10,Qt::Horizontal).toString()=="PROFIT MARGIN",
          "changed dynamic column header");
    CHECK(!model.data(model.index(0,10),ScreenerResultsModel::SortRole).isValid(),
          "missing dynamic metric has invalid sort role");

    CHECK(fincept::screens::screener_format::compact(1234567)=="1.23M",
          "SI compact formatting");
    CHECK(fincept::screens::screener_format::price(0.1234)=="0.1234",
          "small price 4 decimals");
    CHECK(fincept::screens::screener_format::percent(3.25,true)=="+3.25%",
          "positive percent sign");
    std::printf("FINCEPT_ORIGINAL_SCREENER_MODEL_RESULTS: %d checks, %d failures\n",checks,failures);
    return failures?1:0;
}
