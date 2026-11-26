#include "ReadonlyQuoteInbox.h"
#include <QCoreApplication>
#include <QDir>
#include <QTemporaryDir>
#include <cstdio>
using namespace fincept::services::readonly_quote;
int main(int argc,char**argv) {
    QCoreApplication app(argc,argv);
    constexpr qint64 now=1795649670;
    const double p=100.123456, prev=99.12, change=p-prev;
    QJsonObject q{{"schema","YAHOO_PROVIDER_CLAIMED_QUOTE_V1"},{"provider","Yahoo Finance via original yfinance"},{"symbol","SPY"},
      {"price",p},{"previous_close",prev},{"change",change},{"change_percent",100*(change/prev)},{"high",101},{"low",98},{"volume",1000},
      {"provider_claimed_market_time_unix",now-10},{"local_received_at_unix",now-1},{"market_as_of_verified",false},{"freshness_verified",false},
      {"research_only",true},{"execution_authority",false},{"scientific_claim",false},{"broker_calls",0}};
    auto wrap=[&](QByteArray b){return QJsonDocument(QJsonObject{{"schema","YAHOO_QUOTE_SNAPSHOT_V1"},{"provider","Yahoo Finance via original yfinance"},
        {"symbol","SPY"},{"captured_at_unix",now},{"quote_sha256",QString::fromLatin1(QCryptographicHash::hash(b,QCryptographicHash::Sha256).toHex())},
        {"quote_base64",QString::fromLatin1(b.toBase64())}}).toJson(QJsonDocument::Compact);};
    const auto payload=QJsonDocument(q).toJson(QJsonDocument::Compact);
    const auto raw=wrap(payload);
    int checks=0;
    auto ck=[&](bool good,const char* label){if(!good){std::fprintf(stderr,"FAIL %s\n",label);std::exit(1);}++checks;};
    ck(decode(raw,"SPY",now).has_value(),"valid");
    ck(!decode(raw,"EURUSD=X",now),"wrong asset");
    ck(!decode(raw,"SPY",now+61),"expired");
    ck(!decode(raw,"SPY",now-1),"future capture");
    ck(!decode(wrap(payload.chopped(1)+",\"symbol\":\"SPY\"}"),"SPY",now),"duplicate");
    auto bad=q;bad["execution_authority"]=true;ck(!decode(wrap(QJsonDocument(bad).toJson(QJsonDocument::Compact)),"SPY",now),"authority");
    bad=q;bad["provider_claimed_market_time_unix"]=now-901;ck(!decode(wrap(QJsonDocument(bad).toJson(QJsonDocument::Compact)),"SPY",now),"stale claim");
    bad=q;bad["volume"]=true;ck(!decode(wrap(QJsonDocument(bad).toJson(QJsonDocument::Compact)),"SPY",now),"bool volume");
    bad=q;bad["change"]=0;ck(!decode(wrap(QJsonDocument(bad).toJson(QJsonDocument::Compact)),"SPY",now),"arithmetic");
    QTemporaryDir dir;ck(dir.isValid(),"temp");
    ck(QDir(dir.path()).mkdir("SPY"),"child");
    auto child=dir.path()+"/SPY";QFile::setPermissions(child,QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner);
    QFile file(child+"/snapshot.json");ck(file.open(QIODevice::WriteOnly|QIODevice::NewOnly),"write");
    ck(file.write(raw)==raw.size(),"bytes");file.close();QFile::setPermissions(file.fileName(),QFileDevice::ReadOwner|QFileDevice::WriteOwner);
    ck(read(dir.path(),"SPY",now).has_value(),"private file");
    QFile::setPermissions(file.fileName(),QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ReadOther);
    ck(!read(dir.path(),"SPY",now),"public file denied");
    std::printf("NATIVE_QT_QUOTE_INBOX %d/%d PASS\n",checks,checks);
}
