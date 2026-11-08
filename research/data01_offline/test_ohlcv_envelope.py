import unittest
from datetime import datetime, timezone
from copy import deepcopy
from ohlcv_envelope import prepare, Rejected

def ts(s): return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())
def fixture():
    meta = dict(source_id="fixture-v1", classification="SYNTHETIC_FIXTURE",
                retrieved_at="2024-01-04T00:00:00Z",
                requested_from="2024-01-01T00:00:00Z",
                requested_to="2024-01-03T00:00:00Z",
                symbol="KAIROS_FIXTURE", interval="1d", currency="USD",
                rights="FIXTURE_ONLY")
    rows = [{"t":ts("2024-01-01T00:00:00Z"),"o":10,"h":12,"l":9,"c":11,"v":100},
            {"t":ts("2024-01-02T00:00:00Z"),"o":11,"h":13,"l":10,"c":12,"v":110}]
    return rows,meta

class EnvelopeTests(unittest.TestCase):
    def test_success_deterministic(self):
        a,m=fixture(); x=prepare(a,m); y=prepare(a,m)
        self.assertEqual(x,y)
        self.assertEqual(x["data_envelope"]["bar_count"],2)
        self.assertEqual(x["data_envelope"]["coverage"],"UNVERIFIED_SESSION_CALENDAR")
        self.assertEqual(x["data_envelope"]["scientific_status"],"NOT_EVALUATED")
        self.assertFalse(x["data_envelope"]["broker_authority"])
    def test_rejects_false_market_provenance(self):
        a,m=fixture();m["classification"]="BROKER_OBSERVED"
        with self.assertRaises(Rejected):prepare(a,m)
    def test_rejects_rights(self):
        a,m=fixture();m["rights"]="UNKNOWN"
        with self.assertRaises(Rejected):prepare(a,m)
    def test_rejects_out_of_order(self):
        a,m=fixture();a.reverse()
        with self.assertRaises(Rejected):prepare(a,m)
    def test_rejects_duplicate(self):
        a,m=fixture();a[1]["t"]=a[0]["t"]
        with self.assertRaises(Rejected):prepare(a,m)
    def test_rejects_outside(self):
        a,m=fixture();a[0]["t"]=ts("2023-12-31T00:00:00Z")
        with self.assertRaises(Rejected):prepare(a,m)
    def test_rejects_invalid_prices(self):
        a,m=fixture();a[0]["h"]=1
        with self.assertRaises(Rejected):prepare(a,m)
    def test_rejects_nan(self):
        a,m=fixture();a[0]["c"]=float("nan")
        with self.assertRaises(Rejected):prepare(a,m)
    def test_rejects_timestamp_without_utc(self):
        a,m=fixture();m["requested_from"]="2024-01-01T00:00:00+01:00"
        with self.assertRaises(Rejected):prepare(a,m)
    def test_rejects_extra_fields(self):
        a,m=fixture();m["broker_key"]="never"
        with self.assertRaises(Rejected):prepare(a,m)
    def test_rejects_bad_time(self):
        a,m=fixture();m["retrieved_at"]="2024-01-01T00:00:00Z"
        with self.assertRaises(Rejected):prepare(a,m)
    def test_no_mutation(self):
        a,m=fixture();aa=deepcopy(a);mm=deepcopy(m)
        prepare(a,m)
        self.assertEqual((a,m),(aa,mm))

if __name__=="__main__": unittest.main()
