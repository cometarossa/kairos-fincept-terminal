"""Offline candidate: serialized one-shot quote claim; no network or child by default.
Caller must separately admit the capture worker, shared relay, and all mounts.
"""
import fcntl,json,os,re,stat,tempfile,time
from pathlib import Path

SCOPE="FINCEPT_PUBLIC_QUOTE_ON_DEMAND_V1"
SYMBOLS=("SPY","EURUSD=X")
WINDOW=600
class Denied(ValueError):pass
def unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise Denied("DUPLICATE_FIELD")
        out[k]=v
    return out
def request(raw,now):
    if type(raw) is not bytes or not 0<len(raw)<=512:raise Denied("INVALID_REQUEST")
    try:r=json.loads(raw,object_pairs_hook=unique)
    except (ValueError,UnicodeError,RecursionError):raise Denied("INVALID_REQUEST") from None
    if type(r) is not dict or set(r)!={"scope","symbol","request_id","issued_at_unix"} or r["scope"]!=SCOPE or type(r["symbol"]) is not str or r["symbol"] not in SYMBOLS or type(r["request_id"]) is not str or not re.fullmatch("[0-9a-f]{32}",r["request_id"]) or type(r["issued_at_unix"]) is not int or not 0<=now-r["issued_at_unix"]<=30 or r["issued_at_unix"]<=0:raise Denied("INVALID_REQUEST")
    return r
def safe_file(fd):
    s=os.fstat(fd)
    if not stat.S_ISREG(s.st_mode) or stat.S_IMODE(s.st_mode)!=0o600 or s.st_uid!=os.geteuid() or s.st_nlink!=1:raise Denied("UNSAFE_STATE")
def load_state(root):
    fd=os.open(root/"last.json",os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(fd,"rb") as f:
        safe_file(f.fileno());b=f.read(513)
    if len(b)>512:raise Denied("UNSAFE_STATE")
    s=json.loads(b,object_pairs_hook=unique)
    if type(s) is not dict or set(s)!={"last_claim_unix"} or type(s["last_claim_unix"]) is not int or s["last_claim_unix"]<=0:raise Denied("UNSAFE_STATE")
    return s["last_claim_unix"]
def claim(root,now):
    fd,name=tempfile.mkstemp(prefix=".claim-",dir=root)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(json.dumps({"last_claim_unix":now},separators=(",",":")).encode());f.flush();os.fsync(f.fileno())
        os.replace(name,root/"last.json")
        d=os.open(root,os.O_DIRECTORY|os.O_RDONLY|os.O_NOFOLLOW)
        try:os.fsync(d)
        finally:os.close(d)
    finally:
        if os.path.exists(name):os.unlink(name)
SCREENER_SCOPE="FINCEPT_PUBLIC_SCREENER_ON_DEMAND_V1"

def screener_request(raw,now):
    if type(raw) is not bytes or not 0<len(raw)<=512:raise Denied("INVALID_REQUEST")
    try:r=json.loads(raw,object_pairs_hook=unique)
    except (ValueError,UnicodeError,RecursionError):raise Denied("INVALID_REQUEST") from None
    if (type(r) is not dict or set(r)!={"scope","screen_id","request_id","issued_at_unix"}
            or r["scope"]!=SCREENER_SCOPE or r["screen_id"]!="day_gainers"
            or type(r["request_id"]) is not str or not re.fullmatch("[0-9a-f]{32}",r["request_id"])
            or type(r["issued_at_unix"]) is not int or not 0<=now-r["issued_at_unix"]<=30
            or r["issued_at_unix"]<=0):raise Denied("INVALID_REQUEST")
    return r

def dispatch(raw,root,*,scope=None,worker=None,clock=time.time):
    if scope!=SCOPE or not callable(worker):return "DISABLED"
    return _dispatch(raw,root,worker=worker,clock=clock,validate=request,field="symbol")

def dispatch_screener(raw,root,*,scope=None,worker=None,clock=time.time):
    if type(scope) is not str or scope!=SCREENER_SCOPE or not callable(worker):return "DISABLED"
    return _dispatch(raw,root,worker=worker,clock=clock,validate=screener_request,field="screen_id")

def _dispatch(raw,root,*,worker,clock,validate,field):
    fd=None
    try:
        now=int(clock())
        if now<=0:raise Denied("CLOCK_INVALID")
        r=validate(raw,now)
        root=Path(root);s=root.lstat()
        if not stat.S_ISDIR(s.st_mode) or stat.S_IMODE(s.st_mode)!=0o700 or s.st_uid!=os.geteuid():raise Denied("UNSAFE_STATE")
        # This lock must also be held by the history child supervisor.
        # Existing production does NOT yet use it.
        fd=os.open(root/"worker.lock",os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        safe_file(fd)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return "BUSY"
        now=int(clock());r=validate(raw,now)
        last=load_state(root)
        if now-last<WINDOW:return "COOLDOWN"
        # Commit the attempt durably BEFORE calling worker. No refund/retry.
        claim(root,now)
        try:
            result=worker(r[field])
            return "CAPTURE_OK" if type(result) is int and result==0 else "CAPTURE_UNAVAILABLE"
        except Exception:return "CAPTURE_UNAVAILABLE"
    except (OSError,ValueError,TypeError,OverflowError,RecursionError):return "DENIED"
    finally:
        if fd is not None:os.close(fd)
