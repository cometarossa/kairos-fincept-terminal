import os,socket,tempfile,threading,unittest,sys
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts/yahoo_capture_service_v1"))
from public_yahoo_shared_budget_v1 import SharedWindow
from dual_relay import Server,lanes_for
class Tests(unittest.TestCase):
    def test_exact_default_lanes(self):
        self.assertEqual(lanes_for(Path("/tmp")),[(Path("/tmp/history.sock"),"history"),(Path("/tmp/quote.sock"),"quote")])
    def test_actual_three_sockets_one_budget(self):
        clock=[0];budget=SharedWindow(clock=lambda:clock[0],screener_enabled=True);clock[0]=600
        upstream=Mock(side_effect=AssertionError("NO_UPSTREAM"))
        with tempfile.TemporaryDirectory() as td:
            paths=lanes_for(Path(td),screener_enabled=True)
            servers=[Server(p,lane,budget,upstream) for p,lane in paths]
            threads=[threading.Thread(target=x.serve_forever,daemon=True) for x in servers]
            for t in threads:t.start()
            def send(lane):
                path=dict((l,p) for p,l in paths)[lane]
                with socket.socket(socket.AF_UNIX) as s:
                    s.settimeout(2);s.connect(str(path));s.sendall(b"CONNECT denied.invalid:443 HTTP/1.1\r\n\r\n")
                    try:return s.recv(4096)
                    except (ConnectionResetError,BrokenPipeError):return b""
            try:
                self.assertTrue(all(b"403 Forbidden" in send("screener") for _ in range(2)))
                self.assertEqual(send("screener"),b"")
                self.assertTrue(all(b"403 Forbidden" in send("history") for _ in range(4)))
                self.assertEqual(send("history"),b"")
                self.assertTrue(all(b"403 Forbidden" in send("quote") for _ in range(2)))
                self.assertEqual(send("quote"),b"")
                clock[0]=1200
                self.assertIn(b"403 Forbidden",send("history"))
                upstream.assert_not_called()
            finally:
                for srv in servers:srv.shutdown();srv.server_close()
                for t in threads:t.join(2)
if __name__=="__main__":unittest.main()
