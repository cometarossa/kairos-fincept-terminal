import json,os,socket,tempfile,threading,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts/yahoo_capture_service_v1"))
from capture_service import child_env,serve_request,Supervisor,SCOPE
class Tests(unittest.TestCase):
 def test_separate_envs(self):
  h=child_env(10001,"history");q=child_env(10002,"quote")
  self.assertNotIn("FINCEPT_PUBLIC_QUOTE_CAPTURE_ACK",h)
  self.assertNotIn("FINCEPT_PUBLIC_HISTORY_CAPTURE_ACK",q)
  self.assertEqual(h["HTTPS_PROXY"],"http://127.0.0.1:10001")
  self.assertEqual(q["HTTPS_PROXY"],"http://127.0.0.1:10002")
  self.assertFalse(any(k.startswith(("IG_","BROKER_")) for k in h|q))
 def test_real_socket_request_claim(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   for n,v in [("last.json",'{"last_claim_unix":1400}'),("worker.lock","")]:
    p=root/n;p.write_text(v);p.chmod(0o600)
   calls=[]
   s=Supervisor(root,history_worker=lambda x:1,quote_worker=lambda x:calls.append(x) or 0,mono=lambda:0,wall=lambda:2000)
   raw=json.dumps(dict(scope=SCOPE,symbol="SPY",request_id="a"*32,issued_at_unix=2000)).encode()
   def send(payload,enabled):
    a,b=socket.socketpair()
    with a,b:
     t=threading.Thread(target=serve_request,args=(a,s),kwargs={"enabled":enabled});t.start()
     b.sendall(payload);b.shutdown(socket.SHUT_WR);b.settimeout(2)
     result=b.recv(128);t.join(2)
     return result
   self.assertEqual(send(raw,False),b"DISABLED\n")
   self.assertEqual(send(raw,True),b"CAPTURE_OK\n")
   self.assertEqual(send(raw,True),b"COOLDOWN\n")
   self.assertEqual(calls,["SPY"])
   self.assertEqual(send(b"x"*513,True),b"DENIED\n")
if __name__=="__main__":unittest.main()
