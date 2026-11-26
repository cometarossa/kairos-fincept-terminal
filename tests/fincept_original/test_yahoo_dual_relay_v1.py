import os,socket,tempfile,threading,unittest,sys
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts/yahoo_capture_service_v1"))
from public_yahoo_shared_budget_v1 import SharedWindow
from dual_relay import Server
def exchange(s,p):
 s.settimeout(2)
 s.connect(str(p))
 # Admission happens before recv: exhausted relay may close before sendall.
 try:
  s.sendall(b"CONNECT denied.invalid:443 HTTP/1.1\r\n\r\n")
  return s.recv(4096)
 except (BrokenPipeError,ConnectionResetError):
  return b""

class Tests(unittest.TestCase):
 def test_early_close_in_send_and_receive(self):
  for method,error in (("sendall",BrokenPipeError),("sendall",ConnectionResetError),("recv",ConnectionResetError)):
   with self.subTest(method=method,error=error):
    s=Mock()
    getattr(s,method).side_effect=error()
    self.assertEqual(exchange(s,"unused.sock"),b"")
  s=Mock()
  s.connect.side_effect=ConnectionRefusedError()
  with self.assertRaises(ConnectionRefusedError):exchange(s,"unused.sock")
  s=Mock()
  s.recv.side_effect=socket.timeout()
  with self.assertRaises(socket.timeout):exchange(s,"unused.sock")
 def test_actual_two_socket_budget(self):
  clock=[0];budget=SharedWindow(clock=lambda:clock[0]);clock[0]=600
  upstream=Mock(side_effect=AssertionError("NO_UPSTREAM"))
  with tempfile.TemporaryDirectory() as td:
   paths=[Path(td)/x for x in ("h.sock","q.sock")]
   with Server(paths[0],"history",budget,upstream) as a,Server(paths[1],"quote",budget,upstream) as b:
    threads=[threading.Thread(target=x.serve_forever,daemon=True) for x in (a,b)]
    for t in threads:t.start()
    def send(p):
     with socket.socket(socket.AF_UNIX) as s:
      return exchange(s,p)
    try:
     self.assertTrue(all(b"403 Forbidden" in send(paths[1]) for _ in range(2)))
     self.assertEqual(send(paths[1]),b"")
     self.assertTrue(all(b"403 Forbidden" in send(paths[0]) for _ in range(6)))
     self.assertEqual(send(paths[0]),b"")
     clock[0]=1200
     self.assertIn(b"403 Forbidden",send(paths[1]))
     upstream.assert_not_called()
    finally:
     for srv in (a,b):srv.shutdown()
     for t in threads:t.join(2)
if __name__=="__main__":unittest.main()
