"""Independent source boundary checks; they are NOT native runtime QA."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / 'fincept-qt/src/services/markets/MarketDataService.h'
SOURCE = ROOT / 'fincept-qt/src/services/markets/MarketDataService.cpp'
NATIVE = ROOT / 'fincept-qt/src/mcp/server/McpServerSelfTest.cpp'


class NativeMcpHistoryFixtureBoundary(unittest.TestCase):
    def test_only_native_selftest_function_is_friend(self):
        h = HEADER.read_text()
        self.assertIn('friend int fincept::mcp::run_mcp_server_selftest();', h)
        self.assertIn('  private:', h)
        self.assertLess(h.index('  private:'), h.index('history_selftest_fixture_'))
        self.assertNotIn('set_history_fixture', h)

    def test_fixture_is_scoped_behind_early_return(self):
        body = SOURCE.read_text()
        start = body.index('void MarketDataService::fetch_history(')
        boundary = body.index('// ── Static symbol lists', start)
        function = body[start:boundary]
        self.assertLess(function.index('if (history_selftest_fixture_.has_value())'),
                        function.index('python::PythonRunner::instance().run("yfinance_data.py"'))
        self.assertIn('QCoreApplication::arguments().contains(QStringLiteral("--selftest-mcp-server"))', function)
        self.assertIn('symbol == fixture.symbol && period == fixture.period && interval == fixture.interval', function)
        self.assertIn('cb(match, bars)', function)
        self.assertIn('return;\n    }\n    QStringList args;', function)

    def test_fixture_does_not_read_env_or_cache(self):
        s = SOURCE.read_text()
        block = s[s.index('if (history_selftest_fixture_.has_value())'):s.index('    QStringList args;', s.index('if (history_selftest_fixture_.has_value())'))]
        self.assertNotIn('qEnvironmentVariable', block)
        self.assertNotIn('CacheManager', block)
        self.assertNotIn('PythonRunner', block.split('QTimer::singleShot')[1])

    def test_native_selftest_clears_fixture(self):
        s = NATIVE.read_text()
        self.assertIn('markets.history_selftest_fixture_.reset()', s)
        self.assertIn('synthetic history mismatched window fails closed without provider', s)
        self.assertIn('get_history', s)


if __name__ == '__main__':
    unittest.main()
