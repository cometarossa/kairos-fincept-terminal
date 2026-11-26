#include "services/screener/ReadonlyScreenerInbox.h"
#include <QCoreApplication>
#include <QTemporaryDir>
#include <QFile>
#include <cstdio>
using namespace fincept::services::readonly_screener;
static QByteArray seal(QByteArray bytes) {
    return QJsonDocument(QJsonObject{{"schema","FINCEPT_SCREENER_INBOX_V1"},
        {"payload_base64",QString::fromLatin1(bytes.toBase64())},
        {"payload_sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())}}).toJson(QJsonDocument::Compact);
}
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);
    if (argc == 3) {
        bool ok = false;
        const auto now = QString::fromLatin1(argv[2]).toLongLong(&ok);
        if (!ok) return 2;
        const auto result = read(QString::fromLocal8Bit(argv[1]), now);
        if (!result) return 1;
        const auto bytes = QJsonDocument(*result).toJson(QJsonDocument::Compact);
        std::fwrite(bytes.constData(),1,bytes.size(),stdout);
        std::fputc('\n',stdout);
        return 0;
    }
    int total=0, failed=0;
    auto check=[&](bool ok,const char* label){++total;if(!ok){++failed;std::fprintf(stderr,"FAIL %s\n",label);}};
    const qint64 now=1795730000, cap=now-2;
    QJsonObject row{{"symbol","QA-A"},{"price",10.0},{"currency","USD"},{"market_time",cap-10},{"delay_min",15}};
    QJsonObject receipt{{"schema","FINCEPT_SCREENER_SNAPSHOT_V1"},{"source","Yahoo Finance screener"},
        {"screen_id","day_gainers"},{"count",1},{"total",2},{"captured_at_unix",cap},{"valid_until_unix",cap+600},
        {"rows",QJsonArray{row}},{"research_only",true},{"market_as_of_verified",false},
        {"scientific_claim",false},{"execution_authority",false},{"broker_calls",0}};
    auto encode=[](QJsonObject o){return seal(QJsonDocument(o).toJson(QJsonDocument::Compact));};
    auto valid=encode(receipt);
    check(decode(valid,now).has_value(),"valid");
    check(request_allowed({{"screen_id","day_gainers"},{"limit",20}}),"request");
    check(!request_allowed({{"screen_id","day_gainers"},{"limit",20},{"force",true}}),"force");
    check(!request_allowed({{"screen_id","day_gainers"},{"limit",true}}),"bool limit");
    check(!decode(valid,cap+600),"expiry");
    check(!decode(valid,cap-1),"future");
    for (auto k : {"execution_authority","scientific_claim","market_as_of_verified"}) {auto o=receipt;o[k]=true;check(!decode(encode(o),now),k);}
    for (auto k : {"count","captured_at_unix","broker_calls"}) {auto o=receipt;o[k]=true;check(!decode(encode(o),now),k);}
    auto o=receipt;o["rows"]=QJsonArray{row,row};o["count"]=2;check(!decode(encode(o),now),"duplicate");
    o=receipt;o["extra"]=true;check(!decode(encode(o),now),"extra");
    auto raw=QJsonDocument(receipt).toJson(QJsonDocument::Compact);
    raw.insert(1,"\"count\":1,");check(!decode(seal(raw),now),"duplicate key");
    auto bad=valid;bad.replace("payload_sha256","invalid_sha256");check(!decode(bad,now),"digest field");
    o=receipt;auto r=row;r["price"]=0;o["rows"]=QJsonArray{r};check(!decode(encode(o),now),"zero");
    r=row;r["currency"]="EUR";o["rows"]=QJsonArray{r};check(!decode(encode(o),now),"currency");
    r=row;r["market_time"]=cap+1;o["rows"]=QJsonArray{r};check(!decode(encode(o),now),"future row");
    QTemporaryDir tmp; const auto path=tmp.path()+"/snapshot.json";
    QFile file(path);check(file.open(QIODevice::WriteOnly),"file create");file.write(valid);file.close();
    QFile::setPermissions(path,QFileDevice::ReadOwner|QFileDevice::WriteOwner);
    check(read(tmp.path(),now).has_value(),"private file");
    QFile::setPermissions(path,QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ReadOther);
    check(!read(tmp.path(),now),"unsafe mode");
    QFile::remove(path);check(!read(tmp.path(),now),"missing");
    std::printf("NATIVE_SCREENER %d/%d PASS\n",total-failed,total);return failed?1:0;
}
