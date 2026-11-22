"""Static and negative public QA constraints; not evidence of real provider QA."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class PublicYahooQABoundaries(unittest.TestCase):
    def test_original_qt_selftest_never_enables_public_provider_by_default(self):
        cpp=(ROOT/'fincept-qt/src/mcp/server/McpServerSelfTest.cpp').read_text()
        self.assertIn('FINCEPT_PUBLIC_MCP_HISTORY_QA', cpp)
        self.assertIn('SPY_5D_PUBLIC_READ', cpp)
        self.assertIn('public_qa.isEmpty()', cpp)
        self.assertIn('FINCEPT_PUBLIC_QA_SANDBOX_VERIFIED', cpp)
        self.assertIn('EPERM_EXTERNAL', cpp)
        self.assertIn('FINCEPT_PUBLIC_MCP_HISTORY_CLIENT_SCRIPT', cpp)
        self.assertIn('FINCEPT_PUBLIC_MCP_HISTORY_PYTHON', cpp)
        self.assertIn('real public Yahoo history passed original Qt MCP to external KAIROS', cpp)
        self.assertLess(cpp.index('markets.history_selftest_fixture_.reset()'),cpp.index('FINCEPT_PUBLIC_MCP_HISTORY_QA'))
        service = (ROOT/'fincept-qt/src/services/markets/MarketDataService.cpp').read_text()
        self.assertIn('QCoreApplication::arguments().contains(QStringLiteral("--selftest-mcp-server"))', service)
        self.assertIn('history_integrity::decode(doc)', service)
        self.assertNotIn('cb(true, {});', service[service.index('void MarketDataService::fetch_history('):service.index('// ── Static symbol lists', service.index('void MarketDataService::fetch_history('))])

    def test_original_pythonrunner_secrets_are_not_read_during_public_qa(self):
        cpp=(ROOT/'fincept-qt/src/python/PythonRunner.cpp').read_text()
        self.assertIn('public_history_qa',cpp)
        self.assertIn('if (public_history_qa) {\n            env.remove(key);\n            continue;\n        }',cpp)
        self.assertIn('SecureStorage::instance().retrieve(key)',cpp)
        self.assertIn('route_yfinance_to_daemon(args, cb)', cpp)
        self.assertNotIn('public_history_subprocess_qa', cpp)

    def test_proxy_denies_ig_and_any_non_yahoo_domain(self):
        from public_yahoo_only_connect_proxy_v1 import parse_connect
        self.assertIsNone(parse_connect(b'CONNECT demo-api.ig.com:443 HTTP/1.1'))
        self.assertIsNone(parse_connect(b'CONNECT api.ig.com:443 HTTP/1.1'))
        self.assertIsNone(parse_connect(b'CONNECT 169.254.169.254:80 HTTP/1.1'))

if __name__=='__main__':unittest.main()
