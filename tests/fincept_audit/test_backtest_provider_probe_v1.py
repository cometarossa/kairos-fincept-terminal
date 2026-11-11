"""The ORIGINAL Fincept VectorBT provider, run offline, against the exact oracle.

Needs numpy and pandas for the provider's child interpreter (Fincept's own
requirements). Not a Qt test. No original Fincept file is modified.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.fincept_audit import backtest_oracle_v1 as oracle
from tools.fincept_audit import backtest_provider_probe_v1 as probe

ROOT = Path(__file__).resolve().parents[2]
BACKTESTING = ROOT / probe.BACKTESTING_RELATIVE
HAVE_PROVIDER_DEPS = all(importlib.util.find_spec(name) for name in ("numpy", "pandas"))
COSTS = {"name": "costs", "fast": 5, "slow": 20, "commission": "0.001", "slippage": "0.0005"}


def expected_for(scenario):
    return oracle.simulate(
        oracle.synthetic_candles(scenario.get("bars", 160)),
        fast=scenario["fast"], slow=scenario["slow"],
        commission=scenario.get("commission", "0"), slippage=scenario.get("slippage", "0"),
        sizing_mode=scenario.get("sizing_mode", "percent"),
        sizing_value=scenario.get("sizing_value", "100"),
        execution=scenario.get("execution", "next_open"),
        **{name: scenario.get(name) for name in probe.STOP_KEYS})


@unittest.skipUnless(HAVE_PROVIDER_DEPS, "original provider needs numpy and pandas")
class OriginalProviderAgainstOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = probe.run_all(BACKTESTING)
        candles = oracle.synthetic_candles(160)
        cls.costs_run = probe.run_original_provider(BACKTESTING, probe.build_request(candles, COSTS))

    def test_every_scenario_matches_the_exact_oracle(self):
        result = self.result
        self.assertEqual(result["schema"], "kairos_fincept_backtest_provider_probe_v1")
        self.assertEqual(result["scenario_count"], 14)
        names = [s["scenario"] for s in result["scenarios"]]
        self.assertEqual(names, [s["name"] for s in probe.default_scenarios() + probe.stop_scenarios()])
        self.assertEqual(len(set(names)), 14)
        for scenario in result["scenarios"]:
            with self.subTest(scenario=scenario["scenario"]):
                self.assertEqual(scenario["status"], "ORIGINAL_PROVIDER_MATCHES_EXACT_ORACLE")
                self.assertGreaterEqual(scenario["trades"], 3)
                self.assertEqual(scenario["network_attempts_denied"], 0)

    def test_grid_covers_costs_sizing_execution_and_forced_final_exit(self):
        by_name = {s["scenario"]: s for s in self.result["scenarios"]}
        self.assertEqual(by_name["next_open_no_costs"]["oracle_total_fees"], 0.0)
        self.assertGreater(by_name["next_open_costs"]["oracle_total_fees"], 0.0)
        # Same signals, different fills or size: the totals must really differ.
        returns = {by_name[n]["oracle_total_return"] for n in (
            "next_open_no_costs", "next_open_costs", "next_open_costs_40pct", "same_close_costs")}
        self.assertEqual(len(returns), 4)
        self.assertEqual(by_name["open_position_at_end"]["exit_reasons"], ["end_of_data", "signal"])

    def test_stops_fire_before_the_signal_and_change_the_outcome(self):
        by_name = {s["scenario"]: s for s in self.result["scenarios"]}
        # 3% stop-loss leaves four bars before the crossover exit (bar 58).
        self.assertEqual(by_name["stop_loss_after_shock"]["exit_bars"], [24, 54, 81, 137])
        self.assertEqual(by_name["stop_loss_after_shock_same_close"]["exit_bars"], [23, 53, 80, 136])
        self.assertEqual(by_name["take_profit"]["exit_bars"], [24, 56, 113])
        self.assertEqual(by_name["trailing_stop"]["exit_bars"], [24, 78, 135])
        self.assertEqual(by_name["trailing_stop"]["exit_reasons"], ["trailing_stop"])
        self.assertEqual(by_name["all_three_after_shock"]["exit_reasons"],
                         ["signal", "stop_loss", "take_profit"])
        # A stop on the same bar as the signal changes only the reported reason.
        tie, plain = by_name["stop_loss_ties_with_signal"], by_name["next_open_costs"]
        self.assertEqual(tie["exit_bars"], plain["exit_bars"])
        self.assertEqual(tie["oracle_total_return"], plain["oracle_total_return"])
        self.assertEqual(tie["exit_reasons"], ["signal", "stop_loss"])
        self.assertNotEqual(by_name["take_profit"]["oracle_total_return"],
                            plain["oracle_total_return"])

    def test_comparison_detects_a_missing_or_wrong_stop(self):
        scenario = next(s for s in probe.stop_scenarios() if s["name"] == "stop_loss_after_shock")
        run = probe.run_original_provider(
            BACKTESTING, probe.build_request(probe.fixture_for(scenario), scenario))
        candles = probe.fixture_for(scenario)
        base = dict(fast=5, slow=20, commission="0.001", slippage="0.0005")
        probe.compare(run["response"], oracle.simulate(candles, stop_loss="0.03", **base))
        for wrong in ({}, {"stop_loss": "0.08"}, {"trailing_stop": "0.03"},
                      {"stop_loss": "0.03", "execution": "same_close"}):
            with self.subTest(wrong=wrong):
                with self.assertRaises(probe.ProbeError):
                    probe.compare(run["response"], oracle.simulate(candles, **base, **wrong))

    def test_result_carries_the_probe_labels_not_the_provider_ones(self):
        result = self.result
        self.assertEqual(result["source_kind"], "SYNTHETIC_FIXTURE_NOT_MARKET_DATA")
        self.assertEqual(result["scientific_status"], "NOT_EVALUATED")
        self.assertIs(result["broker_authority"], False)
        self.assertIs(result["promotion_eligible"], False)
        self.assertEqual(result["pinned_original_sources"], sorted(probe.PINNED_SOURCES))

    def test_provider_reports_injected_synthetic_candles_as_broker_data(self):
        # Characterisation of ORIGINAL behaviour, not an endorsement: candles
        # passed through `brokerCandles` are reported as real broker data, so a
        # caller must never rely on `usingSyntheticData` to tell fixtures apart.
        for scenario in self.result["scenarios"]:
            with self.subTest(scenario=scenario["scenario"]):
                self.assertIs(scenario["provider_using_synthetic_data"], False)
                self.assertEqual(scenario["provider_data_source"], probe.DATA_SOURCE_TAG)

    def test_provider_reports_zero_total_slippage_although_slippage_was_applied(self):
        # Characterisation: fills include slippage (the equity matches the oracle
        # only with it), yet statistics.totalSlippage stays 0.
        by_name = {s["scenario"]: s for s in self.result["scenarios"]}
        self.assertEqual(by_name["next_open_costs"]["provider_total_slippage"], 0)

    def test_only_pinned_repository_modules_were_imported(self):
        self.assertEqual(sorted(self.costs_run["loaded"]), sorted(probe.PINNED_SOURCES))
        self.assertEqual(self.costs_run["network_attempts"], 0)

    def test_comparison_detects_a_wrong_commission(self):
        wrong = dict(COSTS, commission="0.0011")
        with self.assertRaises(probe.ProbeError) as raised:
            probe.compare(self.costs_run["response"], expected_for(wrong))
        self.assertTrue(str(raised.exception).startswith("ORACLE_MISMATCH:equity["))

    def test_comparison_detects_a_wrong_execution_model_and_sizing(self):
        for change in ({"execution": "same_close"}, {"sizing_value": "99.9"}, {"slippage": "0"}):
            with self.subTest(change=change):
                with self.assertRaises(probe.ProbeError):
                    probe.compare(self.costs_run["response"], expected_for(dict(COSTS, **change)))

    def test_comparison_detects_tampered_provider_output(self):
        expected = expected_for(COSTS)
        mutations = {
            "equity point": lambda d: d["equity"][80].__setitem__("equity", d["equity"][80]["equity"] * 1.000001),
            "dropped trade": lambda d: d["trades"].pop(),
            "trade pnl": lambda d: d["trades"][0].__setitem__("pnl", d["trades"][0]["pnl"] + 0.01),
            "exit reason": lambda d: d["trades"][0].__setitem__("exitReason", "stop_loss"),
            "entry date": lambda d: d["trades"][0].__setitem__("entryDate", "2024-01-01"),
            "total fees": lambda d: d["statistics"].__setitem__("totalFees", 0.0),
            "nan equity": lambda d: d["equity"][5].__setitem__("equity", float("nan")),
            "bool equity": lambda d: d["equity"][5].__setitem__("equity", True),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                response = copy.deepcopy(self.costs_run["response"])
                mutate(response["data"])
                with self.assertRaises(probe.ProbeError):
                    probe.compare(response, expected)
        # The untouched response still passes, so the mutations are what failed.
        probe.compare(copy.deepcopy(self.costs_run["response"]), expected)


class PinnedSourceTests(unittest.TestCase):
    def copy_tree(self, directory):
        target = Path(directory) / "backtesting"
        for relative in probe.PINNED_SOURCES:
            (target / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(BACKTESTING / relative, target / relative)
        return target

    def test_every_pinned_original_is_present_and_unchanged(self):
        probe._verify_sources(BACKTESTING)
        self.assertEqual(len(probe.PINNED_SOURCES), 9)

    def test_changed_missing_or_symlinked_original_is_refused_before_running(self):
        request = probe.build_request(oracle.synthetic_candles(160), COSTS)
        for relative in ("vectorbt/vbt_portfolio.py", "base/base_provider.py"):
            with self.subTest(changed=relative), TemporaryDirectory() as directory:
                target = self.copy_tree(directory)
                with (target / relative).open("ab") as handle:
                    handle.write(b"\n# drift\n")
                with self.assertRaises(probe.ProbeError) as raised:
                    probe.run_original_provider(target, request)
                self.assertEqual(str(raised.exception), "CHANGED_ORIGINAL_SOURCE_SHA256:" + relative)
        with TemporaryDirectory() as directory:
            target = self.copy_tree(directory)
            (target / "vectorbt/vbt_metrics.py").unlink()
            with self.assertRaises(probe.ProbeError) as raised:
                probe.run_original_provider(target, request)
            self.assertEqual(str(raised.exception),
                             "MISSING_OR_INVALID_PINNED_ORIGINAL:vectorbt/vbt_metrics.py")
        with TemporaryDirectory() as directory:
            target = self.copy_tree(directory)
            victim = target / "vectorbt/vbt_indicators.py"
            victim.unlink()
            victim.symlink_to(BACKTESTING / "vectorbt/vbt_indicators.py")
            with self.assertRaises(probe.ProbeError) as raised:
                probe.run_original_provider(target, request)
            self.assertEqual(str(raised.exception),
                             "MISSING_OR_INVALID_PINNED_ORIGINAL:vectorbt/vbt_indicators.py")

    def test_fixture_drift_is_refused(self):
        for key, scenario in (("160", COSTS), ("160/shock53x500", probe.stop_scenarios()[0])):
            original = probe.FIXTURE_SHA256[key]
            probe.FIXTURE_SHA256[key] = "0" * 64
            try:
                with self.subTest(key=key), self.assertRaises(probe.ProbeError) as raised:
                    probe.run_scenario(BACKTESTING, scenario)
                self.assertEqual(str(raised.exception), "SYNTHETIC_FIXTURE_DRIFT:" + key)
            finally:
                probe.FIXTURE_SHA256[key] = original
        self.assertEqual(sorted(probe.FIXTURE_SHA256), ["130", "160", "160/shock53x500"])


class ChildIsolationTests(unittest.TestCase):
    """The child wrapper itself, with stand-in provider scripts (stdlib only)."""

    def run_script(self, body, extra=None):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            script = root / "pkg" / "provider.py"
            script.write_text(body, encoding="utf-8")
            for name, text in (extra or {}).items():
                (root / "pkg" / name).write_text(text, encoding="utf-8")
            return probe.execute_child(script, root, {"hello": "world"})

    def test_network_attempts_are_denied_and_counted(self):
        stdout, report = self.run_script(
            "import json, socket, sys, urllib.request\n"
            "denied = 0\n"
            "for attempt in (lambda: socket.create_connection(('192.0.2.1', 80), 1),\n"
            "                lambda: socket.socket().connect(('192.0.2.1', 80)),\n"
            "                lambda: socket.socket().connect_ex(('192.0.2.1', 80)),\n"
            "                lambda: urllib.request.urlopen('http://192.0.2.1/', timeout=1)):\n"
            "    try:\n        attempt()\n    except OSError:\n        denied += 1\n"
            "print(json.dumps({'denied': denied, 'stdin': json.load(sys.stdin)}))\n")
        self.assertEqual(json.loads(stdout), {"denied": 4, "stdin": {"hello": "world"}})
        self.assertGreaterEqual(report["network_attempts"], 4)

    def test_child_reports_every_repository_module_it_imported(self):
        stdout, report = self.run_script(
            "import os, sys\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
            "import helper\nprint(helper.VALUE)\n", extra={"helper.py": "VALUE = 7\n"})
        self.assertEqual(stdout.strip(), "7")
        self.assertEqual(report["loaded"], ["pkg/helper.py", "pkg/provider.py"])

    def test_stale_bytecode_next_to_the_source_is_not_executed_or_rewritten(self):
        import os
        import py_compile
        with TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / "helper.py"
            helper.write_bytes(b"VALUE = 'cached'\n")
            stamp = 1700000000
            os.utime(helper, (stamp, stamp))
            cached = Path(importlib.util.cache_from_source(str(helper)))
            py_compile.compile(str(helper), cfile=str(cached), doraise=True)
            before = cached.read_bytes()
            helper.write_bytes(b"VALUE = 'source'\n")       # same size, same mtime
            os.utime(helper, (stamp, stamp))
            script = root / "provider.py"
            script.write_text("import os, sys\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
                              "import helper\nprint(helper.VALUE)\n", encoding="utf-8")
            stdout, _ = probe.execute_child(script, root, {})
            self.assertEqual(stdout.strip(), "source")
            self.assertEqual(cached.read_bytes(), before)
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             ["__pycache__", "helper.py", "provider.py"])

    def test_child_gets_a_minimal_environment(self):
        import os
        os.environ["KAIROS_PROBE_SECRET_CANARY"] = "must-not-leak"
        try:
            stdout, _ = self.run_script("import json, os\nprint(json.dumps(sorted(os.environ)))\n")
        finally:
            del os.environ["KAIROS_PROBE_SECRET_CANARY"]
        names = set(json.loads(stdout))
        self.assertNotIn("KAIROS_PROBE_SECRET_CANARY", names)
        self.assertLessEqual(names - {"LC_CTYPE"}, {"PATH", "HOME", "TMPDIR", "PYTHONDONTWRITEBYTECODE",
                                                     "MPLBACKEND", "NUMBA_CACHE_DIR"})

    def test_failing_provider_is_reported_not_trusted(self):
        with self.assertRaises(probe.ProbeError) as raised:
            self.run_script("raise SystemExit(3)\n")
        self.assertEqual(str(raised.exception), "ORIGINAL_PROVIDER_EXIT_3")
        with self.assertRaises(probe.ProbeError) as raised:
            self.run_script("raise RuntimeError('boom')\n")
        self.assertEqual(str(raised.exception), "ORIGINAL_PROVIDER_EXIT_1")

    def test_parent_network_functions_are_untouched(self):
        before = (socket.socket.connect, socket.create_connection, socket.getaddrinfo)
        self.run_script("print('ok')\n")
        self.assertEqual(before, (socket.socket.connect, socket.create_connection, socket.getaddrinfo))


class RequestTests(unittest.TestCase):
    def test_request_uses_the_provider_contract_and_exact_decimal_prices(self):
        candles = oracle.synthetic_candles(160)
        request = probe.build_request(candles, COSTS)
        self.assertEqual(request["strategy"], {"type": "sma_crossover",
                                               "params": {"fastPeriod": 5, "slowPeriod": 20}})
        self.assertEqual(request["symbols"], [probe.SYMBOL])
        self.assertEqual(request["brokerDataSource"], "kairos_synthetic_fixture")
        rows = request["brokerCandles"][probe.SYMBOL]
        self.assertEqual(len(rows), 160)
        for row, source in zip(rows, candles):
            # Two-decimal prices survive the provider's round(4) unchanged.
            self.assertEqual(Fraction(repr(row["c"])), Fraction(source["c"]))
            self.assertEqual(round(row["c"], 4), row["c"])
        for forbidden in ("allowSyntheticData", "benchmark", "benchmarkSymbol",
                          "stopLoss", "takeProfit", "trailingStop"):
            self.assertNotIn(forbidden, request)
        stops = probe.build_request(candles, dict(COSTS, stop_loss="0.03", trailing_stop="0.04"))
        self.assertEqual((stops["stopLoss"], stops["trailingStop"]), (0.03, 0.04))
        self.assertNotIn("takeProfit", stops)


if __name__ == "__main__":
    unittest.main()
