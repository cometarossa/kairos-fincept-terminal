"""Offline original Python history QA diagnostics: no network, no secrets.

Injected pandas frames and exact yfinance error registry only. Categories are
inferences, not independently verified Yahoo HTTP status or proof of market data.
"""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'fincept-qt/scripts/yfinance_data.py'
MARKET = ROOT / 'fincept-qt/src/services/markets/MarketDataService.cpp'
WORKER = ROOT / 'fincept-qt/src/python/PythonWorker.cpp'
OPTIN = 'FINCEPT_PUBLIC_MCP_HISTORY_QA'
APPROVED = 'SPY_5D_PUBLIC_READ'

class PublicYahooFailureClasses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous = sys.modules.get('yfinance')
        cls.fake = types.ModuleType('yfinance')
        cls.fake.Ticker = lambda *_: (_ for _ in ()).throw(AssertionError('No provider access'))
        cls.fake.shared = types.SimpleNamespace(_ERRORS={})
        sys.modules['yfinance'] = cls.fake
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            spec = importlib.util.spec_from_file_location('original_fincept_history_qa_class_v1', SCRIPT)
            assert spec and spec.loader
            cls.mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.mod)
        finally:
            sys.path.remove(str(SCRIPT.parent))

    @classmethod
    def tearDownClass(cls):
        if cls.previous is None:
            sys.modules.pop('yfinance', None)
        else:
            sys.modules['yfinance'] = cls.previous

    def setUp(self):
        self.fake.shared._ERRORS.clear()

    def _run_empty(self, enabled=True, symbol='SPY', period='5d', interval='1d', error=None):
        def provider(**_):
            if error:
                self.fake.shared._ERRORS[symbol] = error
            return pd.DataFrame()
        env = {OPTIN: APPROVED} if enabled else {}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(self.fake, 'Ticker', return_value=types.SimpleNamespace(history=provider)):
                return self.mod.get_historical_period(symbol, period, interval)

    def test_default_off_preserves_empty_list_and_does_not_classify(self):
        self.assertEqual(self._run_empty(enabled=False, error='HTTP 429 throttled'), [])

    def test_approved_empty_no_reason_remains_unattributed(self):
        result = self._run_empty()
        self.assertEqual(result, {'error': 'HISTORY_UNAVAILABLE', 'qa_failure_class': 'EMPTY_UNATTRIBUTED'})

    def test_approved_rate_limit_is_hypothesis_only_and_leaks_nothing(self):
        result = self._run_empty(error='YFRateLimitError 429 cookie:SECRET_URL?token=NOT_FOR_LOGS')
        self.assertEqual(result['qa_failure_class'], 'POSSIBLE_RATE_LIMIT')
        self.assertNotIn('SECRET', str(result))
        self.assertNotIn('429', str(result))

    def test_malformed_proxy_crumb_timeout_and_auth_inferences_are_bounded(self):
        examples = [
            ('curl ProxyError via https://secret.example/path?crumb=SENSITIVE', 'POSSIBLE_PROXY_FAILURE'),
            ('Request timed out with confidential URL', 'POSSIBLE_TIMEOUT'),
            ('SSLerror certificate failed; Bearer PROTECTED', 'POSSIBLE_TLS_FAILURE'),
            ('Cookie fetch returned bad crumb: ABCSECRET', 'POSSIBLE_CRUMB_OR_COOKIE'),
            ('HTTP 403 credential in query', 'POSSIBLE_AUTH_DENIAL'),
            ('No price data found, possibly delisted', 'YFINANCE_GENERIC_NO_PRICE'),
        ]
        for diagnostic, expected in examples:
            with self.subTest(expected=expected):
                result = self._run_empty(error=diagnostic)
                self.assertEqual(result['qa_failure_class'], expected)
                self.assertEqual(result['error'], 'HISTORY_UNAVAILABLE')
                self.assertNotIn('SECRET', str(result))
                self.assertNotIn('PROTECTED', str(result))

    def test_yfinance_generic_possibly_delisted_is_not_listing_evidence(self):
        # In yfinance 0.2.61 this generic phrase arises for MANY upstream
        # invalid-chart responses, not a verified delisting event.
        for diagnostic in ('possibly delisted; no price data found (period=5d)',
                           'YFPricesMissingError: missing chart quote'):
            with self.subTest(diagnostic=diagnostic):
                result = self._run_empty(error=diagnostic)
                self.assertEqual(result['qa_failure_class'], 'YFINANCE_GENERIC_NO_PRICE')
                self.assertNotIn('delisted', str(result).lower())

    def test_stale_error_cannot_label_next_new_empty_request(self):
        self.fake.shared._ERRORS['SPY'] = 'YFRateLimitError previously'
        result = self._run_empty()
        self.assertEqual(result['qa_failure_class'], 'EMPTY_UNATTRIBUTED')
        self.assertNotIn('SPY', self.fake.shared._ERRORS)

    def test_unapproved_symbol_or_window_preserve_original_non_qa_behavior(self):
        for symbol, period, interval in [('NVDA', '5d', '1d'), ('SPY', '1mo', '1d'), ('SPY', '5d', '1h')]:
            with self.subTest(symbol=symbol, period=period, interval=interval):
                self.assertEqual(self._run_empty(True, symbol, period, interval, error='HTTP 429'), [])

    def test_exception_is_fixed_class_with_no_raw_exception_body(self):
        with patch.dict(os.environ, {OPTIN: APPROVED}, clear=True):
            with patch.object(self.fake, 'Ticker', side_effect=TimeoutError('HTTP_URL_SECRET / crumb token')):
                result = self.mod.get_historical_period('SPY', '5d', '1d')
        self.assertEqual(result, {'error': 'HISTORY_UNAVAILABLE', 'qa_failure_class': 'POSSIBLE_TIMEOUT'})
        self.assertNotIn('HTTP_URL_SECRET', str(result))

    def test_exception_without_evidence_is_not_misrepresented_as_confirmed_error(self):
        with patch.dict(os.environ, {OPTIN: APPROVED}, clear=True):
            with patch.object(self.fake, 'Ticker', side_effect=ValueError('private details')):
                result = self.mod.get_historical_period('SPY', '5d', '1d')
        self.assertEqual(result['qa_failure_class'], 'EXCEPTION_UNCLASSIFIED')
        self.assertNotIn('private details', str(result))

    def test_native_finite_class_allowlist_and_only_explicit_selftest(self):
        source = MARKET.read_text()
        self.assertIn('QCoreApplication::arguments().contains(QStringLiteral("--selftest-mcp-server"))', source)
        self.assertIn('FINCEPT_PUBLIC_MCP_HISTORY_QA', source)
        self.assertIn('kAllowed.contains(category) ? category : QStringLiteral("MISSING_OR_UNRECOGNIZED")', source)
        self.assertIn('QA_YAHOO_HISTORY_CLASS=', source)
        self.assertIn('history_integrity::decode(doc)', source)
        self.assertIn('cb(false, {});', source)

    def test_pythonworker_public_qa_stderr_must_be_redacted(self):
        worker = WORKER.read_text()
        self.assertIn('Public Yahoo QA stderr withheld (untrusted provider output)', worker)
        self.assertIn('if (public_history_qa)', worker)
        self.assertIn('QCoreApplication::arguments().contains(QStringLiteral("--selftest-mcp-server"))', worker)
        self.assertIn('LOG_WARN("PythonWorker", QString("stderr: %1")', worker)

if __name__ == '__main__':
    unittest.main()
