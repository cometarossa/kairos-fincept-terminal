"""Offline QA candidate only; never called by the capture service.

Classify the *same* row at the yfinance adjustment boundary. No I/O,
provider calls, repair, tolerance, or change to the admission predicate.
The caller must supply the actual first strict-validator failure position.
"""
import math
import unittest

UNKNOWN = "ADJUSTMENT_ORIGIN_UNVERIFIED"
PREEXISTING = "PRE_ADJUSTMENT_OHLC_ORDER"
INTRODUCED = "ADJUSTMENT_STAGE_OHLC_ORDER"


def _rows(frame):
    if type(frame) is not tuple or not 1 <= len(frame) <= 160:
        raise ValueError("coverage")
    previous = None
    for row in frame:
        if type(row) is not tuple or len(row) != 5:
            raise ValueError("row")
        ts, *prices = row
        if type(ts) is not int or (previous is not None and ts <= previous):
            raise ValueError("identity")
        if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0
               for x in prices):
            raise ValueError("price")
        previous = ts
    return frame


def _ordered(row):
    _, o, h, l, c = row
    return l <= min(o, c) and h >= max(o, c) and h >= l


def classify_order_origin(before, adjusted, returned, *, failure_position, reason):
    """Fixed labels; unknown unless all three bounded series align exactly.

    PREEXISTING means the price ordering already failed immediately before
    auto_adjust; it does not attest raw wire data. INTRODUCED identifies the
    adjustment stage, not the numerical mechanism or the size of the error.
    Both outcomes leave the original strict rejection intact.
    """
    if type(reason) is not str or reason != "OHLC_ORDER" or type(failure_position) is not int:
        return UNKNOWN
    try:
        before, adjusted, returned = map(_rows, (before, adjusted, returned))
        if (len(before) != len(adjusted) or adjusted != returned
                or tuple(r[0] for r in before) != tuple(r[0] for r in adjusted)
                or not 0 <= failure_position < len(returned)
                or any(not _ordered(r) for r in returned[:failure_position])
                or _ordered(returned[failure_position])):
            return UNKNOWN
        return INTRODUCED if _ordered(before[failure_position]) else PREEXISTING
    except (ValueError, TypeError, OverflowError):
        return UNKNOWN


class AdjustmentOriginCandidateTests(unittest.TestCase):
    def setUp(self):
        self.good = (1, 1.0, 1.0, 0.9, 1.0)
        self.bad = (1, 1.0, 1.0, 0.9, math.nextafter(1.0, 2.0))
        self.material = (1, 1.0, 1.0, 0.9, 1.1)

    def label(self, before, adjusted, returned=None, **kw):
        return classify_order_origin(before, adjusted,
            adjusted if returned is None else returned,
            failure_position=kw.get("pos", 0), reason=kw.get("reason", "OHLC_ORDER"))

    def test_adjustment_boundary(self):
        self.assertEqual(self.label((self.good,), (self.bad,)), INTRODUCED)

    def test_preexisting(self):
        self.assertEqual(self.label((self.material,), (self.material,)), PREEXISTING)

    def test_material_new_error_is_not_claimed_to_be_rounding(self):
        self.assertEqual(self.label((self.good,), (self.material,)), INTRODUCED)

    def test_unmatched_rows_or_postprocessing(self):
        for before, adjusted, returned in (
            ((self.good,), ((2, *self.bad[1:]),), None),
            ((self.good,), (self.bad,), (self.material,)),
            ((self.good,), (self.bad,), ()),
            ((self.good, self.good), (self.bad, self.bad), None),
        ):
            with self.subTest(before=before):
                self.assertEqual(self.label(before, adjusted, returned), UNKNOWN)

    def test_no_order_failure_or_invalid_position(self):
        for pos, reason, adjusted in (
            (0, "OHLC_ORDER", (self.good,)),
            (0, "NONFINITE", (self.bad,)),
            (-1, "OHLC_ORDER", (self.bad,)),
            (True, "OHLC_ORDER", (self.bad,)),
        ):
            self.assertEqual(self.label((self.good,), adjusted, pos=pos, reason=reason), UNKNOWN)

    def test_earlier_order_violation_cannot_be_misattributed(self):
        before = (self.good, (2, *self.good[1:]))
        after = (self.bad, (2, *self.bad[1:]))
        self.assertEqual(self.label(before, after, pos=1), UNKNOWN)

    def test_nonfinite_and_nonpositive_fail_closed(self):
        for value in (float("nan"), float("inf"), 0, -1, True, "private"):
            before = ((1, value, 1.0, 0.9, 1.0),)
            self.assertEqual(self.label(before, (self.bad,)), UNKNOWN)

    def test_bounded_input(self):
        before = tuple((n, *self.good[1:]) for n in range(161))
        after = tuple((n, *self.bad[1:]) for n in range(161))
        self.assertEqual(self.label(before, after), UNKNOWN)

    def test_nonstring_reason_never_compared(self):
        class Pretender:
            def __ne__(self, other):
                raise AssertionError("untrusted equality invoked")
        class StringSubclass(str):
            pass
        for reason in (None, True, 1, Pretender(), StringSubclass("OHLC_ORDER")):
            with self.subTest(kind=type(reason).__name__):
                self.assertEqual(self.label((self.good,), (self.bad,), reason=reason), UNKNOWN)

    def test_only_fixed_labels_no_values(self):
        self.assertEqual(self.label((self.good,), (self.bad,), reason="private provider text"), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
