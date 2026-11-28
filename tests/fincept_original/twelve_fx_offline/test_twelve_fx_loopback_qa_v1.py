"""QA only: actual requests/TLS on a private loopback socket.

No external network, no real credentials, no production transport.
"""
import hashlib
import importlib.util
import http.server
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qsl

import requests
from test_twelve_fx_research_schema_v1 import TestSchema as SchemaFixture
from twelve_fx_transport_qa_v1 import (
    FIXTURE_KEY, URL, plan, transport_policy, evaluate_fixture,
    TransportRejected, MAX_BYTES,
)

def load_original():
    # The scratch layout deliberately requires the verified colocated source.
    path=Path(__file__).resolve().with_name("twelve_data.py")
    raw=path.read_bytes()
    if hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!="a32b67df0e8e63d5518ce7f1fea1f821b4607d3e":
        raise RuntimeError("ORIGINAL_BLOB_MISMATCH")
    if os.environ.get("TWELVE_DATA_API_KEY")!=FIXTURE_KEY:
        raise RuntimeError("FIXTURE_KEY_REQUIRED")
    spec=importlib.util.spec_from_file_location("twelve_original_fixture",path)
    module=importlib.util.module_from_spec(spec)
    # Execute exactly the bytes already verified; no second path read or pyc.
    exec(compile(raw,str(path),"exec"),module.__dict__)
    if module.API_KEY!=FIXTURE_KEY:
        raise RuntimeError("FIXTURE_KEY_MISMATCH")
    return module

class LocalServer:
    def __init__(self, cert, key, *, status=200, body=b"", headers=None):
        self.calls=[]
        self.status=status
        self.body=body
        self.headers=headers or {"Content-Type":"application/json"}
        state=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                state.calls.append(self.path)
                self.send_response(state.status)
                for k,v in state.headers.items():self.send_header(k,v)
                self.send_header("Content-Length",str(len(state.body)))
                self.end_headers()
                try:self.wfile.write(state.body)
                except (BrokenPipeError,ConnectionResetError,ssl.SSLError):pass
        self.server=http.server.HTTPServer(("127.0.0.1",0),Handler)
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version=ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert,key)
        self.server.socket=ctx.wrap_socket(self.server.socket,server_side=True)
        self.origin=f"https://127.0.0.1:{self.server.server_port}"
        self.worker=threading.Thread(target=self.server.serve_forever,kwargs={"poll_interval":.01},daemon=True)
    def __enter__(self):
        self.worker.start();return self
    def __exit__(self,*args):
        self.server.shutdown();self.server.server_close();self.worker.join(timeout=2)

class TestLoopback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Generate an ephemeral QA-only leaf certificate. No host files/keys.
        cls.original=load_original()
        cls.tmp=tempfile.TemporaryDirectory()
        cls.cert=Path(cls.tmp.name)/"cert.pem"
        key=Path(cls.tmp.name)/"key.pem";cls.key=key
        subprocess.run(["openssl","req","-x509","-newkey","rsa:2048","-nodes",
                        "-days","1","-subj","/CN=127.0.0.1",
                        "-addext","subjectAltName=IP:127.0.0.1",
                        "-keyout",str(key),"-out",str(cls.cert)],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
    @classmethod
    def tearDownClass(cls):
        cls.original.session.close()
        cls.tmp.cleanup()
    def setUp(self):
        fixture=SchemaFixture();fixture.setUp()
        self.payload=fixture.p
        self.kw=dict(first_day=fixture.first,last_day=fixture.last,completed_before=fixture.bound)
        self.body=json.dumps(self.payload).encode()
    def server(self,**kw):
        return LocalServer(self.cert,self.key,**kw)
    def fetch(self,s,*,verify=None,original_route=False):
        prepared=plan(self.kw["first_day"],self.kw["last_day"])
        p=urlsplit(prepared.url)
        if (p.scheme,p.netloc,p.path)!=("https","api.twelvedata.com","/time_series"):
            raise RuntimeError("PLAN_ORIGIN_MISMATCH")
        if original_route:
            # Exercise original Fincept route and parameter construction, never
            # its uncontrolled network session or exception-text propagation.
            class Captured(Exception):pass
            with patch.object(self.original,"_make_request",side_effect=Captured) as call:
                with self.assertRaises(Captured):
                    self.original.get_time_series("EUR/USD","1day",self.kw["first_day"].isoformat(),self.kw["last_day"].isoformat(),160)
                call.assert_called_once()
                route,params=call.call_args.args
                self.assertEqual(route,"time_series")
                self.assertEqual({k:str(v) for k,v in params.items()},dict(parse_qsl(p.query)))
        # Replace origin ONLY with the ephemeral local test server, never
        # accept an arbitrary host. This is not a production egress policy.
        if urlsplit(s.origin).hostname!="127.0.0.1":
            raise RuntimeError("NON_LOOPBACK_DENIED")
        target=s.origin+p.path+"?"+p.query
        # HTTPAdapter.send does not invoke Session.resolve_redirects or
        # Response.next preparation. Never hand a redirect body to the parser.
        adapter=transport_policy()
        try:
            request=requests.Request("GET",target,headers={"Accept":"application/json","Accept-Encoding":"identity"}).prepare()
            try:
                with adapter.send(request,timeout=(1,1),stream=True,
                                  verify=str(self.cert) if verify is None else verify,
                                  proxies={}) as response:
                    if response.status_code!=200:
                        return evaluate_fixture(response.status_code,None,(),**self.kw)
                    if response.headers.get("Content-Encoding","identity").lower()!="identity":
                        raise TransportRejected("ENCODING_DENIED")
                    return evaluate_fixture(response.status_code,response.headers.get("Content-Type"),
                                            response.iter_content(chunk_size=4096),**self.kw)
            except requests.exceptions.RequestException:
                raise TransportRejected("TLS_OR_TRANSPORT_UNAVAILABLE") from None
        finally:
            adapter.close()
    def test_original_request_real_tls_fixture(self):
        with self.server(body=self.body) as s:
            result=self.fetch(s,original_route=True)
            self.assertEqual(len(result.bars),130)
            self.assertFalse(result.market_admitted)
            self.assertEqual(len(s.calls),1)
            p=urlsplit(s.calls[0]);self.assertEqual(p.path,"/time_series")
            self.assertEqual(dict(parse_qsl(p.query))["symbol"],"EUR/USD")
    def test_untrusted_certificate_denied(self):
        with self.server(body=self.body) as s:
            with self.assertRaisesRegex(TransportRejected,"^TLS_OR_TRANSPORT_UNAVAILABLE$"):
                self.fetch(s,verify=True)
            self.assertEqual(s.calls,[])
    def test_redirect_not_followed(self):
        with self.server(status=302,headers={"Location":"/unexpected","Content-Type":"application/json"}) as s:
            with self.assertRaisesRegex(TransportRejected,"^REDIRECT_DENIED$"):self.fetch(s)
            self.assertEqual(len(s.calls),1)
    def test_redirect_nonempty_body_not_read(self):
        with self.server(status=302,body=b"x"*(MAX_BYTES+1),
                         headers={"Location":"/unexpected","Content-Type":"application/json"}) as s:
            # Spy on both the eager content access path and streaming path.
            with patch.object(requests.Response,"iter_content",side_effect=AssertionError("redirect body read")):
                with self.assertRaisesRegex(TransportRejected,"^REDIRECT_DENIED$"):self.fetch(s)
            self.assertEqual(len(s.calls),1)
    def test_original_provenance_and_fake_key_unconditional(self):
        with patch.dict(os.environ,{"TWELVE_DATA_API_KEY":"WRONG_FIXTURE"}):
            with self.assertRaisesRegex(RuntimeError,"^FIXTURE_KEY_REQUIRED$"):load_original()
        with patch.object(Path,"read_bytes",return_value=b"untrusted fixture"):
            with self.assertRaisesRegex(RuntimeError,"^ORIGINAL_BLOB_MISMATCH$"):load_original()
    def test_no_retry_429_or_503(self):
        for status,reason in ((429,"RATE_LIMITED"),(503,"HTTP_UNAVAILABLE")):
            with self.subTest(status=status),self.server(status=status,headers={"Retry-After":"0","Content-Type":"application/json"}) as s:
                with self.assertRaisesRegex(TransportRejected,"^"+reason+"$"):self.fetch(s)
                self.assertEqual(len(s.calls),1)
    def test_oversize_stream(self):
        with self.server(body=b"x"*(MAX_BYTES+1)) as s:
            with self.assertRaisesRegex(TransportRejected,"^BODY_TOO_LARGE$"):self.fetch(s)
            self.assertEqual(len(s.calls),1)
    def test_compressed_response_denied(self):
        with self.server(body=b"fake gzip",headers={"Content-Type":"application/json","Content-Encoding":"gzip"}) as s:
            with self.assertRaisesRegex(TransportRejected,"^ENCODING_DENIED$"):self.fetch(s)
            self.assertEqual(len(s.calls),1)

if __name__=="__main__":unittest.main()
