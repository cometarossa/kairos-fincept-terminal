import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for p in (ROOT/"scripts/yahoo_capture_service_v1", ROOT/"scripts", ROOT/"fincept-qt/scripts"):
    sys.path.insert(0,str(p))
import os, tempfile, pathlib, unittest, fcntl
from unittest.mock import patch
from screener_inbox_publish_candidate import publish, decode
from public_yahoo_shared_budget_v1 import SharedWindow

NOW=1795730000
def sample(cap=NOW-10):
    return {"source":"Yahoo Finance screener","kind":"predefined","screen_id":"day_gainers","offset":0,"warnings":[],"count":1,"total":2,"fetched_at":cap,"rows":[{"symbol":"QA-A","price":10.0,"currency":"USD","market_time":cap-5,"delay_min":15}]}

class Publication(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name).resolve()
        self.target=self.root/"snapshot.json"
    def put(self, raw=None):
        return publish(sample() if raw is None else raw,self.root,now=NOW)
    def test_valid(self):
        self.assertEqual(self.put(),"PUBLISHED")
        self.assertEqual(self.target.stat().st_mode & 0o777,0o600)
        self.assertEqual(decode(self.target.read_bytes())[0],NOW-10)
    def test_idempotent(self):
        self.put();old=self.target.stat().st_ino
        self.assertEqual(self.put(),"ALREADY_PUBLISHED")
        self.assertEqual(self.target.stat().st_ino,old)
    def test_older(self):
        self.put();old=self.target.read_bytes()
        self.assertEqual(self.put(sample(NOW-11)),"REPLAY_DENIED")
        self.assertEqual(self.target.read_bytes(),old)
    def test_same_time_changed(self):
        self.put();old=self.target.read_bytes()
        q=sample();q["rows"][0]["price"]=11.
        self.assertEqual(self.put(q),"REPLAY_DENIED")
        self.assertEqual(self.target.read_bytes(),old)
    def test_newer(self):
        self.put();self.assertEqual(self.put(sample(NOW-9)),"PUBLISHED")
        self.assertEqual(decode(self.target.read_bytes())[0],NOW-9)
    def test_bad_input_preserves(self):
        self.put();old=self.target.read_bytes()
        for q in (sample(NOW-601),sample(NOW+1),dict(sample(),warnings=["incomplete"])):
            self.assertEqual(self.put(q),"DENIED")
            self.assertEqual(self.target.read_bytes(),old)
    def test_mode(self):
        self.put();self.target.chmod(0o644)
        self.assertEqual(self.put(sample(NOW-9)),"DENIED")
    def test_bad_existing(self):
        self.target.write_text("{}");self.target.chmod(0o600)
        self.assertEqual(self.put(),"DENIED")
        self.assertEqual(self.target.read_text(),"{}")
    def test_symlink(self):
        other=self.root/"other";other.write_text("unchanged")
        self.target.symlink_to(other)
        self.assertEqual(self.put(),"DENIED")
        self.assertEqual(other.read_text(),"unchanged")
    def test_hardlink(self):
        self.put();os.link(self.target,self.root/"other")
        self.assertEqual(self.put(sample(NOW-9)),"DENIED")
    def test_busy(self):
        with open(self.root/".publish.lock","w") as f:
            os.fchmod(f.fileno(),0o600);fcntl.flock(f,fcntl.LOCK_EX)
            self.assertEqual(self.put(),"BUSY")
        self.assertFalse(self.target.exists())
    def test_directory_mode(self):
        self.root.chmod(0o755)
        self.assertEqual(self.put(),"DENIED")
    def test_collision_never_deletes_existing_temp(self):
        target=self.root/('.next-'+'a'*32);target.write_text('other writer')
        with patch('screener_inbox_publish_candidate.secrets.token_hex',return_value='a'*32):
            self.assertEqual(self.put(),'DENIED')
        self.assertEqual(target.read_text(),'other writer')
    def test_post_replace_fsync_uncertainty(self):
        original=os.fsync
        def fail_dir(fd):
            import stat
            if stat.S_ISDIR(os.fstat(fd).st_mode):raise OSError('synthetic fsync failure')
            return original(fd)
        with patch('screener_inbox_publish_candidate.os.fsync',side_effect=fail_dir):
            self.assertEqual(self.put(),'PUBLICATION_UNCERTAIN_REVIEW_REQUIRED')
        self.assertTrue(self.target.exists())
    def test_current_relay_denies_screener(self):
        clock=[0];budget=SharedWindow(clock=lambda:clock[0]);clock[0]=600
        self.assertFalse(budget.admit("screener"))
        self.assertTrue(all(budget.admit("history") for _ in range(6)))
        self.assertTrue(all(budget.admit("quote") for _ in range(2)))
        self.assertFalse(budget.admit("history"))
        self.assertFalse(budget.admit("screener"))
if __name__=="__main__":unittest.main(verbosity=2)
