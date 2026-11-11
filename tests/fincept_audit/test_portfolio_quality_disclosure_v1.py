"""Current-source disclosure tests and exact original/candidate numeric parity.

Original source is read from a fixed Git commit by the parent audit helper.
No provider, broker or installed Fincept runtime is invoked.
"""
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
import sys
import unittest
from unittest.mock import patch

import pandas as pd

from test_portfolio_metrics_oracle_v1 import ROOT, SCRIPTS, fixture, load_original


class PortfolioQualityDisclosureTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        for target in ['socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.create_connection', 'socket.getaddrinfo']:
            stack.enter_context(patch(target, side_effect=AssertionError('NETWORK_DENIED')))
        stack.enter_context(patch.dict(sys.modules, {'fincept_json': load_original('fincept_json')}))
        self.original = load_original('portfolio_metrics')
        path = SCRIPTS / 'portfolio_metrics.py'
        spec = importlib.util.spec_from_file_location('portfolio_candidate', path)
        self.current = importlib.util.module_from_spec(spec)
        exec(compile(path.read_bytes(), str(path), 'exec'), self.current.__dict__)
        self.payload = {'symbols': ['ALPHA', 'BETA'], 'benchmark': 'BENCH',
                        'weights': {'ALPHA': .25, 'BETA': .75}}

    def run_module(self, module, data):
        with patch.object(module, '_download', return_value=data) as download:
            result = module.analytics(self.payload)
        download.assert_called_once()
        json.dumps(result, allow_nan=False)
        return result

    def test_numerical_parity_across_missing_data_scenarios(self):
        scenarios = {'complete': fixture(), 'flat': fixture(flat=True), 'short': fixture(10)}
        for label, rows in [('late', slice(0, 20)), ('too_late', slice(0, 50)),
                            ('stale', slice(21, None)), ('one_return', slice(2, None)),
                            ('gap', slice(30, 31)), ('absent', slice(None))]:
            frame = fixture()
            frame.loc[frame.index[rows], ('BETA', 'Close')] = float('nan')
            scenarios[label] = frame
        for label, frame in scenarios.items():
            with self.subTest(label=label):
                before = self.run_module(self.original, frame)
                after = self.run_module(self.current, frame)
                old_warnings = before.pop('warnings')
                new_warnings = after.pop('warnings')
                self.assertEqual(before, after)  # Exact equality, not just tolerance.
                self.assertTrue(all(w in new_warnings for w in old_warnings))

    def test_stale_tail_discloses_forty_padded_returns(self):
        data = fixture()
        data.loc[data.index[21:], ('BETA', 'Close')] = float('nan')
        result = self.run_module(self.current, data)
        self.assertIn('BETA: 40 missing return observations treated as zero; calendar/data completeness unverified', result['warnings'])

    def test_internal_gap_discloses_padding(self):
        data = fixture()
        data.loc[data.index[30], ('BETA', 'Close')] = float('nan')
        result = self.run_module(self.current, data)
        self.assertIn('BETA: 1 missing return observations treated as zero; calendar/data completeness unverified', result['warnings'])

    def test_insufficient_return_exclusion_is_disclosed(self):
        data = fixture()
        data.loc[data.index[2:], ('BETA', 'Close')] = float('nan')
        result = self.run_module(self.current, data)
        self.assertIn('BETA: fewer than 2 finite returns; excluded from risk estimates', result['warnings'])

    def test_short_shared_history_preserves_existing_warning(self):
        data = fixture()
        data.loc[data.index[:50], ('BETA', 'Close')] = float('nan')
        result = self.run_module(self.current, data)
        self.assertIn('short shared history — earliest listings padded with zero returns', result['warnings'])
        self.assertIn('BETA: 50 missing return observations treated as zero; calendar/data completeness unverified', result['warnings'])

    def test_complete_and_sufficient_shared_history_have_no_new_warnings(self):
        for start in [0, 20]:
            data = fixture()
            data.loc[data.index[:start], ('BETA', 'Close')] = float('nan')
            self.assertEqual(self.run_module(self.current, data)['warnings'], [])

    def test_original_download_error_contract_is_preserved(self):
        for module in [self.original, self.current]:
            output = io.StringIO()
            with patch.object(module, '_download', side_effect=RuntimeError('fixture unavailable')):
                with redirect_stdout(output), self.assertRaises(SystemExit) as error:
                    module.analytics(self.payload)
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(json.loads(output.getvalue()), {'error': 'price download failed: fixture unavailable'})

    def test_warning_is_in_original_cli_json_channel(self):
        data = fixture()
        data.loc[data.index[21:], ('BETA', 'Close')] = float('nan')
        output = io.StringIO()
        with patch.object(self.current, '_download', return_value=data), redirect_stdout(output):
            self.current.main(['portfolio_metrics.py', 'analytics', json.dumps(self.payload)])
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertTrue(any('40 missing return' in w for w in json.loads(output.getvalue())['warnings']))

    def test_qt_source_consumes_warnings_in_existing_status_tooltip(self):
        # Source contract ONLY. A native build and runtime test remain required.
        source = (ROOT / 'fincept-qt/src/screens/portfolio/PortfolioScreen_Handlers.cpp').read_text()
        handler = source.split('void PortfolioScreen::on_market_analytics(', 1)[1].split('void PortfolioScreen::on_summary_error', 1)[0]
        self.assertIn('a.warnings.join(QStringLiteral("\\n"))', handler)
        self.assertIn('!ok || !a.missing.isEmpty() || !a.warnings.isEmpty()', handler)


if __name__ == '__main__':
    unittest.main()
