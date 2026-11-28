import copy
import unittest
from datetime import date,timedelta,datetime
from decimal import Decimal
from twelve_fx_research_schema_v1 import qualify,Rejected

class TestSchema(unittest.TestCase):
    def setUp(self):
        self.first=date(2026,6,1)
        self.last=date(2026,11,27)
        self.bound=self.last+timedelta(days=1)
        rows=[]
        for i in range((self.last-self.first).days+1):
            d=self.last-timedelta(days=i)
            if d.weekday()<5:
                rows.append(dict(datetime=d.isoformat(),open="1.15000",high="1.16000",low="1.14000",close="1.15500"))
        self.p=dict(status="ok",meta=dict(symbol="EUR/USD",interval="1day",currency_base="EUR",currency_quote="USD"),values=rows)
    def runq(self,p=None,**kw):
        args=dict(first_day=self.first,last_day=self.last,completed_before=self.bound)
        args.update(kw)
        return qualify(self.p if p is None else p,**args)
    def reject(self,reason,mutate):
        p=copy.deepcopy(self.p);mutate(p)
        with self.assertRaisesRegex(Rejected,"^"+reason+"$"):self.runq(p)
    def test_valid(self):
        r=self.runq()
        self.assertEqual(len(r.bars),130)
        self.assertEqual(r.bars[0].session_date,self.first)
        self.assertEqual(r.bars[-1].session_date,self.last)
        self.assertEqual(r.bars[0].open,Decimal("1.15000"))
        self.assertFalse(r.market_admitted)
        self.assertFalse(hasattr(r.bars[0],"volume"))
        self.assertEqual(r.status,"OFFLINE_SHAPE_ONLY")
    def test_provider_error(self):
        self.reject("PROVIDER_NOT_OK",lambda p:p.update(status="error",message="FAKE_KEY"))
        self.reject("PROVIDER_NOT_OK",lambda p:p.update(code=429))
    def test_identity(self):
        for k,v in (("symbol","USD/EUR"),("interval","1h"),("currency_base","USD"),("currency_quote","JPY")):
            with self.subTest(k=k):self.reject("IDENTITY_INVALID",lambda p:p["meta"].update({k:v}))
    def test_tz(self):
        self.reject("TIMEZONE_UNVERIFIED",lambda p:p["meta"].update(exchange_timezone="UTC"))
    def test_duplicates(self):
        self.reject("DATE_ORDER",lambda p:p["values"][1].update(datetime=p["values"][0]["datetime"]))
    def test_ascending(self):
        self.reject("DATE_ORDER",lambda p:p["values"].reverse())
    def test_dates(self):
        for v in ("2026-02-30","2026-11-27T00:00:00",True,None):
            with self.subTest(v=v):self.reject("DATE_INVALID",lambda p:p["values"][0].update(datetime=v))
    def test_outside(self):
        self.reject("DATE_OUTSIDE_SCOPE",lambda p:p["values"][0].update(datetime="2026-11-28"))
    def test_price(self):
        for v in (0,True,None,"0","NaN","Infinity","1e0","-1","1.0000000000001"," 1.1"):
            with self.subTest(v=v):self.reject("PRICE_INVALID",lambda p:p["values"][0].update(open=v))
    def test_ohlc(self):
        for k,v in (("high","1.1"),("low","1.17")):
            with self.subTest(k=k):self.reject("OHLC_ORDER",lambda p:p["values"][40].update({k:v}))
    def test_count(self):
        self.reject("COUNT_INVALID",lambda p:p.update(values=p["values"][:99]))
        self.reject("COUNT_INVALID",lambda p:p.update(values=p["values"]*2))
    def test_span(self):
        self.reject("SPAN_INVALID",lambda p:p.update(values=p["values"][:100]))
    def test_scope(self):
        for kw in (dict(completed_before=self.last),dict(first_day=datetime(2026,6,1)),dict(first_day=self.last)):
            with self.subTest(kw=kw),self.assertRaisesRegex(Rejected,"^SCOPE_INVALID$"):self.runq(**kw)
    def test_missing_day_not_certified(self):
        del self.p["values"][30]
        r=self.runq()
        self.assertFalse(r.market_admitted)
        self.assertEqual(r.status,"OFFLINE_SHAPE_ONLY")

if __name__=="__main__":unittest.main()
