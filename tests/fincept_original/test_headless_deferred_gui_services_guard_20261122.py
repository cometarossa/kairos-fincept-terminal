"""Do not start GUI market/network/broker deferred tasks from headless Qt selftests.

The true executable exit-code gate remains the Linux AppImage MCP selftest.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'fincept-qt/src/app/main.cpp'

class HeadlessDeferredServicesGuard(unittest.TestCase):
    def test_headless_mode_is_computed_before_gui_services_are_queued(self):
        s=SRC.read_text()
        declaration=s.index('const bool headless_run = [argc, argv]() {')
        self.assertEqual(s.count('const bool headless_run ='),1)
        self.assertLess(declaration,s.index('QTimer::singleShot(0, qApp, []() {'))
        self.assertIn('qstrncmp(argv[i], "--selftest", 10) == 0',s)
        self.assertIn('qstrcmp(argv[i], "--smoke-test") == 0',s)
        self.assertIn('qstrcmp(argv[i], "--dump-tools") == 0',s)

    def test_gui_market_prewarm_is_not_queued_in_headless_mode(self):
        s=SRC.read_text()
        self.assertIn('if (!headless_run)\n        QTimer::singleShot(0, qApp, []() {\n'
                      '        auto& hub = fincept::datahub::DataHub::instance();',s)
        self.assertIn('Pre-warmed %1 dashboard topics during login screen',s)

    def test_broker_and_cloud_services_cannot_launch_in_headless_nested_event_loop(self):
        s=SRC.read_text()
        self.assertIn('if (!headless_run)\n'
                      '        post_chain({init_hub_producers, init_cloud_sync, init_wallet_treasury_and_monitors});',s)
        self.assertIn('fincept::trading::AccountManager::instance().start_session_monitor();',s)

    def test_headless_prune_and_retention_are_both_gated(self):
        s=SRC.read_text()
        self.assertIn('if (!headless_run)\n                QTimer::singleShot(0, [news_cutoff]() {',s)
        self.assertIn('if (!headless_run)\n'
                      '            fincept::StorageManager::instance().start_retention_sweeper();',s)

if __name__ == '__main__': unittest.main()
