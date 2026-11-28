"""QA-only worker reusing the verified local TLS harness.

Returns fixed exit codes; no output, provider access, persistence of bars,
or production import. This intentionally uses synthetic test fixtures.
"""
import json
from test_twelve_fx_loopback_qa_v1 import TestLoopback as Harness
from twelve_fx_transport_qa_v1 import TransportRejected
from twelve_fx_research_schema_v1 import Rejected

def run_fixture(mode):
    if mode not in ("tls_success","tls_rate_limit","tls_invalid"):
        return 2
    Harness.setUpClass()
    try:
        h=Harness()
        h.setUp()
        if mode=="tls_invalid":
            h.payload["values"][40]["high"]="1.10"
        body=json.dumps(h.payload).encode()
        with h.server(status=429 if mode=="tls_rate_limit" else 200,body=body) as server:
            try:
                result=h.fetch(server,original_route=True)
            except TransportRejected as exc:
                if mode=="tls_rate_limit" and str(exc)=="RATE_LIMITED" and len(server.calls)==1:
                    return 20
                return 22
            except Rejected as exc:
                if mode=="tls_invalid" and str(exc)=="OHLC_ORDER" and len(server.calls)==1:
                    return 21
                return 22
            if (mode=="tls_success" and len(server.calls)==1
                    and len(result.bars)==130 and result.market_admitted is False
                    and result.status=="OFFLINE_SHAPE_ONLY"):
                return 0
            return 22
    finally:
        Harness.tearDownClass()
