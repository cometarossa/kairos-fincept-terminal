"""Offline validation of OrderBook.get_execution_price quantity input checks.

Loads the ORIGINAL qlib_advanced_backtest.py directly from the source tree and
verifies that invalid order quantities (zero, negative, NaN, inf) raise
ValueError before any calculation, while valid buy/sell quantities preserve
their numeric execution results. Fully deterministic; no network, broker, or
credentials involved.
"""
import importlib.util
import math
from pathlib import Path
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "fincept-qt" / "scripts"
MODULE_PATH = SCRIPTS / "ai_quant_lab" / "qlib_advanced_backtest.py"


class OriginalQuantInvalidOrderQuantityInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "fincept_qa_original_qlib_advanced_backtest_v1", MODULE_PATH
        )
        assert spec is not None and spec.loader is not None
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def _make_book(self):
        return self.module.OrderBook(
            initial_mid_price=100.0, spread_bps=10.0, depth=1_000_000
        )

    def test_valid_buy_baseline_preserves_numeric_result(self):
        book = self._make_book()
        avg_price, total_cost = book.get_execution_price("buy", 100.0)
        # 100 shares fill entirely at best ask (depth 1,000,000 >> 100)
        self.assertEqual(avg_price, book.best_ask)
        self.assertAlmostEqual(total_cost, 100.0 * book.best_ask, places=9)
        self.assertAlmostEqual(avg_price, 100.05, places=9)
        self.assertAlmostEqual(total_cost, 10005.0, places=6)

    def test_valid_sell_baseline_preserves_numeric_result(self):
        book = self._make_book()
        avg_price, total_cost = book.get_execution_price("sell", 250.0)
        # 250 shares fill entirely at best bid
        self.assertEqual(avg_price, book.best_bid)
        self.assertAlmostEqual(total_cost, 250.0 * book.best_bid, places=9)
        self.assertAlmostEqual(avg_price, 99.95, places=9)
        self.assertAlmostEqual(total_cost, 24987.5, places=6)

    def test_valid_passive_buy_baseline_preserves_numeric_result(self):
        book = self._make_book()
        avg_price, total_cost = book.get_execution_price(
            "buy", 100.0, aggressive=False
        )
        self.assertEqual(avg_price, book.best_bid)
        self.assertAlmostEqual(total_cost, 100.0 * book.best_bid, places=9)

    def test_invalid_quantities_raise_value_error(self):
        invalid = [
            ("zero", 0.0),
            ("negative", -100.0),
            ("nan", math.nan),
            ("positive_inf", math.inf),
            ("negative_inf", -math.inf),
            ("null", None),
            ("text", "5"),
            ("boolean", True),
            ("overflow_integer", 10 ** 500),
        ]
        for side in ("buy", "sell"):
            for aggressive in (True, False):
                for label, quantity in invalid:
                    with self.subTest(side=side, aggressive=aggressive, quantity=label):
                        book = self._make_book()
                        with self.assertRaises(ValueError):
                            book.get_execution_price(
                                side, quantity, aggressive=aggressive
                            )

    def test_zero_quantity_raises_value_error_not_zero_division(self):
        book = self._make_book()
        with self.assertRaises(ValueError):
            book.get_execution_price("buy", 0)


if __name__ == "__main__":
    unittest.main()
