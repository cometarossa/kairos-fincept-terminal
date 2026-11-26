"""Pinned yfinance raw quote path; isolated one-shot research only.

Three HTTP session request attempts maximum, exact ordered paths, no redirects,
no consent fallback or persistent cookie cache. Not an egress sandbox: caller
must separately confine networking and impose a hard process deadline.
"""
import json
import importlib.metadata
from urllib.parse import urlsplit

ACK = "PUBLIC_YAHOO_QUOTE_RESEARCH_V1"
URLS = ("https://fc.yahoo.com", "https://query1.finance.yahoo.com/v1/test/getcrumb",
        "https://query1.finance.yahoo.com/v7/finance/quote")
MAX_RESPONSE = 262144
class QuoteDenied(ValueError):
    pass

def unique(pairs):
    result = {}
    for k,v in pairs:
        if k in result: raise QuoteDenied("duplicate field")
        result[k]=v
    return result

def raw_record(raw, symbol):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_RESPONSE:
        raise QuoteDenied("response size")
    obj=json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(QuoteDenied("nonfinite")))
    if type(obj) is not dict or set(obj)!={"quoteResponse"}:
        raise QuoteDenied("response shape")
    q=obj["quoteResponse"]
    if type(q) is not dict or set(q)!={"result","error"} or q["error"] is not None:
        raise QuoteDenied("provider error")
    rows=q["result"]
    if type(rows) is not list or len(rows)!=1 or type(rows[0]) is not dict or rows[0].get("symbol")!=symbol:
        raise QuoteDenied("provider identity")
    return rows[0]

def fetch_raw_quote(symbol):
    import os
    if symbol not in ("SPY","EURUSD=X") or os.environ.get("FINCEPT_PUBLIC_YAHOO_QUOTE_ACK")!=ACK:
        raise QuoteDenied("opt-in")
    if importlib.metadata.version("yfinance")!="0.2.66":
        raise QuoteDenied("unreviewed yfinance version")
    from curl_cffi.requests import Session
    from yfinance.data import YfData

    class BoundedSession(Session):
        attempts=0
        blocked=False
        def request(self, method, url, **kwargs):
            if self.blocked or self.attempts>=len(URLS):
                raise QuoteDenied("request budget")
            expected=URLS[self.attempts]
            self.attempts+=1
            # yfinance may append '?' to a URL; only exact reviewed endpoints.
            if method.upper()!="GET" or url.rstrip("?")!=expected:
                self.blocked=True
                raise QuoteDenied("endpoint denied")
            if any(k in kwargs for k in ("data","json","files","auth","proxy_auth")):
                self.blocked=True
                raise QuoteDenied("request shape")
            kwargs.update(timeout=8,allow_redirects=False,max_redirects=0)
            try:
                response=super().request(method,url,**kwargs)
                final=urlsplit(response.url)
                wanted=urlsplit(expected)
                if (final.scheme!=wanted.scheme or final.netloc!=wanted.netloc
                        or (final.path or "/")!=(wanted.path or "/")
                        or response.status_code not in ((200,404) if expected==URLS[0] else (200,))
                        or len(response.content)>MAX_RESPONSE):
                    raise QuoteDenied("response denied")
                return response
            except Exception:
                self.blocked=True
                raise

    class EphemeralYfData(YfData):
        def _load_cookie_curlCffi(self): return False
        def _save_cookie_curlCffi(self): return True
        def _get_cookie_basic(self, timeout=30):
            if getattr(self,"_research_cookie_ready",False): return True
            self._research_cookie_ready=super()._get_cookie_basic(timeout=timeout)
            return self._research_cookie_ready
        def _get_cookie_csrf(self, timeout):
            raise QuoteDenied("alternate cookie path denied")

    # Bypass the dependency singleton for this dedicated operation; never
    # replace a live Fincept session or reuse a persistent cookie.
    with BoundedSession(impersonate="chrome") as session:
        data=type.__call__(EphemeralYfData,session=session)
        response=data.get(URLS[2],params={"symbols":symbol,"formatted":"false"},timeout=8)
        if session.blocked or session.attempts!=3:
            raise QuoteDenied("incomplete request path")
        return raw_record(response.content,symbol)
