"""Real POSIX descendant pipe-lifetime regressions for Fincept PR #25.

Run only in the disposable offline checkout. No broker, network, or app profile.
The launched Python process forms a private session/process group; its child
inherits captured stdout/stderr descriptors unless it deliberately closes them.
"""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

from research.kairos_bridge_v1.sidecar import BridgeRejected, _capture_bounded


@unittest.skipUnless(os.name == "posix", "POSIX process-group boundary only")
class DescendantCaptureTests(unittest.TestCase):
    def test_orphaned_pipe_holder_is_killed_at_deadline(self):
        """Parent exits 0, but its spawned child keeps inherited pipes open."""
        with tempfile.TemporaryDirectory() as tmp:
            ready = Path(tmp, "descendant-started")
            should_never_exist = Path(tmp, "descendant-survived")
            grandchild = (
                "from pathlib import Path;import sys,time;"
                "Path(sys.argv[1]).write_text('started');"
                "time.sleep(1);"
                "Path(sys.argv[2]).write_text('survived')"
            )
            parent = (
                "import subprocess,sys;"
                "subprocess.Popen([sys.executable,'-c',sys.argv[1],"
                "sys.argv[2],sys.argv[3]],stdin=subprocess.DEVNULL)"
            )
            with self.assertRaisesRegex(BridgeRejected, "PINNED_TOOL_UNAVAILABLE_OR_TIMEOUT"):
                _capture_bounded(
                    [sys.executable, "-c", parent, grandchild,
                     str(ready), str(should_never_exist)],
                    cwd=tmp, env={}, timeout=0.5, limit=4096,
                )
            self.assertTrue(ready.exists(), "Descendant did not start: invalid test")
            # A leaked child would create this file 1 second after start.
            time.sleep(1.2)
            self.assertFalse(
                should_never_exist.exists(),
                "Timed-out descendant survived private-group cleanup",
            )

    def test_successful_descendant_closes_pipes_and_returns_stdout(self):
        """A short-lived inherited-pipe writer can finish normally."""
        with tempfile.TemporaryDirectory() as tmp:
            grandchild = (
                "import sys,time;"
                "time.sleep(0.08);"
                "sys.stdout.write('{\\\"ok\\\":true}');"
                "sys.stdout.flush()"
            )
            parent = (
                "import subprocess,sys;"
                "subprocess.Popen([sys.executable,'-c',sys.argv[1]],"
                "stdin=subprocess.DEVNULL)"
            )
            code, out = _capture_bounded(
                [sys.executable, "-c", parent, grandchild],
                cwd=tmp, env={}, timeout=2, limit=4096,
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, '{"ok":true}')


if __name__ == "__main__":
    unittest.main()
