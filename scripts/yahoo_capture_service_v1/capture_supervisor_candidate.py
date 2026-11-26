"""Candidate single-child supervisor for fixed research-only captures.
Offline lab; no listener, scheduling daemon, or production admission here.
"""
import fcntl,os,signal,subprocess,time,stat
from pathlib import Path
from public_quote_request_gate_v1 import dispatch,SCOPE,safe_file

SYMBOLS=("SPY","EURUSD=X")
MAX_SECONDS=45
HISTORY_GUARD=55
class Supervisor:
    def __init__(self,root,*,history_worker,quote_worker,mono=time.monotonic,wall=time.time):
        self.root=Path(root)
        self.history_worker=history_worker
        self.quote_worker=quote_worker
        self.mono=mono
        self.wall=wall
        self.next_history=mono()+300
        self.index=0
    def history_tick(self):
        start=self.mono()
        if start<self.next_history:return "NOT_DUE"
        # A missed slot is never caught up with repeated requests.
        self.next_history=start+300
        symbol=SYMBOLS[self.index%2]
        self.index+=1
        fd=None
        try:
            fd=os.open(self.root/"worker.lock",os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            safe_file(fd)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return "HISTORY_BUSY_SKIPPED"
            result=self.history_worker(symbol)
            return "HISTORY_OK" if type(result) is int and result==0 else "HISTORY_UNAVAILABLE"
        except Exception:return "HISTORY_UNAVAILABLE"
        finally:
            if fd is not None:os.close(fd)
    def quote(self,raw,*,scope=None):
        if scope!=SCOPE:return "DISABLED"
        if self.next_history-self.mono()<=HISTORY_GUARD:return "HISTORY_PRIORITY"
        def worker(symbol):
            # Recheck after acquiring the common lock and claiming cooldown.
            # Denial here consumes the claimed attempt, never launches later.
            if self.next_history-self.mono()<=HISTORY_GUARD:return 1
            return self.quote_worker(symbol)
        return dispatch(raw,self.root,scope=scope,worker=worker,clock=self.wall)

def run_child(argv,env,*,stop,timeout=MAX_SECONDS):
    """Bound and reap the sole child group. Caller supplies fixed trusted argv/env."""
    if stop.is_set():return 1
    child=subprocess.Popen(argv,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    deadline=time.monotonic()+timeout
    try:
        while not stop.is_set() and time.monotonic()<deadline:
            info=os.waitid(os.P_PID,child.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT)
            if info is not None:
                return info.si_status if info.si_code==os.CLD_EXITED else 1
            stop.wait(min(.05,max(0,deadline-time.monotonic())))
        return 1
    finally:
        # Linux waitid(WNOWAIT) keeps the leader PID reserved until reaping.
        # No signal is sent to a process-group ID after reaping the leader.
        try:
            os.killpg(child.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        time.sleep(.1)
        try:
            os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait()
