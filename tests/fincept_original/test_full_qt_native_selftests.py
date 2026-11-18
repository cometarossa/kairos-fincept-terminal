"""Opt-in original FinceptTerminal Qt macOS runtime QA, no external network.

Requires an independently compiled original FinceptTerminal.app binary:
    FINCEPT_QT_NATIVE_BINARY=/absolute/path/FinceptTerminal \
        python3 -m unittest discover -s tests/fincept_original \
        -p 'test_full_qt_native_selftests.py' -v

Runs the complete selftest registry (not GUI or provider/broker integration)
with a fresh empty HOME per invocation and a macOS Seatbelt network sandbox.
Only the original MCP server test can bind/connect on localhost; all other
selftests are denied all network access. The connected user's existing
Fincept settings and trading sessions are not passed to the test process.
No test enables execution, broker credentials, or live market requests.

If no binary is explicitly selected, tests SKIP rather than silently running
an installed/different version of Fincept. If selected but missing/unsafe
platform sandbox, tests FAIL rather than claiming a PASS.
"""
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest


BINARY_ENV = "FINCEPT_QT_NATIVE_BINARY"
OFFLINE = "(version 1) (allow default) (deny network*)"
LOCALHOST_ONLY = """(version 1)
(allow default)
(deny network-bind (local ip "*:*"))
(deny network-outbound (remote ip "*:*"))
(allow network-bind (local ip "localhost:*"))
(allow network-outbound (remote ip "localhost:*"))"""
FLAGS = (
    "--selftest-tools",
    "--selftest-llm-tools",
    "--selftest-mcp-server",
    "--selftest-feeds",
    "--selftest-dock-layout",
    "--selftest-live-table",
    "--selftest-fno-algo",
    "--selftest-universe-scan",
    "--selftest-paper",
    "--selftest-portfolio-monitor",
    "--selftest-portfolio-replication",
    "--selftest-arena",
)


class OriginalQtNativeRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selected = os.getenv(BINARY_ENV)
        if not selected:
            raise unittest.SkipTest("No explicitly selected new original Qt binary")
        cls.binary = Path(selected).expanduser().resolve()
        if not cls.binary.is_file() or not os.access(cls.binary, os.X_OK):
            raise AssertionError(f"Selected Qt binary unavailable: {cls.binary}")
        if platform.system() != "Darwin" or not Path("/usr/bin/sandbox-exec").is_file():
            raise AssertionError("Mac sandbox-exec required; no unsafe fallback")
        # Apple's system Python may have a different Seatbelt network policy
        # than the explicitly validated QA interpreter. Prefer Python 3.11.
        cls.python = shutil.which("python3.11") or shutil.which("python3") or shutil.which("python")
        if not cls.python:
            raise AssertionError("Python required for sandbox policy preflight")

    @classmethod
    def isolated_run(cls, *command, local_network=False, timeout=75):
        profile = LOCALHOST_ONLY if local_network else OFFLINE
        with tempfile.TemporaryDirectory(prefix="fincept-native-offline-qa-") as home:
            env = {
                "HOME": home, "TMPDIR": home,
                "XDG_CONFIG_HOME": home + "/.config",
                "XDG_DATA_HOME": home + "/.data",
                "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/local/bin",
                "QT_QPA_PLATFORM": "offscreen",
                "QT_QUICK_BACKEND": "software",
                "QTWEBENGINE_CHROMIUM_FLAGS": "--disable-gpu",
                "LC_ALL": "en_US.UTF-8",
            }
            return subprocess.run(
                ["/usr/bin/sandbox-exec", "-p", profile, *map(str, command)],
                env=env, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=timeout, check=False,
            )

    def test_loopback_policy_denies_all_external_sockets(self):
        # No broker address is contacted. A denied socket to a fixed public
        # probe address must be EPERM. macOS Seatbelt can deny Python's local
        # AF_INET bind even while the original Qt server CAN bind/connect;
        # original --selftest-mcp-server independently verifies local IPC.
        script = """import errno, socket, sys
external = socket.socket(); external.settimeout(.5)
try:
    rc = external.connect_ex(('1.1.1.1', 443))
finally:
    external.close()
if rc != errno.EPERM:
    print('External network sandbox not proven:', rc)
    sys.exit(1)
print('LOOPBACK_ONLY_EXTERNAL_DENIED')
"""
        p = self.isolated_run(self.python, "-c", script, local_network=True)
        self.assertEqual(p.returncode, 0, p.stdout[-1200:])
        self.assertIn("LOOPBACK_ONLY_EXTERNAL_DENIED", p.stdout)

    def test_original_binary_enumerates_12_selftest_suites(self):
        p = self.isolated_run(self.binary, "--selftest-list")
        self.assertEqual(p.returncode, 0, p.stdout[-2200:])
        discovered = [s.strip() for s in p.stdout.splitlines() if s.startswith("--selftest-")]
        self.assertEqual(discovered, list(FLAGS))

    def test_original_52_screen_smoke_without_external_network(self):
        # Actual WindowFrame / DockScreenRouter creates every screen using
        # the freshly compiled binary, in an isolated profile with no broker
        # credentials or Internet sockets. This is construction, not data QA.
        p = self.isolated_run(self.binary, "--smoke-test", timeout=100)
        self.assertEqual(p.returncode, 0, p.stdout[-3300:])
        self.assertIn("[Smoke] OK: all 52 screens constructed", p.stdout)
        self.assertEqual(
            p.stdout.count("[Smoke] >>> constructing"), 52,
            "All 52 original screens must participate in the walk",
        )

    def test_all_original_selftest_suites(self):
        for flag in FLAGS:
            with self.subTest(suite=flag):
                p = self.isolated_run(
                    self.binary, flag, local_network=(flag == "--selftest-mcp-server")
                )
                self.assertEqual(p.returncode, 0, f"{flag} failed:\n{p.stdout[-1800:]}")
                if flag == "--selftest-mcp-server":
                    self.assertIn("60 passed, 0 failed", p.stdout)
                    for required in (
                        "synthetic quote test cache database is open",
                        "synthetic quote was seeded without provider calls",
                        "real get_quote MCP handler returns cached synthetic quote",
                        "real get_quote preserves local receipt; market as-of remains unknown",
                        "real get_quote denies clock, freshness, science and execution authority",
                        "synthetic history fixture armed without Python/provider access",
                        "original get_history MCP returns latest synthetic OHLCV bars only",
                        "synthetic history mismatched window fails closed without provider",
                        "synthetic history fixture cleared before end of selftest",
                        "provider history integrity accepts valid OHLCV UTC bars",
                        "provider history integrity rejects missing close",
                        "provider history integrity rejects unknown volume, not zero",
                        "provider history integrity rejects duplicate timestamp",
                        "provider history integrity rejects nonmonotonic timestamps",
                        "provider history integrity rejects fractional UTC epoch",
                        "provider history integrity rejects future timestamp",
                        "provider history integrity rejects inconsistent OHLC envelope",
                        "provider history integrity rejects negative OHLC price",
                        "provider history integrity rejects noninteger volume",
                    ):
                        self.assertIn("[PASS] " + required, p.stdout)
                elif flag == "--selftest-tools":
                    self.assertIn("VERDICT: PASS", p.stdout)


if __name__ == "__main__":
    unittest.main()
