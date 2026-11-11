"""Independent synthetic oracles for ORIGINAL Fincept portfolio analytics.

Only the download boundary is replaced in memory. No production adapter,
provider/GUI certification, economic evidence or broker authority is implied.
Run in a dedicated process: python -m unittest discover -s tests/fincept_audit
    -p 'test_portfolio_metrics_oracle_v1.py' -v
"""
from contextlib import ExitStack, redirect_stdout
from hashlib import sha256
import importlib.util
import io
import json
import math
import statistics
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'fincept-qt/scripts'
PINS = {
    'portfolio_metrics': '03c120bc7af9c2a9d25de62a69e9d4e62942e3726bff8841a388d744bbbe76a2',
    'fincept_json': '438f3d2353e18a24946b0899ef4ecf6f1689b70df999ee9372e26e989c4e62c7',
}


def load_original(name):
    path = SCRIPTS / (name + '.py')
    source = path.read_bytes()
    if sha256(source).hexdigest() != PINS[name]:
        raise AssertionError('ORIGINAL_SOURCE_CHANGED: ' + name)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Execute the exact verified bytes; do not reuse a stale .pyc.
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def fixture(n=60, flat=False):
    """Known returns: benchmark +/-1%, ALPHA twice, BETA half.

    61 daily closes yield 60 returns, 30 losses and 30 gains. Names and
    prices are fabricated. IRX is a constant synthetic 4% yield quote.
    """
    index = pd.date_range('2020-01-01', periods=n + 1, freq='D')
    columns = {}
    for symbol, scale in [('ALPHA', 2), ('BETA', .5), ('BENCH', 1)]:
        values = [100.0]
        for i in range(n):
            r = 0 if flat else (.01 if i % 2 else -.01) * scale
            values.append(values[-1] * (1 + r))
        columns[(symbol, 'Close')] = values
    columns[('^IRX', 'Close')] = [4.0] * (n + 1)
    return pd.DataFrame(columns, index=index)


class PortfolioMetricsOracleTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        # Defense in depth only: not an OS sandbox or a native-library guard.
        for target in ['socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.create_connection', 'socket.getaddrinfo']:
            stack.enter_context(patch(target, side_effect=AssertionError('NETWORK_DENIED')))
        helper = load_original('fincept_json')
        stack.enter_context(patch.dict(sys.modules, {'fincept_json': helper}))
        self.mod = load_original('portfolio_metrics')
        self.data = fixture()
        self.download = stack.enter_context(patch.object(self.mod, '_download', return_value=self.data))
        self.payload = {'symbols': ['ALPHA', 'BETA'], 'benchmark': 'BENCH',
                        'weights': {'ALPHA': .25, 'BETA': .75}}

    def calculate(self):
        result = self.mod.analytics(self.payload)
        # Strict JSON check before any serializer could sanitize invalid output.
        json.dumps(result, allow_nan=False)
        self.download.assert_called_once_with(['ALPHA', 'BETA', 'BENCH', '^IRX'], '1y')
        return result

    def test_weighted_risk_against_closed_form(self):
        p = self.calculate()['portfolio']
        # Portfolio return = (.25*2 + .75*.5)*benchmark = .875*benchmark.
        self.assertEqual(p['observations'], 60)
        self.assertEqual(p['coverage'], 1)
        self.assertEqual(p['periods_per_year'], 365.25)
        self.assertAlmostEqual(p['ann_vol'], .00875 * math.sqrt(60 / 59 * 365.25), places=12)
        self.assertAlmostEqual(p['var_95_1d'], .00875, places=12)
        self.assertAlmostEqual(p['cvar_95_1d'], .00875, places=12)
        self.assertAlmostEqual(p['beta'], .875, places=12)

    def test_correlation_beta_and_risk_contributions(self):
        r = self.calculate()
        self.assertEqual(r['correlation']['matrix'],
                         {'ALPHA|ALPHA': 1., 'ALPHA|BETA': 1., 'BETA|ALPHA': 1., 'BETA|BETA': 1.})
        for symbol, beta, contribution in [('ALPHA', 2, 4/7), ('BETA', .5, 3/7)]:
            self.assertAlmostEqual(r['holdings'][symbol]['beta'], beta, places=12)
            self.assertAlmostEqual(r['holdings'][symbol]['risk_contribution'], contribution, places=12)
        self.assertEqual(r['risk_free']['rate'], .04)
        self.assertEqual(r['as_of'], '2020-03-01')

    def test_missing_holding_is_disclosed_with_partial_coverage(self):
        self.download.return_value = self.data.drop(columns='BETA', level=0)
        r = self.calculate()
        self.assertEqual(r['missing'], ['BETA'])
        self.assertEqual(r['portfolio']['coverage'], .25)
        self.assertAlmostEqual(r['portfolio']['beta'], 2, places=12)
        self.assertTrue(any('BETA' in w for w in r['warnings']))

    def test_short_history_has_no_risk_estimate(self):
        self.download.return_value = fixture(n=10)
        r = self.calculate()
        self.assertEqual(r['portfolio']['observations'], 10)
        for key in ['ann_vol', 'var_95_1d', 'cvar_95_1d', 'beta']:
            self.assertIsNone(r['portfolio'][key])
        self.assertEqual(r['holdings'], {})
        self.assertTrue(any('not estimated' in w for w in r['warnings']))

    def test_flat_prices_do_not_invent_beta(self):
        self.download.return_value = fixture(flat=True)
        r = self.calculate()
        for key in ['ann_vol', 'var_95_1d', 'cvar_95_1d']:
            self.assertEqual(r['portfolio'][key], 0)
        self.assertIsNone(r['portfolio']['beta'])
        self.assertIsNone(r['holdings']['ALPHA']['risk_contribution'])

    def test_equal_weight_fallback_is_explicit(self):
        self.payload.pop('weights')
        r = self.calculate()
        self.assertAlmostEqual(r['portfolio']['beta'], 1.25, places=12)
        self.assertIn('no weights supplied — equal weights assumed', r['warnings'])

    def test_missing_benchmark_and_yield_are_disclosed(self):
        self.download.return_value = self.data.drop(columns=['BENCH', '^IRX'], level=0)
        r = self.calculate()
        self.assertIsNone(r['portfolio']['beta'])
        self.assertEqual(r['benchmark']['closes'], [])
        self.assertNotIn('risk_free', r)
        self.assertEqual(len(r['warnings']), 2)

    def test_input_frame_and_payload_are_unchanged(self):
        frame = self.data.copy(deep=True)
        payload = json.loads(json.dumps(self.payload))
        self.calculate()
        pd.testing.assert_frame_equal(self.data, frame)
        self.assertEqual(self.payload, payload)

    def test_download_failure_is_json_error_not_success(self):
        self.download.side_effect = RuntimeError('synthetic provider unavailable')
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as error:
            self.mod.analytics(self.payload)
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(json.loads(output.getvalue()),
                         {'error': 'price download failed: synthetic provider unavailable'})

    def test_empty_data_is_error(self):
        self.download.return_value = pd.DataFrame()
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as error:
            self.mod.analytics(self.payload)
        self.assertEqual(error.exception.code, 1)
        self.assertIn('no price data returned', json.loads(output.getvalue())['error'])

    def test_invalid_symbols_fail_before_download(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as error:
            self.mod.analytics({'symbols': []})
        self.assertEqual(error.exception.code, 1)
        self.assertIn('non-empty list', json.loads(output.getvalue())['error'])
        self.download.assert_not_called()

    def test_cli_stdout_is_single_strict_json_object(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.mod.main(['portfolio_metrics.py', 'analytics', json.dumps(self.payload)])
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        def reject_constant(value):
            raise AssertionError(value)
        r = json.loads(output.getvalue(), parse_constant=reject_constant)
        self.assertAlmostEqual(r['portfolio']['beta'], .875, places=12)

    def test_anticorrelation_retains_negative_risk_contribution(self):
        prices = [100.]
        for i in range(60):
            prices.append(prices[-1] * (1 + (.005 if i % 2 == 0 else -.005)))
        self.data[('BETA', 'Close')] = prices
        r = self.calculate()
        # 1/4 * 2 + 3/4 * -1/2 = 1/8 benchmark exposure.
        self.assertEqual(r['correlation']['matrix']['ALPHA|BETA'], -1.)
        self.assertAlmostEqual(r['portfolio']['beta'], .125, places=12)
        self.assertAlmostEqual(r['portfolio']['ann_vol'], .00125 * math.sqrt(60/59*365.25), places=12)
        self.assertAlmostEqual(r['holdings']['ALPHA']['risk_contribution'], 4., places=10)
        self.assertAlmostEqual(r['holdings']['BETA']['risk_contribution'], -3., places=10)

    def test_staggered_listing_uses_sufficient_shared_history(self):
        self.data.loc[self.data.index[:20], ('BETA', 'Close')] = float('nan')
        r = self.calculate()
        self.assertEqual(r['portfolio']['observations'], 40)
        self.assertEqual(r['portfolio']['start'], '2020-01-22')
        self.assertEqual(r['holdings']['BETA']['observations'], 40)
        self.assertAlmostEqual(r['portfolio']['ann_vol'], .00875 * math.sqrt(40/39*365.25), places=12)
        self.assertEqual(r['warnings'], [])

    def test_mixed_calendar_matches_explicit_zero_return_convention(self):
        # BETA has a fabricated observation every second day. This tests the
        # existing convention; it cannot establish whether a real gap is a closure.
        prices, last, beta_returns = [100.], 100., {}
        for day in range(1, 61):
            if day % 2:
                prices.append(float('nan'))
            else:
                ret = -.02 if (day // 2) % 2 else .02
                beta_returns[day] = ret
                last *= 1 + ret
                prices.append(last)
        self.data[('BETA', 'Close')] = prices
        r = self.calculate()
        expected = [.25 * (.02 if day % 2 == 0 else -.02)
                    + .75 * beta_returns.get(day, 0.) for day in range(2, 61)]
        self.assertEqual(r['portfolio']['observations'], 59)
        self.assertEqual(r['holdings']['BETA']['observations'], 30)
        self.assertAlmostEqual(r['portfolio']['ann_vol'], statistics.stdev(expected) * math.sqrt(365.25), places=12)
        self.assertAlmostEqual(r['holdings']['BETA']['ann_vol'], .02 * math.sqrt(30/29*182.625), places=12)

    def test_short_shared_history_characterizes_padding_warning(self):
        # Audit finding PM-01: PASS here means behavior reproduced, NOT that
        # padded observations are scientifically acceptable risk evidence.
        self.data.loc[self.data.index[:50], ('BETA', 'Close')] = float('nan')
        r = self.calculate()
        self.assertEqual(r['portfolio']['observations'], 60)
        self.assertEqual(r['holdings']['BETA']['observations'], 10)
        self.assertEqual(r['portfolio']['coverage'], 1.)
        self.assertIsNotNone(r['portfolio']['ann_vol'])
        self.assertIn('short shared history — earliest listings padded with zero returns', r['warnings'])

    def test_stale_tail_characterizes_undisclosed_padding(self):
        # PM-02: coverage is weight coverage, NOT date coverage or freshness.
        self.data.loc[self.data.index[21:], ('BETA', 'Close')] = float('nan')
        r = self.calculate()
        self.assertEqual(r['as_of'], '2020-03-01')
        self.assertEqual(r['portfolio']['coverage'], 1.)
        self.assertEqual(r['portfolio']['observations'], 60)
        self.assertEqual(r['holdings']['BETA']['observations'], 20)
        self.assertEqual(r['missing'], [])
        self.assertEqual(r['warnings'], [])
        expected = [.25 * (.02 if day % 2 == 0 else -.02)
                    + (.75 * (.005 if day % 2 == 0 else -.005) if day <= 20 else 0.)
                    for day in range(1, 61)]
        self.assertAlmostEqual(r['portfolio']['ann_vol'], statistics.stdev(expected) * math.sqrt(365.25), places=12)
        self.assertLess(r['portfolio']['ann_vol'], .00875 * math.sqrt(60/59*365.25))

    def test_internal_gap_characterizes_multiday_return(self):
        # PM-03: original cleaning drops the missing close before pct_change.
        self.data.loc[self.data.index[30], ('BETA', 'Close')] = float('nan')
        r = self.calculate()
        self.assertEqual(r['holdings']['BETA']['observations'], 59)
        self.assertEqual(r['warnings'], [])
        expected = []
        for day in range(1, 61):
            beta = .005 if day % 2 == 0 else -.005
            if day == 30:
                beta = 0.
            elif day == 31:
                beta = -.000025  # (1+.005)*(1-.005)-1: TWO-day return
            expected.append(.25 * (.02 if day % 2 == 0 else -.02) + .75 * beta)
        self.assertAlmostEqual(r['portfolio']['ann_vol'], statistics.stdev(expected) * math.sqrt(365.25), places=12)

    def test_two_closes_characterizes_missing_diagnostic_gap(self):
        # PM-04: two closes pass 'missing' classification but one return is
        # subsequently removed from priced holdings without a warning.
        self.data.loc[self.data.index[2:], ('BETA', 'Close')] = float('nan')
        r = self.calculate()
        self.assertEqual(r['missing'], [])
        self.assertNotIn('BETA', r['holdings'])
        self.assertEqual(r['portfolio']['coverage'], .25)
        self.assertEqual(r['warnings'], [])

    def test_all_holdings_absent_returns_no_portfolio(self):
        self.download.return_value = self.data.drop(columns=['ALPHA', 'BETA'], level=0)
        r = self.calculate()
        self.assertIsNone(r['portfolio'])
        self.assertEqual(r['holdings'], {})
        self.assertEqual(r['missing'], ['ALPHA', 'BETA'])


if __name__ == '__main__':
    unittest.main()
