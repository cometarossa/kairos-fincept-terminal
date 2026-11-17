"""Research-only finite numeric guard for original Fincept indicators; no broker."""
import hashlib
import importlib.util
import math
from pathlib import Path
import unittest

# Explicit source selection prevents accidental use of an installed Fincept profile
# or a stale /tmp checkout. Run with FINCEPT_INDICATORS_SOURCE set to an
# isolated, pinned original source file; this harness never modifies it.
# Source is resolved relative to this test in the isolated repository checkout.
# The original engine remains untouched. Exact blob pin prevents silent drift.
SOURCE = Path(__file__).resolve().parents[2] / "scripts/strategies/fincept_engine/indicators.py"
if not SOURCE.is_file():
    raise RuntimeError("Original Fincept indicator source NOT_VERIFIED")
EXPECTED_BLOB_SHA1 = "f60c27876f218f7537e203afe5a8250916a2544d"
source_bytes = SOURCE.read_bytes()
blob = b"blob " + str(len(source_bytes)).encode("ascii") + b"\0" + source_bytes
if hashlib.sha1(blob).hexdigest() != EXPECTED_BLOB_SHA1:
    raise RuntimeError("FINCEPT_INDICATORS_SOURCE blob SHA mismatch; source NOT_VERIFIED")
spec = importlib.util.spec_from_file_location("fincept_original_guard_run29", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FiniteInputGuard:
    """Opt-in boundary; rejects bad data before mutating original indicator state."""
    def __init__(self, indicator):
        self.indicator = indicator

    def update(self, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("indicator input must be a finite real number")
        try:
            finite = math.isfinite(value)
        except (ValueError, TypeError, OverflowError):
            finite = False
        if not finite:
            raise ValueError("indicator input must be finite")
        return self.indicator.update(value)

class GuardTests(unittest.TestCase):
    def test_original_sma_numeric_unchanged(self):
        original = mod.SimpleMovingAverage(period=3)
        guarded = FiniteInputGuard(mod.SimpleMovingAverage(period=3))
        for v in (10, 20, 30):
            original.update(v)
            guarded.update(v)
        self.assertEqual(guarded.indicator.current.value, original.current.value)

    def test_rejected_inputs_do_not_mutate_sma_ema_rsi(self):
        for factory in (mod.SimpleMovingAverage, mod.ExponentialMovingAverage, mod.RelativeStrengthIndex):
            for bad in (object(), None, True, "12", float("nan"), float("inf"), -float("inf"), [], {}):
                with self.subTest(factory=factory.__name__, bad=repr(bad)):
                    x = FiniteInputGuard(factory(period=3))
                    x.update(10)
                    samples_before = x.indicator.samples
                    value_before = x.indicator.current.value
                    with self.assertRaises(ValueError):
                        x.update(bad)
                    self.assertEqual(x.indicator.samples, samples_before)
                    self.assertEqual(x.indicator.current.value, value_before)

    def test_recovery_after_rejected_value(self):
        x = FiniteInputGuard(mod.SimpleMovingAverage(period=3))
        x.update(10)
        with self.assertRaises(ValueError):
            x.update(float("nan"))
        x.update(20)
        self.assertEqual(x.indicator.samples, 2)
        self.assertEqual(x.indicator.current.value, 15)

    def test_rejection_after_warmup_preserves_future_outputs(self):
        # Exercise the fully initialized state, not only the warm-up path.
        for factory in (mod.SimpleMovingAverage, mod.ExponentialMovingAverage, mod.RelativeStrengthIndex):
            with self.subTest(indicator=factory.__name__):
                baseline = factory(period=3)
                guarded = FiniteInputGuard(factory(period=3))
                for value in (10, 12, 11, 15, 13):
                    baseline.update(value)
                    guarded.update(value)
                for bad in (float("nan"), float("inf"), "invalid", False):
                    with self.assertRaises(ValueError):
                        guarded.update(bad)
                for value in (17, 16, 20, 18):
                    baseline.update(value)
                    guarded.update(value)
                    self.assertEqual(guarded.indicator.samples, baseline.samples)
                    self.assertEqual(guarded.indicator.current.value, baseline.current.value)

    def test_ema_rsi_recovery_matches_uninterrupted_original(self):
        # A rejected observation must not change any future indicator output.
        for factory in (mod.ExponentialMovingAverage, mod.RelativeStrengthIndex):
            with self.subTest(indicator=factory.__name__):
                baseline = factory(period=3)
                guarded = FiniteInputGuard(factory(period=3))
                for value in (10, 12, 11, 15, 13, 17, 16):
                    baseline.update(value)
                    guarded.update(value)
                    with self.assertRaises(ValueError):
                        guarded.update(float("nan"))
                    self.assertEqual(guarded.indicator.samples, baseline.samples)
                    self.assertEqual(guarded.indicator.current.value, baseline.current.value)

if __name__ == "__main__":
    unittest.main(verbosity=2)
