"""Exercise the original public JSON boundary without GUI or providers."""
from contextlib import redirect_stdout
from decimal import Decimal
import importlib.util
import io
import json
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[2] / 'fincept-qt/scripts/fincept_json.py'
spec = importlib.util.spec_from_file_location('fincept_json_under_test', PATH)
boundary = importlib.util.module_from_spec(spec)
exec(compile(PATH.read_bytes(), str(PATH), 'exec'), boundary.__dict__)


def strict_load(text):
    def reject(value):
        raise AssertionError('nonstandard JSON constant: ' + value)
    return json.loads(text, parse_constant=reject)


class JsonNumericBoundaryTests(unittest.TestCase):
    def test_finite_decimal_float_overflow_becomes_null(self):
        for value in [Decimal('1e10000'), Decimal('-1e10000')]:
            with self.subTest(value=str(value)):
                self.assertIsNone(boundary.sanitize(value))
                self.assertEqual(strict_load(boundary.dumps({'value': value, 'other': 12})),
                                 {'value': None, 'other': 12})

    def test_normal_decimals_preserve_existing_numeric_conversion(self):
        for value in ['0', '-0', '1.25', '-17.5', '1e300', '1e-10000']:
            with self.subTest(value=value):
                self.assertEqual(strict_load(boundary.dumps(Decimal(value))), float(Decimal(value)))

    def test_nonfinite_decimals_and_floats_become_null(self):
        values = [Decimal('NaN'), Decimal('sNaN'), Decimal('Infinity'),
                  Decimal('-Infinity'), float('nan'), float('inf'), -float('inf')]
        self.assertEqual(strict_load(boundary.dumps(values)), [None] * len(values))

    def test_nested_payload_survives_without_mutating_input(self):
        number = Decimal('1e10000')
        source = {'rows': [{'value': number}, {'value': Decimal('2.5')}], 'label': 'risk'}
        result = strict_load(boundary.dumps(source))
        self.assertEqual(result, {'rows': [{'value': None}, {'value': 2.5}], 'label': 'risk'})
        self.assertIs(source['rows'][0]['value'], number)
        self.assertIsInstance(source['rows'][1]['value'], Decimal)

    def test_emit_is_one_line_and_bytes_are_utf8(self):
        payload = {'label': 'rischio — qualità', 'value': Decimal('1e10000')}
        output = io.StringIO()
        with redirect_stdout(output):
            returned = boundary.emit(payload)
        self.assertEqual(output.getvalue(), returned + '\n')
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(strict_load(boundary.dumps_bytes(payload).decode('utf-8')),
                         {'label': 'rischio — qualità', 'value': None})

    def test_allow_nan_cannot_disable_strict_boundary(self):
        self.assertEqual(strict_load(boundary.dumps([float('nan'), Decimal('1e10000')], allow_nan=True)),
                         [None, None])

    def test_standard_scalars_are_preserved(self):
        payload = {'a': True, 'b': False, 'c': None, 'd': 123, 'e': 'text', 'f': 1.5}
        self.assertEqual(strict_load(boundary.dumps(payload)), payload)

    def test_optional_numpy_pandas_are_not_required_for_decimal_boundary(self):
        from unittest.mock import patch
        with patch.object(boundary, '_np', None), patch.object(boundary, '_pd', None):
            self.assertEqual(strict_load(boundary.dumps([Decimal('1e10000'), Decimal('1.5')])), [None, 1.5])

    def test_numpy_arrays_keep_nonfinite_null_and_finite_values(self):
        import numpy as np
        payload = {'values': np.array([1.25, np.nan, np.inf]), 'count': np.int64(3)}
        self.assertEqual(strict_load(boundary.dumps(payload)), {'values': [1.25, None, None], 'count': 3})

    def test_pandas_missing_values_and_decimal_column_survive(self):
        import pandas as pd
        frame = pd.DataFrame({'value': [Decimal('1e10000'), Decimal('1.25')],
                              'missing': [pd.NA, pd.NaT]})
        self.assertEqual(strict_load(boundary.dumps(frame)),
                         [{'value': None, 'missing': None}, {'value': 1.25, 'missing': None}])


if __name__ == '__main__':
    unittest.main()
