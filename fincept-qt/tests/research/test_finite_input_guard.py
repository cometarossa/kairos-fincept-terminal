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

    @staticmethod
    def validate(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("indicator input must be a finite real number")
        try:
            finite = math.isfinite(value)
        except (ValueError, TypeError, OverflowError):
            finite = False
        if not finite:
            raise ValueError("indicator input must be finite")
    def update(self, value):
        self.validate(value)
        return self.indicator.update(value)

class FiniteOutputBoundary:
    """Research-only result gate: never expose nonfinite values to a consumer.

    This is a read-only output boundary, NOT a transactional indicator update.
    The original engine may already have advanced its internal state.
    """
    def __init__(self, indicator):
        self.indicator = FiniteInputGuard(indicator)
        self.invalidated = False
        self.failure_code = None

    def update(self, value):
        if self.invalidated:
            raise RuntimeError("indicator instance invalidated; create a fresh instance")
        # Input denial is pre-mutation; it must not poison a healthy instance.
        try:
            FiniteInputGuard.validate(value)
        except ValueError:
            self.failure_code = "INPUT_REJECTED"
            raise
        self.failure_code = None
        try:
            self.indicator.update(value)
        except Exception:
            # Original update may have mutated state before raising.
            self.invalidated = True
            self.failure_code = "ENGINE_UPDATE_FAILED"
            raise
        try:
            result = self.indicator.indicator.current.value
        except Exception:
            # The original update already ran; quarantine a broken accessor.
            self.invalidated = True
            self.failure_code = "RESULT_ACCESS_FAILED"
            raise
        if isinstance(result, bool) or not isinstance(result, (int, float)):
            self.invalidated = True
            self.failure_code = "OUTPUT_INVALID"
            raise ValueError("indicator output is not a finite numeric result")
        try:
            valid = math.isfinite(result)
        except (ValueError, TypeError, OverflowError):
            valid = False
        if not valid:
            self.invalidated = True
            self.failure_code = "OUTPUT_NONFINITE"
            raise ValueError("indicator output is nonfinite; consumer must abstain")
        return result

class GuardTests(unittest.TestCase):
    def test_boundary_failure_codes_are_distinct_and_fail_closed(self):
        healthy = FiniteOutputBoundary(mod.SimpleMovingAverage(period=3))
        with self.assertRaises(ValueError):
            healthy.update(float("nan"))
        self.assertEqual(healthy.failure_code, "INPUT_REJECTED")
        self.assertFalse(healthy.invalidated)
        self.assertEqual(healthy.update(12), 12)
        self.assertIsNone(healthy.failure_code)

        class BrokenEngine:
            def update(self, value):
                raise ArithmeticError("synthetic engine failure")
        failed = FiniteOutputBoundary(BrokenEngine())
        with self.assertRaises(ArithmeticError):
            failed.update(1)
        self.assertEqual(failed.failure_code, "ENGINE_UPDATE_FAILED")
        self.assertTrue(failed.invalidated)
        with self.assertRaises(RuntimeError):
            failed.update(2)
        self.assertEqual(failed.failure_code, "ENGINE_UPDATE_FAILED")

        overflow = FiniteOutputBoundary(mod.SimpleMovingAverage(period=3))
        overflow.update(1e308)
        with self.assertRaises(ValueError):
            overflow.update(1e308)
        self.assertEqual(overflow.failure_code, "OUTPUT_NONFINITE")
        self.assertTrue(overflow.invalidated)

    def test_boolean_output_is_rejected_and_instance_quarantined(self):
        # bool is a Python int subclass, but never a valid financial indicator result.
        class BooleanOutputIndicator:
            def __init__(self):
                self.calls = 0
                self.current = type("Current", (), {"value": True})()
            def update(self, value):
                self.calls += 1

        original = BooleanOutputIndicator()
        boundary = FiniteOutputBoundary(original)
        with self.assertRaisesRegex(ValueError, "not a finite numeric result"):
            boundary.update(12)
        self.assertEqual(boundary.failure_code, "OUTPUT_INVALID")
        self.assertTrue(boundary.invalidated)
        with self.assertRaisesRegex(RuntimeError, "instance invalidated"):
            boundary.update(13)
        self.assertEqual(original.calls, 1)
        self.assertEqual(boundary.failure_code, "OUTPUT_INVALID")

    def test_denied_input_never_invokes_original_engine(self):
        # Boundary denial must precede every original update() call.
        class SpyIndicator:
            def __init__(self):
                self.calls = []
            def update(self, value):
                self.calls.append(value)
                return "original-result"
        spy = SpyIndicator()
        guarded = FiniteInputGuard(spy)
        for invalid in (None, True, "12", float("nan"), float("inf"), 10**1000):
            with self.subTest(invalid=repr(invalid)[:40]):
                with self.assertRaises(ValueError):
                    guarded.update(invalid)
                self.assertEqual(spy.calls, [])
        self.assertEqual(guarded.update(12), "original-result")
        self.assertEqual(spy.calls, [12])

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

    def test_huge_integer_overflow_rejected_without_state_mutation(self):
        # math.isfinite() raises OverflowError for integers too large for float.
        # The boundary must fail closed without advancing the original engine.
        huge = 10 ** 1000
        for factory in (mod.SimpleMovingAverage, mod.ExponentialMovingAverage, mod.RelativeStrengthIndex):
            with self.subTest(indicator=factory.__name__):
                guarded = FiniteInputGuard(factory(period=3))
                baseline = factory(period=3)
                for value in (10, 12, 11, 15):
                    guarded.update(value)
                    baseline.update(value)
                with self.assertRaises(ValueError):
                    guarded.update(huge)
                self.assertEqual(guarded.indicator.samples, baseline.samples)
                guarded.update(17)
                baseline.update(17)
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

    def test_invalid_input_does_not_invalidate_healthy_output_boundary(self):
        original = mod.SimpleMovingAverage(period=3)
        boundary = FiniteOutputBoundary(original)
        self.assertEqual(boundary.update(10), 10)
        samples = original.samples
        for bad in (True, None, float("nan"), 10**1000):
            with self.subTest(bad=repr(bad)[:30]):
                with self.assertRaises(ValueError):
                    boundary.update(bad)
                self.assertFalse(boundary.invalidated)
                self.assertEqual(original.samples, samples)
        self.assertEqual(boundary.update(20), 15)
        self.assertEqual(original.samples, samples + 1)

    def test_output_boundary_denies_overflow_and_preserves_valid_result(self):
        baseline = mod.SimpleMovingAverage(period=3)
        boundary = FiniteOutputBoundary(mod.SimpleMovingAverage(period=3))
        for value in (10, 20, 30):
            baseline.update(value)
            self.assertEqual(boundary.update(value), baseline.current.value)
        overflowing = FiniteOutputBoundary(mod.SimpleMovingAverage(period=3))
        overflowing.update(1e308)
        with self.assertRaisesRegex(ValueError, "consumer must abstain"):
            overflowing.update(1e308)
        # The original engine has advanced: do not claim rollback/atomicity.
        self.assertTrue(math.isinf(overflowing.indicator.indicator.current.value))

    def test_nonfinite_output_invalidates_instance_and_denies_reuse(self):
        boundary = FiniteOutputBoundary(mod.SimpleMovingAverage(period=3))
        boundary.update(1e308)
        with self.assertRaisesRegex(ValueError, "consumer must abstain"):
            boundary.update(1e308)
        self.assertTrue(boundary.invalidated)
        samples = boundary.indicator.indicator.samples
        with self.assertRaisesRegex(RuntimeError, "instance invalidated"):
            boundary.update(10)
        self.assertEqual(boundary.indicator.indicator.samples, samples)
        # A fresh original instance can still be used independently.
        fresh = FiniteOutputBoundary(mod.SimpleMovingAverage(period=3))
        self.assertEqual(fresh.update(10), 10)

    def test_original_update_exception_invalidates_boundary_and_denies_reuse(self):
        # Synthetic fault injection: an original engine can mutate before raising.
        class MutatingThenRaisingIndicator:
            def __init__(self):
                self.samples = 0
                self.current = type("Current", (), {"value": 0})()
            def update(self, value):
                self.samples += 1
                raise ArithmeticError("synthetic engine failure after mutation")

        original = MutatingThenRaisingIndicator()
        boundary = FiniteOutputBoundary(original)
        with self.assertRaisesRegex(ArithmeticError, "synthetic engine failure"):
            boundary.update(10)
        self.assertTrue(boundary.invalidated)
        self.assertEqual(original.samples, 1)
        with self.assertRaisesRegex(RuntimeError, "instance invalidated"):
            boundary.update(20)
        self.assertEqual(original.samples, 1)
        # No rollback or scientific PASS is claimed for the mutated engine.
    def test_result_accessor_failure_invalidates_instance(self):
        class BrokenCurrent:
            @property
            def value(self):
                raise RuntimeError("synthetic accessor failure")

        class SpyIndicator:
            def __init__(self):
                self.calls = 0
                self.current = BrokenCurrent()
            def update(self, value):
                self.calls += 1

        spy = SpyIndicator()
        boundary = FiniteOutputBoundary(spy)
        with self.assertRaisesRegex(RuntimeError, "synthetic accessor failure"):
            boundary.update(10)
        self.assertTrue(boundary.invalidated)
        with self.assertRaisesRegex(RuntimeError, "instance invalidated"):
            boundary.update(20)
        self.assertEqual(spy.calls, 1)

    def test_non_numeric_output_invalidates_and_denies_reuse(self):
        # Synthetic contract fault: no non-numeric payload may escape to KAIROS.
        class NonNumericIndicator:
            def __init__(self):
                self.calls = 0
                self.current = type("Current", (), {"value": "not-a-number"})()
            def update(self, value):
                self.calls += 1

        original = NonNumericIndicator()
        boundary = FiniteOutputBoundary(original)
        with self.assertRaisesRegex(ValueError, "not a finite numeric result"):
            boundary.update(10)
        self.assertTrue(boundary.invalidated)
        with self.assertRaisesRegex(RuntimeError, "instance invalidated"):
            boundary.update(11)
        self.assertEqual(original.calls, 1)

    def test_finite_inputs_can_overflow_original_sma_output(self):
        # Known limitation / reproduced defect, NOT a safety PASS:
        # input validation alone cannot guarantee finite derived outputs.
        guarded = FiniteInputGuard(mod.SimpleMovingAverage(period=3))
        for value in (1e308, 1e308, 1e308):
            self.assertTrue(math.isfinite(value))
            guarded.update(value)
        self.assertTrue(math.isinf(guarded.indicator.current.value))

if __name__ == "__main__":
    unittest.main(verbosity=2)
