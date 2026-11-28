import json
import unittest
from urllib.parse import urlsplit, parse_qsl
from test_twelve_fx_research_schema_v1 import TestSchema
from twelve_fx_transport_qa_v1 import plan, transport_policy, evaluate_fixture, TransportRejected, FIXTURE_KEY, MAX_BYTES

class TestTransport(unittest.TestCase):
    def setUp(self):
        fixture=TestSchema()
        fixture.setUp()
        self.p=fixture.p
        self.kw=dict(first_day=fixture.first,last_day=fixture.last,completed_before=fixture.bound)
    def eval(self, status=200, ct="application/json", chunks=None):
        if chunks is None:chunks=[json.dumps(self.p).encode()]
        return evaluate_fixture(status,ct,chunks,**self.kw)
    def deny(self,code,**kw):
        with self.assertRaisesRegex(TransportRejected,"^"+code+"$"):self.eval(**kw)
    def test_fixed_plan(self):
        r=plan(self.kw["first_day"],self.kw["last_day"])
        p=urlsplit(r.url)
        self.assertEqual((r.method,p.scheme,p.netloc,p.path),("GET","https","api.twelvedata.com","/time_series"))
        self.assertEqual(dict(parse_qsl(p.query)),dict(symbol="EUR/USD",interval="1day",start_date="2026-06-01",end_date="2026-11-27",outputsize="160",apikey=FIXTURE_KEY))
    def test_zero_retry_policy(self):
        a=transport_policy()
        try:
            self.assertTrue(all(getattr(a.max_retries,k)==0 for k in ("total","connect","read","redirect","status","other")))
        finally:a.close()
    def test_success_not_admitted(self):
        r=self.eval()
        self.assertFalse(r.market_admitted)
        self.assertEqual(len(r.bars),130)
    def test_fixed_status(self):
        for status,code in [(301,"REDIRECT_DENIED"),(302,"REDIRECT_DENIED"),(307,"REDIRECT_DENIED"),(401,"AUTH_DENIED"),(403,"AUTH_DENIED"),(429,"RATE_LIMITED"),(503,"HTTP_UNAVAILABLE"),(204,"HTTP_UNAVAILABLE"),(True,"HTTP_INVALID")]:
            with self.subTest(status=status):self.deny(code,status=status,chunks=iter(()))
    def test_redirect_body_unread(self):
        def bad():
            raise AssertionError("body must not be read")
            yield b""
        self.deny("REDIRECT_DENIED",status=302,chunks=bad())
    def test_wrong_content_type(self):
        self.deny("CONTENT_TYPE_DENIED",ct="text/html")
    def test_oversize(self):
        self.deny("BODY_TOO_LARGE",chunks=[b"a"*MAX_BYTES,b"b"])
    def test_chunk_count(self):
        self.deny("BODY_INVALID",chunks=[b""]*1025)
    def test_chunk_type(self):
        self.deny("BODY_INVALID",chunks=["not bytes"])
    def test_stream_exception_sanitized(self):
        def broken():
            yield b"{"
            raise OSError("synthetic key "+FIXTURE_KEY)
        self.deny("BODY_UNAVAILABLE",chunks=broken())
    def test_duplicate_keys(self):
        for raw in (b'{"status":"ok","status":"error"}',b'{"meta":{"symbol":"EUR/USD","symbol":"GBP/USD"}}'):
            with self.subTest(raw=raw):self.deny("JSON_DUPLICATE_KEY",chunks=[raw])
    def test_invalid_json(self):
        for raw in (b"\xff",b"{",b'{"value":NaN}'):
            with self.subTest(raw=raw):self.deny("JSON_INVALID",chunks=[raw])
    def test_bad_scope(self):
        with self.assertRaisesRegex(TransportRejected,"^SCOPE_INVALID$"):plan(self.kw["last_day"],self.kw["first_day"])
if __name__=="__main__":unittest.main()
