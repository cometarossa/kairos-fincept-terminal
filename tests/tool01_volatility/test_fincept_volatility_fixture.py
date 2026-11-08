"""TOOL-01 tests: run with existing Fincept numpy2 Python (pandas+ta)."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "research/tool01_volatility/fincept_volatility_fixture.py"
spec = importlib.util.spec_from_file_location("fixture_adapter", MODULE)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Source is supplied explicitly via env-free positional CLI argument.
        import sys
        cls.source = Path(sys.argv[-1]) if sys.argv[-1].endswith("volatility_indicators.py") else None

    def test_requires_exact_module_name(self):
        with self.assertRaises((ValueError, FileNotFoundError)):
            adapter.run(MODULE)

    def test_no_source_available_fails_closed(self):
        with self.assertRaises(FileNotFoundError):
            adapter.run(Path("/nonexistent/volatility_indicators.py"))

    def test_real_fincept_function_and_provenance(self):
        if self.source is None:
            self.skipTest("pass source path as last argument through runner")
        a = adapter.run(self.source)
        b = adapter.run(self.source)
        self.assertEqual(a, b)
        self.assertEqual(a["dataset_class"], "SYNTHETIC_FIXTURE")
        self.assertEqual(a["scientific_status"], "NOT_EVALUATED")
        self.assertIs(a["broker_authority"], False)
        self.assertEqual(a["bar_count"], 120)
        self.assertEqual(len(a["input_sha256"]), 64)
        self.assertEqual(a["cost"]["external_api_calls"], 0)
        for v in a["result"].values():
            self.assertTrue(math.isfinite(v))


if __name__ == "__main__":
    import sys
    # unittest receives only its own args; source file is the last CLI argument.
    source = sys.argv.pop(-1) if sys.argv[-1].endswith("volatility_indicators.py") else ""
    # override path without globals/hidden credentials
    FixtureTests.setUpClass = classmethod(lambda cls: setattr(cls, "source", Path(source) if source else None))
    unittest.main()
