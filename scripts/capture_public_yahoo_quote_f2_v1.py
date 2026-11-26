"""Strict public quote snapshot, one opt-in capture, no broker or scheduler.
Provider claimed time is not market-time attestation. Caller must enforce a
separate bounded Yahoo-only network environment and process timeout.
"""
import argparse,base64,fcntl,hashlib,json,math,os,stat,sys,time
from pathlib import Path
from capture_public_cnbc_rss_f2_v1 import private_directory,publish

ACK="PUBLIC_YAHOO_QUOTE_RESEARCH_V1"
SYMBOLS=("SPY","EURUSD=X")
FIELDS={"schema","provider","symbol","price","previous_close","change","change_percent","high","low","volume","provider_claimed_market_time_unix","local_received_at_unix","market_as_of_verified","freshness_verified","research_only","execution_authority","scientific_claim","broker_calls"}
def encode(value):return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode("ascii")
def unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError("duplicate field")
        out[k]=v
    return out
def validate_quote(q,symbol,now):
    if type(symbol) is not str or symbol not in SYMBOLS or type(now) is not int or now<=0:raise ValueError("identity")
    if type(q) is not dict or set(q)!=FIELDS or q["schema"]!="YAHOO_PROVIDER_CLAIMED_QUOTE_V1" or q["provider"]!="Yahoo Finance via original yfinance" or q["symbol"]!=symbol:raise ValueError("quote contract")
    if q["research_only"] is not True or any(q[k] is not False for k in ("market_as_of_verified","freshness_verified","execution_authority","scientific_claim")) or type(q["broker_calls"]) is not int or q["broker_calls"]!=0:raise ValueError("authority")
    t=q["provider_claimed_market_time_unix"];r=q["local_received_at_unix"]
    if type(t) is not int or type(r) is not int or not 0<t<=r<=now or now-t>900 or now-r>60:raise ValueError("stale quote")
    p,prev,hi,lo,vol,change,pct=[q[k] for k in ("price","previous_close","high","low","volume","change","change_percent")]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (p,prev,hi,lo,vol,change,pct)):raise ValueError("invalid number")
    if not 0<lo<=p<=hi or prev<=0 or not 0<=vol<=9007199254740991 or type(vol) is not int:raise ValueError("invalid quote")
    if change!=p-prev or pct!=100*(change/prev):raise ValueError("inconsistent change")
def build_snapshot(q,symbol,now):
    validate_quote(q,symbol,now)
    raw=encode(q)
    if len(raw)>4096:raise ValueError("quote size")
    return {"schema":"YAHOO_QUOTE_SNAPSHOT_V1","provider":"Yahoo Finance via original yfinance","symbol":symbol,"captured_at_unix":now,"quote_sha256":hashlib.sha256(raw).hexdigest(),"quote_base64":base64.b64encode(raw).decode("ascii")}
def decode_snapshot(raw,symbol,now):
    if type(raw) is not bytes or not 0<len(raw)<=8192:raise ValueError("snapshot size")
    s=json.loads(raw,object_pairs_hook=unique)
    if type(s) is not dict or set(s)!={"schema","provider","symbol","captured_at_unix","quote_sha256","quote_base64"} or s["schema"]!="YAHOO_QUOTE_SNAPSHOT_V1" or s["provider"]!="Yahoo Finance via original yfinance" or s["symbol"]!=symbol:raise ValueError("snapshot identity")
    t=s["captured_at_unix"]
    if type(now) is not int or type(t) is not int or not 0<t<=now or now-t>60:raise ValueError("snapshot expired")
    b=base64.b64decode(s["quote_base64"],validate=True)
    if not 0<len(b)<=4096 or hashlib.sha256(b).hexdigest()!=s["quote_sha256"]:raise ValueError("digest")
    q=json.loads(b,object_pairs_hook=unique)
    validate_quote(q,symbol,t)
    validate_quote(q,symbol,now)
    return q
def capture(directory,symbol,*,clock=None,adapter=None):
    if os.environ.get("FINCEPT_PUBLIC_QUOTE_CAPTURE_ACK")!=ACK or os.environ.get("FINCEPT_PUBLIC_YAHOO_QUOTE_ACK")!=ACK or symbol not in SYMBOLS:raise ValueError("opt-in required")
    private_directory(directory)
    directory=directory/symbol
    private_directory(directory)
    fd=os.open(directory/".capture.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or stat.S_IMODE(st.st_mode)!=0o600 or st.st_nlink!=1:raise ValueError("unsafe lock")
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if adapter is None:
            sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"fincept-qt"/"scripts"))
            import yfinance_data as original
            adapter=original.get_quote
        q=adapter(symbol,strict_research=True)
        snap=build_snapshot(q,symbol,int(time.time()) if clock is None else clock())
        publish(directory,snap)
        return snap["quote_sha256"]
    finally:os.close(fd)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inbox",required=True,type=Path)
    p.add_argument("--symbol",required=True,choices=SYMBOLS)
    a=p.parse_args()
    try:
        digest=capture(a.inbox,a.symbol)
    except Exception:
        print("FINCEPT_F2_QUOTE_CAPTURE_UNAVAILABLE");return 1
    print("FINCEPT_F2_QUOTE_CAPTURE_OK","symbol="+a.symbol,"sha256="+digest)
    return 0
if __name__=="__main__":raise SystemExit(main())
