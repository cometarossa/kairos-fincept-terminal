"""Pinned Fincept volatility source-contract tests; NO import of Fincept dependencies.

These tests detect accidental default/schema drift in source, not numerical
parity, headless runtime safety, scientific validity, or execution authority.
They use Python stdlib only, never call Fincept modules or KAIROS.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

SOURCE = (
    Path(__file__).resolve().parents[2]
    / "fincept-qt"
    / "scripts"
    / "technicals"
    / "volatility_indicators.py"
)


class FinceptVolatilityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
        cls.functions = {
            node.name: node
            for node in cls.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def _defaults(self, function_name: str) -> dict[str, object]:
        fn = self.functions[function_name]
        names = [arg.arg for arg in fn.args.args]
        return {
            name: ast.literal_eval(value)
            for name, value in zip(names[-len(fn.args.defaults):], fn.args.defaults)
        }

    def test_six_public_entrypoints_exist(self):
        self.assertEqual(set(self.functions), {
            "calculate_atr",
            "calculate_bollinger_bands",
            "calculate_keltner_channel",
            "calculate_donchian_channel",
            "calculate_ulcer_index",
            "calculate_all_volatility_indicators",
        })

    def test_atr_default_is_explicit_window_14(self):
        defaults = self._defaults("calculate_atr")
        self.assertEqual(defaults["window"], 14)
        self.assertIs(defaults["fillna"], False)

    def test_bollinger_default_deviation_differs_from_kairos_2_5(self):
        defaults = self._defaults("calculate_bollinger_bands")
        self.assertEqual(defaults["window"], 20)
        self.assertEqual(defaults["window_dev"], 2)
        self.assertIs(defaults["fillna"], False)

    def test_keltner_and_donchian_controls_explicit(self):
        self.assertEqual(self._defaults("calculate_keltner_channel"), {
            "window": 20,
            "window_atr": 10,
            "fillna": False,
            "original_version": True,
        })
        self.assertEqual(self._defaults("calculate_donchian_channel"), {
            "window": 20,
            "offset": 0,
            "fillna": False,
        })

    def test_lowercase_ohlc_input_contract(self):
        indices = {
            node.slice.value
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "df"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        }
        self.assertTrue({"high", "low", "close"}.issubset(indices))
        self.assertFalse({"High", "Low", "Close"} & indices)

    def test_expected_technical_dependency_is_ta(self):
        imports = [
            node
            for node in self.tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        self.assertTrue(any(
            isinstance(node, ast.ImportFrom) and node.module == "ta.volatility"
            for node in imports
        ))
        self.assertTrue(any(
            isinstance(node, ast.Import)
            and any(alias.name == "pandas" for alias in node.names)
            for node in imports
        ))

    def test_no_direct_network_or_broker_imports(self):
        banned = {"requests", "urllib", "httpx", "socket", "ccxt",
                  "subprocess", "os", "yfinance"}
        imported = {
            name.split(".")[0]
            for node in self.tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for name in ([node.module] if isinstance(node, ast.ImportFrom)
                         else [alias.name for alias in node.names])
            if name is not None
        }
        self.assertFalse(imported & banned)
        # Does NOT establish that third-party dependencies have no side effects.

    def test_no_direct_mutating_trading_calls(self):
        blocked = {"place_order", "cancel_order", "execute_order",
                   "square_off", "set_leverage", "enable_live"}
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute)
            else node.func.id
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        self.assertFalse(called & blocked)

    def test_aggregate_exposes_atr_and_paired_bands(self):
        aggregate = self.functions["calculate_all_volatility_indicators"]
        fields = {
            node.slice.value
            for node in ast.walk(aggregate)
            if isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "result_df"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        }
        self.assertTrue({
            "atr", "bb_hband", "bb_lband", "bb_mavg",
            "kc_hband", "kc_lband", "dc_hband", "dc_lband", "ui",
        }.issubset(fields))

    def test_no_point_in_time_envelope_in_source_functions(self):
        # PIT/available_at/source timestamp must be provided by an adapter;
        # this is an observed absence in this module, NOT a global Fincept claim.
        for fn in self.functions.values():
            names = {arg.arg for arg in fn.args.args}
            self.assertFalse(names & {
                "as_of", "available_at", "observed_at",
                "source_id", "knowledge_time",
            })


if __name__ == "__main__":
    unittest.main()
