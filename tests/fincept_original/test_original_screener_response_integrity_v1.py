"""Synthetic transport tests of the original Screener backend. No provider calls."""
import json
import unittest
import copy
import importlib.util
from pathlib import Path
from unittest.mock import patch
SCRIPTS = Path(__file__).resolve().parents[2] / 'fincept-qt' / 'scripts'
spec = importlib.util.spec_from_file_location('fincept_original_screener_test', SCRIPTS / 'screener_data.py')
assert spec is not None and spec.loader is not None
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

class Response:

    def __init__(self, result=None, error=None, status=200):
        self.status_code = status
        self.payload = {'finance': {'result': [result] if result is not None else [], 'error': error}}

    def json(self):
        return copy.deepcopy(self.payload)

class Session:

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def post(self, url, **kw):
        self.calls.append(('post', url, kw))
        return self.results.pop(0)

    def get(self, **kw):
        self.calls.append(('get', None, kw))
        return self.results.pop(0)
Q = [{'symbol': 'QA-A', 'currency': 'GBp', 'financialCurrency': 'USD', 'regularMarketPrice': 125.0, 'marketCap': 5000000, 'regularMarketTime': 1700000000, 'exchangeDataDelayedBy': 15, 'regularMarketChangePercent': 4.5}, {'symbol': 'QA-B', 'currency': 'USD', 'regularMarketPrice': 20.0, 'regularMarketTime': 1700000060, 'exchangeDataDelayedBy': 0}]
R = [{'ticker': 'QA-B', 'sector': 'Technology', 'beta': 1.2, 'percentchange': 5.0}, {'ticker': 'QA-A', 'sector': 'Energy', 'beta': 0.7, 'percentchange': 6.0}]
C = {'region': ['us'], 'filters': [{'field': 'change_pct', 'op': 'gte', 'value': 3}]}

def custom(quotes=Q, records=R, second=None):
    session = Session([Response({'quotes': quotes, 'total': 2}), second or Response({'records': records})])
    with patch.object(s, '_session', return_value=session):
        out = s.run_custom(C, 2, 'change_pct', False, 0)
    return (out, session.calls)

class Probe(unittest.TestCase):

    def test_catalogue(self):
        x = s.cmd_fields()
        ids = [f['id'] for f in x['fields']]
        self.assertEqual(len(ids), len(set(ids)))
        print('CATALOGUE', len(ids), 'FIELDS', len(x['predefined']), 'PREDEFINED')

    def test_query(self):
        q, u = s.build_custom_query(C)
        self.assertEqual(u, ['change_pct'])
        self.assertEqual(q['operands'][1], {'operator': 'GTE', 'operands': ['percentchange', 3.0]})

    def test_invalid_filters(self):
        for v in [True, float('nan'), float('inf'), '3']:
            with self.subTest(v=v), self.assertRaises(s.ScreenerError):
                s.build_custom_query({'filters': [{'field': 'pe', 'op': 'gte', 'value': v}]})

    def test_between(self):
        q, _ = s.build_custom_query({'filters': [{'field': 'pe', 'op': 'btwn', 'value': [20, 0]}]})
        self.assertEqual(q['operands'], ['peratio.lasttwelvemonths', 0.0, 20.0])

    def test_merge_and_currency(self):
        x, c = custom()
        self.assertEqual(len(c), 2)
        self.assertEqual([r['symbol'] for r in x['rows']], ['QA-A', 'QA-B'])
        self.assertEqual(x['rows'][0]['market_cap_currency'], 'GBP')
        self.assertEqual(x['rows'][0]['financial_currency'], 'USD')
        self.assertEqual(x['rows'][0]['beta'], 0.7)
        self.assertEqual(x['rows'][0]['change_pct'], 4.5)
        self.assertEqual(x['as_of'], 1700000060)
        self.assertEqual(x['max_delay_min'], 15)
        self.assertIn('change_pct_screen', x['rows'][0]['fields'])

    def test_lookup_error_disclosed(self):
        x, _ = custom(second=Response(error={'description': 'SYNTHETIC_FAILURE'}))
        self.assertTrue(any(('unavailable for this run' in w for w in x['warnings'])))
        self.assertIsNone(x['rows'][0]['beta'])

    def test_partial_lookup_disclosed(self):
        x, _ = custom(records=R[:1])
        self.assertTrue(any(('1 of 2 rows' in w for w in x['warnings'])))
        self.assertIsNone(x['rows'][0]['beta'])

    def test_empty_quotes_no_second_call(self):
        x, c = custom(quotes=[])
        self.assertEqual(x['count'], 0)
        self.assertEqual(len(c), 1)

    def test_empty_records_disclosed(self):
        x, _ = custom(records=[])
        self.assertTrue(any(('0 of 2 rows' in w for w in x['warnings'])), 'empty records silently accepted')

    def test_unrelated_records_disclosed(self):
        x, _ = custom(records=[{'ticker': 'OTHER-A'}, {'ticker': 'OTHER-B'}])
        self.assertTrue(any(('Unexpected or duplicate fundamentals row identity' in w for w in x['warnings'])), 'unmatched records silently accepted')

    def test_duplicate_quotes_rejected(self):
        with self.assertRaises(s.ScreenerError):
            custom(quotes=[Q[0], Q[0]])

    def test_mixed_clock_not_single_provenance(self):
        q = copy.deepcopy(Q)
        q[0]['regularMarketTime'] = 1600000000
        x, _ = custom(quotes=q)
        self.assertTrue(any(('not a common market snapshot' in w for w in x['warnings'])), 'mixed timestamps not disclosed')

    def test_duplicate_records_disclosed(self):
        x, _ = custom(records=[R[0], R[0]])
        self.assertTrue(any(('duplicate' in w for w in x['warnings'])))
        self.assertTrue(all((r['beta'] is None for r in x['rows'])))

    def test_missing_clock_disclosed(self):
        q = copy.deepcopy(Q)
        del q[0]['regularMarketTime']
        x, _ = custom(quotes=q)
        self.assertTrue(any(('timestamps are missing' in w for w in x['warnings'])))

    def test_aligned_clean_output(self):
        q = copy.deepcopy(Q)
        q[0]['regularMarketTime'] = q[1]['regularMarketTime']
        x, _ = custom(quotes=q)
        self.assertEqual(x['warnings'], [])

    def test_invalid_clock_types(self):
        for value in (True, 1.5, float('nan'), float('inf'), -1, 0, 9999999999, '1700000000'):
            with self.subTest(value=value):
                q = copy.deepcopy(Q)
                q[0]['regularMarketTime'] = value
                x, _ = custom(quotes=q)
                self.assertIsNone(x['rows'][0]['market_time'])
                self.assertEqual(x['as_of'], 1700000060)
                self.assertTrue(any(('timestamps are missing' in w for w in x['warnings'])))

    def test_invalid_delay_types(self):
        for value in (True, -1, 1.5, float('inf'), '15'):
            with self.subTest(value=value):
                q = copy.deepcopy(Q)
                q[0]['exchangeDataDelayedBy'] = value
                x, _ = custom(quotes=q)
                self.assertIsNone(x['rows'][0]['delay_min'])
                self.assertEqual(x['max_delay_min'], 0)
                self.assertTrue(any(('delay coverage is incomplete' in w for w in x['warnings'])))

    def test_all_clocks_invalid(self):
        q = copy.deepcopy(Q)
        for row in q:
            row['regularMarketTime'] = False
        x, _ = custom(quotes=q)
        self.assertIsNone(x['as_of'])

    def test_malformed_quote_rows(self):
        for bad in (None, {}, [None], [{'symbol': None}], [{'symbol': 42}], [{'symbol': ' '}], 'bad'):
            with self.subTest(bad=bad), self.assertRaises(s.ScreenerError):
                custom(quotes=bad)

    def test_malformed_fundamentals(self):
        for bad in (None, {}, 'bad', [None]):
            with self.subTest(bad=bad):
                x, _ = custom(records=bad)
                self.assertTrue(any(('unavailable for this run' in w for w in x['warnings'])))
                self.assertTrue(all((r['beta'] is None for r in x['rows'])))

    def test_malformed_envelopes(self):
        for payload in (None, [], {'finance': []}, {'finance': {'result': {}}}, {'finance': {'result': [{}, {}]}}, {'finance': {'error': 'bad'}}):
            with self.subTest(payload=payload):
                resp = Response()
                resp.payload = payload
                with self.assertRaises(s.ScreenerError):
                    s._unwrap(resp, 'fixture')

    def test_predefined_second_page_preserves_request(self):
        raw = {'query': {'operator': 'GT', 'operands': ['percentchange', 3]}}
        initial = {'quotes': Q[:1], 'total': 12, 'rawCriteria': json.dumps(raw), 'criteriaMeta': {'sortField': 'percentchange', 'sortType': 'DESC', 'quoteType': 'EQUITY'}}
        session = Session([Response(initial), Response({'quotes': Q, 'total': 12}), Response({'records': R})])
        with patch.object(s, '_session', return_value=session):
            out = s.run_predefined('day_gainers', 2, 2)
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(session.calls[0][2]['params']['count'], 1)
        body = session.calls[1][2]['body']
        self.assertEqual((body['offset'], body['size'], body['query']), (2, 2, raw['query']))
        self.assertEqual((out['offset'], out['count'], out['total']), (2, 2, 12))
        self.assertEqual([row['symbol'] for row in out['rows']], ['QA-A', 'QA-B'])

    def test_fields_cli_no_session(self):
        with patch.object(s, '_session', side_effect=AssertionError('unexpected provider session')):
            out = s.main(['fields'])
        self.assertEqual(len(out['fields']), 76)
        self.assertEqual(len(out['predefined']), 22)
if __name__ == '__main__':
    unittest.main(verbosity=2)
