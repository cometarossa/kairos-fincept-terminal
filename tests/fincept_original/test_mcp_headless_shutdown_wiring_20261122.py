"""Source contract: packaged MCP selftest uses the normal cleanup path.

Real certification requires the packaged AppImage to exit zero; CI tests that.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class NativeMcpHeadlessShutdown(unittest.TestCase):
    def test_gui_and_mcp_selftest_share_orderly_cleanup(self):
        src = (ROOT/'fincept-qt/src/app/main.cpp').read_text()
        self.assertIn('const auto shutdown_application_services = []() {',src)
        self.assertIn('QObject::connect(&app, &QCoreApplication::aboutToQuit, shutdown_application_services);',src)
        self.assertIn('const int result = suite.run();',src)
        block = src[src.index('for (const auto& suite : kSelftestSuites) {',src.index('if (qstrcmp(argv[i], "--dump-tools") == 0)')):]
        self.assertIn('if (qstrcmp(argv[i], "--selftest-mcp-server") == 0)',block)
        self.assertIn('shutdown_application_services();',block)
        self.assertIn('return result;',block)
    def test_packaged_mcp_exit_is_strict_gate_not_log_only(self):
        workflow=(ROOT/'.github/workflows/build-linux-qa.yml').read_text()
        self.assertIn('run: |\n        set -euo pipefail',workflow,\n                      'The packaged gate must be a literal multiline shell script, not folded into a comment')
        self.assertIn('timeout 35 "$APPIMAGE" --profile ci-packaged-mcp-shutdown --selftest-mcp-server',workflow)
        self.assertIn('grep -q "60 passed, 0 failed"',workflow)
        self.assertIn('|| { tail -n 60 /tmp/fincept-mcp-lifecycle-ci.log; exit 1; }',workflow)

if __name__ == '__main__':
    unittest.main()
