import sys,unittest,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"fincept-qt/scripts"))
from screener_snapshot_v1 import project,MIXED_TIME_WARNING
NOW=1795730000
def sample():
    return dict(source="Yahoo Finance screener",kind="predefined",screen_id="day_gainers",offset=0,warnings=[MIXED_TIME_WARNING],count=2,total=2,fetched_at=NOW,as_of=NOW-10,rows=[dict(symbol=s,price=10.,currency="USD",market_time=NOW-d,delay_min=15) for s,d in (("QA-A",10),("QA-B",11))])
class Mixed(unittest.TestCase):
    def test_valid(self):
        x=sample();r=project(x,now=NOW)
        self.assertEqual(r["rows"],x["rows"])
        self.assertNotIn("as_of",r)
        self.assertIs(r["market_as_of_verified"],False)
        self.assertIs(r["execution_authority"],False)
    def test_invalid_warning_or_asof(self):
        for changes in ({"warnings":[]},{"warnings":[MIXED_TIME_WARNING,"other"]},{"warnings":[MIXED_TIME_WARNING]*2},{"warnings":["unknown"]},{"as_of":NOW-11},{"as_of":True},{"as_of":None},{"as_of":float(NOW-10)}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):project(dict(sample(),**changes),now=NOW)
    def test_warning_not_corroborated(self):
        x=sample();x["rows"][1]["market_time"]=NOW-10
        with self.assertRaises(ValueError):project(x,now=NOW)
        x["warnings"]=[]
        self.assertEqual(project(x,now=NOW)["count"],2)
    def test_invalid_rows(self):
        for field,value in (("market_time",None),("market_time",NOW+1),("market_time",True),("delay_min",None),("delay_min",-1),("price",float("nan")),("currency","EUR"),("symbol","QA-A")):
            x=sample();x["rows"][1][field]=value
            with self.subTest(field=field,value=value):
                with self.assertRaises(ValueError):project(x,now=NOW)
    def test_local_ttl_not_market_freshness(self):
        x=sample();x["rows"][1]["market_time"]=1
        r=project(x,now=NOW+599)
        self.assertEqual(r["rows"][1]["market_time"],1)
        self.assertFalse(r["market_as_of_verified"])
        with self.assertRaises(ValueError):project(x,now=NOW+600)
