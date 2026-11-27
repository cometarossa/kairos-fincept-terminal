"""Opt-in Linux supervisor; one history/quote child at a time, no direct egress.
Host admission must supply fixed private mounts and a separately reviewed relay.
"""
import errno,fcntl,json,os,select,signal,socket,socketserver,stat,sys,threading,time
from pathlib import Path
from contextlib import ExitStack
from capture_supervisor_candidate import Supervisor,run_child,SCOPE,SCREENER_SCOPE
from public_quote_request_gate_v1 import safe_file,unique

ACK="FINCEPT_YAHOO_CAPTURE_SERVICE_V1"
LONG_ACK="FINCEPT_YAHOO_LONG_HISTORY_REPLACEMENT_V1"
# Keep exact numeric protocol in sync with the producer; no raw child output.
HISTORY_EXIT_REASONS = {
    20: "ADAPTER_UNAVAILABLE",
    21: "EMPTY_HISTORY",
    22: "INSUFFICIENT_SPAN",
    23: "INTERNAL_FAILURE",
    24: "INVALID_BAR",
    25: "INVALID_COUNT",
    26: "INVALID_NUMBER",
    27: "INVALID_OHLC",
    28: "INVALID_TIMESTAMP",
    29: "INVALID_VOLUME",
    30: "LOCK_UNAVAILABLE",
    31: "OPT_IN_REQUIRED",
    32: "OVERSIZED_BARS",
    33: "PUBLICATION_REJECTED",
    34: "RAW_INVALID_BAR",
    35: "RAW_INVALID_BAR_BOOLEAN_CLOSE",
    36: "RAW_INVALID_BAR_BOOLEAN_HIGH",
    37: "RAW_INVALID_BAR_BOOLEAN_LOW",
    38: "RAW_INVALID_BAR_BOOLEAN_OPEN",
    39: "RAW_INVALID_BAR_BOOLEAN_VOLUME",
    40: "RAW_INVALID_BAR_CELL_CONVERSION",
    41: "RAW_INVALID_BAR_MISSING_CLOSE",
    42: "RAW_INVALID_BAR_MISSING_HIGH",
    43: "RAW_INVALID_BAR_MISSING_LOW",
    44: "RAW_INVALID_BAR_MISSING_OPEN",
    45: "RAW_INVALID_BAR_MISSING_OR_BOOLEAN",
    46: "RAW_INVALID_BAR_MISSING_VOLUME",
    47: "RAW_INVALID_BAR_NONFINITE",
    48: "RAW_INVALID_BAR_NONPOSITIVE_PRICE",
    49: "RAW_INVALID_BAR_OHLC_ORDER",
    50: "RAW_INVALID_BAR_VOLUME_FRACTIONAL",
    51: "RAW_INVALID_BAR_VOLUME_RANGE",
    52: "STALE_HISTORY",
    53: "SYMBOL_DENIED",
    54: "UNSAFE_DIRECTORY",
    55: "WINDOW_DENIED",
    56: "RAW_INVALID_BAR_PRE_ADJUSTMENT_OHLC_ORDER",
    57: "RAW_INVALID_BAR_ADJUSTMENT_STAGE_OHLC_ORDER"
}

def history_diagnostic(symbol, period, code):
    if symbol not in ("SPY","EURUSD=X") or period not in ("5d","6mo") or type(code) is not int or code == 0:
        return None
    reason=HISTORY_EXIT_REASONS.get(code,"CHILD_UNAVAILABLE_UNCLASSIFIED")
    if code in (56,57) and (symbol,period)!=("EURUSD=X","6mo"):
        reason="CHILD_UNAVAILABLE_UNCLASSIFIED"
    return "HISTORY_CAPTURE_DIAGNOSTIC symbol="+symbol+" period="+period+" reason="+reason

ROOT=Path("/capture")
CONTROL=Path("/control")
REQUEST=Path("/request")
HISTORY=Path("/inbox")
QUOTES=Path("/quote-inbox")
SCREENS=Path("/screener-inbox")
RELAY=Path("/relay")

def private_dir(path):
    s=path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid() or stat.S_IMODE(s.st_mode)!=0o700:
        raise ValueError("UNSAFE_DIRECTORY")

def child_env(port,lane,*,period="5d"):
    if period not in ("5d","6mo") or (period=="6mo" and lane!="history"):raise ValueError("WINDOW_DENIED")
    url="http://127.0.0.1:"+str(port)
    env={"PATH":"/usr/local/bin:/usr/bin:/bin","HOME":"/tmp","XDG_CACHE_HOME":"/tmp","PYTHONDONTWRITEBYTECODE":"1",
         "HTTP_PROXY":url,"HTTPS_PROXY":url,"ALL_PROXY":url,"http_proxy":url,"https_proxy":url,"all_proxy":url,"NO_PROXY":"","no_proxy":""}
    if lane=="history":
        env["FINCEPT_HISTORY_REASON_EXIT_ACK"]="FINCEPT_HISTORY_REASON_EXIT_V1"
        if period == "6mo":
            env["FINCEPT_FX_ADJUSTMENT_DIAGNOSTIC_ACK"]="FINCEPT_FX_ADJUSTMENT_ORIGIN_V1"
        env["FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK"]="DUAL_WINDOW_YAHOO_HISTORY_SNAPSHOT_V1" if period=="6mo" else "MULTI_YAHOO_HISTORY_SNAPSHOT_V1"
    elif lane=="quote":
        env["FINCEPT_PUBLIC_QUOTE_CAPTURE_ACK"]="PUBLIC_YAHOO_QUOTE_RESEARCH_V1"
        env["FINCEPT_PUBLIC_YAHOO_QUOTE_ACK"]="PUBLIC_YAHOO_QUOTE_RESEARCH_V1"
    elif lane=="screener":
        env["FINCEPT_PUBLIC_SCREENER_CAPTURE_ACK"]="FINCEPT_SCREENER_CAPTURE_CANDIDATE_V1"
    else:raise ValueError("LANE_DENIED")
    return env

class Relay(socketserver.BaseRequestHandler):
    def handle(self):
        with socket.socket(socket.AF_UNIX) as peer:
            try:
                peer.settimeout(5);peer.connect(str(self.server.relay_path))
                self.request.settimeout(5)
                end=time.monotonic()+45
                totals={self.request:0,peer:0}
                while time.monotonic()<end:
                    ready,_,_=select.select([self.request,peer],[],[],1)
                    for a in ready:
                        b=a.recv(65536)
                        if not b:return
                        totals[a]+=len(b)
                        if totals[a]>3010000:return
                        (peer if a is self.request else self.request).sendall(b)
            except OSError:return

class LocalRelay(socketserver.ThreadingMixIn,socketserver.TCPServer):
    daemon_threads=True
    request_queue_size=6
    def __init__(self,path):
        self.relay_path=path
        super().__init__(("127.0.0.1",0),Relay)

def serve_request(conn,supervisor,*,enabled,screener_enabled=False):
    deadline=time.monotonic()+1
    try:
        chunks=bytearray()
        while len(chunks)<=512:
            remaining=deadline-time.monotonic()
            if remaining<=0:return
            conn.settimeout(remaining)
            part=conn.recv(513-len(chunks))
            if not part:break
            chunks.extend(part)
        raw=bytes(chunks)
        try:
            request=json.loads(raw,object_pairs_hook=unique) if len(raw)<=512 else None
        except (ValueError,UnicodeError,RecursionError):request=None
        if type(request) is dict and request.get("scope")==SCREENER_SCOPE:
            result=supervisor.screener(raw,scope=SCREENER_SCOPE if screener_enabled else None)
        else:
            result=supervisor.quote(raw,scope=SCOPE if enabled else None)
        conn.sendall((result+"\n").encode("ascii"))
    except (OSError,ValueError):return

def main():
    if os.environ.get("FINCEPT_YAHOO_CAPTURE_SERVICE_ACK")!=ACK:return 2
    if os.geteuid()==0 or set(os.listdir("/sys/class/net"))!={"lo"} or any(k.startswith(("IG_","BROKER_")) for k in os.environ):return 2
    with socket.socket() as s:
        s.settimeout(1)
        try:s.connect(("192.0.2.1",443))
        except OSError as e:
            if e.errno not in (errno.ENETUNREACH,errno.EHOSTUNREACH,errno.EPERM,errno.EACCES):return 2
        else:return 2
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stop.set())
    os.umask(0o077)
    private_dir(CONTROL);private_dir(REQUEST);private_dir(HISTORY);private_dir(QUOTES)
    for sym in ("SPY","EURUSD=X"):private_dir(QUOTES/sym)
    screener_enabled=os.environ.get("FINCEPT_YAHOO_SCREENER_REQUEST_ACK")==SCREENER_SCOPE
    if screener_enabled:
        private_dir(SCREENS)
        st=(RELAY/"screener.sock").lstat()
        if not stat.S_ISSOCK(st.st_mode) or st.st_uid!=os.geteuid() or stat.S_IMODE(st.st_mode)!=0o600:return 2
    fd=os.open(CONTROL/"supervisor.lock",os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        safe_file(fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        path=REQUEST/"request.sock"
        if os.path.lexists(path):return 2
        with ExitStack() as stack:
            history=stack.enter_context(LocalRelay(RELAY/"history.sock"))
            quote=stack.enter_context(LocalRelay(RELAY/"quote.sock"))
            screener=stack.enter_context(LocalRelay(RELAY/"screener.sock")) if screener_enabled else None
            listener=stack.enter_context(socket.socket(socket.AF_UNIX,socket.SOCK_STREAM))
            relays=(history,quote) if screener is None else (history,quote,screener)
            listener.bind(str(path));os.chmod(path,0o600);listener.listen(2);listener.settimeout(.2)
            threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in relays]
            for t in threads:t.start()
            def worker(lane,symbol,period="5d"):
                server=history if lane=="history" else quote
                script="capture_public_yahoo_"+lane+"_f2_v1.py"
                inbox=HISTORY if lane=="history" else QUOTES
                argv=[sys.executable,str(ROOT/"scripts"/script),"--inbox",str(inbox),"--symbol",symbol]
                if lane=="history":argv+=["--period",period]
                code=run_child(argv,child_env(server.server_address[1],lane,period=period),stop=stop)
                if lane=="history":
                    message=history_diagnostic(symbol,period,code)
                    if message is not None:print(message,flush=True)
                return code
            def screen_worker(screen_id):
                if screen_id!="day_gainers" or screener is None:return 1
                argv=[sys.executable,str(ROOT/"scripts"/"capture_public_yahoo_screener_f2_v1.py")]
                return run_child(argv,child_env(screener.server_address[1],"screener"),stop=stop)
            long_enabled=os.environ.get("FINCEPT_YAHOO_LONG_HISTORY_ACK")==LONG_ACK
            supervisor=Supervisor(CONTROL,history_worker=lambda s:worker("history",s),quote_worker=lambda s:worker("quote",s),long_history_worker=(lambda s:worker("history",s,"6mo")) if long_enabled else None,screener_worker=screen_worker if screener_enabled else None)
            enabled=os.environ.get("FINCEPT_YAHOO_QUOTE_REQUEST_ACK")==SCOPE
            print("FINCEPT_CAPTURE_SUPERVISOR_READY",flush=True)
            try:
                while not stop.is_set():
                    status=supervisor.history_tick()
                    if status!="NOT_DUE":print(status,flush=True)
                    try:conn,_=listener.accept()
                    except socket.timeout:continue
                    with conn:
                        if not stop.is_set():serve_request(conn,supervisor,enabled=enabled,screener_enabled=screener_enabled)
            finally:
                for s in relays:s.shutdown()
                path.unlink()
                print("FINCEPT_CAPTURE_SUPERVISOR_STOPPED",flush=True)
    finally:os.close(fd)
    return 0
if __name__=="__main__":raise SystemExit(main())
