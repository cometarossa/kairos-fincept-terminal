"""Explicit dual-socket public-only relay; one sliding ledger, no broker access."""
import fcntl,ipaddress,os,select,signal,socket,socketserver,stat,threading,time
from pathlib import Path
import connect_handler as proxy
from public_yahoo_shared_budget_v1 import SharedWindow
from public_quote_request_gate_v1 import safe_file

ACK="FINCEPT_YAHOO_DUAL_RELAY_V1"
SCREENER_ACK="FINCEPT_YAHOO_SCREENER_RELAY_CANDIDATE_V1"

def lanes_for(root,*,screener_enabled=False):
    if type(screener_enabled) is not bool:raise ValueError("INVALID_OPT_IN")
    lanes=("history","quote","screener") if screener_enabled else ("history","quote")
    return [(root/(lane+".sock"),lane) for lane in lanes]

def public_connect(address,timeout=7):
    host,port=address
    if host not in proxy.APPROVED or port!=443:raise OSError("destination denied")
    deadline=time.monotonic()+min(timeout,7)
    count=0
    for family,kind,proto,_,addr in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(addr[0]).is_global:continue
        remaining=deadline-time.monotonic()
        if remaining<=0 or count>=3:break
        count+=1
        s=socket.socket(family,kind,proto);s.settimeout(remaining)
        try:s.connect(addr);return s
        except OSError:s.close()
    raise OSError("public provider unavailable")

class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True
    request_queue_size=6
    def __init__(self,path,lane,budget,connect_upstream=public_connect):
        self.lane=lane;self.shared_budget=budget;self.connect_upstream=connect_upstream
        self._admission_lock=threading.Lock()
        super().__init__(str(path),proxy.ConnectHandler)
def main():
    if os.environ.get("FINCEPT_YAHOO_DUAL_RELAY_ACK")!=ACK or os.geteuid()==0 or any(k.startswith(("IG_","BROKER_")) for k in os.environ):return 2
    root=Path("/relay");st=root.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid() or stat.S_IMODE(st.st_mode)!=0o700:return 2
    os.umask(0o077)
    fd=os.open(root/"relay.lock",os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        safe_file(fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        enabled=os.environ.get("FINCEPT_YAHOO_SCREENER_RELAY_ACK")==SCREENER_ACK
        lanes=lanes_for(root,screener_enabled=enabled)
        paths=[path for path,_ in lanes]
        if any(os.path.lexists(p) for p in paths):return 2
        stop=threading.Event()
        for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stop.set())
        budget=SharedWindow(screener_enabled=enabled)
        servers=[]
        try:
            for path,lane in lanes:
                srv=Server(path,lane,budget);servers.append(srv);os.chmod(path,0o600)
            print("FINCEPT_DUAL_RELAY_READY_COOLDOWN_600",flush=True)
            while not stop.is_set():
                ready,_,_=select.select(servers,[],[],.2)
                for srv in ready:srv.handle_request()
        finally:
            for srv,path in zip(servers,paths):
                srv.server_close();path.unlink()
            print("FINCEPT_DUAL_RELAY_STOPPED",flush=True)
    finally:os.close(fd)
    return 0
if __name__=="__main__":raise SystemExit(main())
