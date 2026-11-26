import os,sys,pathlib,tempfile,unittest,socket,threading,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/"scripts/yahoo_capture_service_v1"))
from capture_service import child_env,serve_request,Supervisor,SCREENER_SCOPE,SCOPE
class Tests(unittest.TestCase):
    def test_isolated_env(self):
        e=child_env(10003,"screener")
        self.assertEqual(e["FINCEPT_PUBLIC_SCREENER_CAPTURE_ACK"],"FINCEPT_SCREENER_CAPTURE_CANDIDATE_V1")
        self.assertEqual(e["HTTPS_PROXY"],"http://127.0.0.1:10003")
        self.assertFalse(any(k.startswith(("IG_","BROKER_","FINCEPT_PUBLIC_QUOTE","FINCEPT_PUBLIC_HISTORY")) for k in e))
        self.assertNotIn("FINCEPT_PUBLIC_SCREENER_CAPTURE_ACK",child_env(10001,"history"))
        self.assertNotIn("FINCEPT_PUBLIC_SCREENER_CAPTURE_ACK",child_env(10002,"quote"))
    def test_socket_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            for name,data in (("worker.lock",""),("last.json",'{"last_claim_unix":1000}')):
                p=root/name;p.write_text(data);p.chmod(0o600)
            calls=[]
            s=Supervisor(root,history_worker=lambda x:1,quote_worker=lambda x:calls.append(("quote",x)) or 0,screener_worker=lambda x:calls.append(("screen",x)) or 0,mono=lambda:0,wall=lambda:2000)
            r=dict(scope=SCREENER_SCOPE,screen_id="day_gainers",request_id="a"*32,issued_at_unix=2000)
            def send(payload,enabled=False):
                a,b=socket.socketpair()
                with a,b:
                    t=threading.Thread(target=serve_request,args=(a,s),kwargs={"enabled":True,"screener_enabled":enabled});t.start()
                    b.sendall(json.dumps(payload).encode());b.shutdown(socket.SHUT_WR);b.settimeout(2)
                    result=b.recv(128);t.join(2)
                    return result
            self.assertEqual(send(r),b"DISABLED\n")
            self.assertEqual(send(dict(r,force=True),True),b"DENIED\n")
            self.assertEqual(send(r,True),b"CAPTURE_OK\n")
            self.assertEqual(send(r,True),b"COOLDOWN\n")
            quote=dict(scope=SCOPE,symbol="SPY",request_id="b"*32,issued_at_unix=2000)
            self.assertEqual(send(quote,True),b"COOLDOWN\n")
            self.assertEqual(calls,[("screen","day_gainers")])
