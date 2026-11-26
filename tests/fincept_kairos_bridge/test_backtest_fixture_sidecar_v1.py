import unittest
from unittest.mock import patch
from tools.fincept_authority.server_policy import authorize
from research.kairos_bridge_v1.backtest_fixture_sidecar_v1 import run_fixture, TOOL, SCOPE, BacktestDenied
from tools.fincept_audit import backtest_provider_probe_v1 as probe

class BacktestSidecarTests(unittest.TestCase):
    def test_denial_before_compute(self):
        for principal, tool, request in (
            ("synthetic-reviewer", TOOL, {"scope": SCOPE}),
            ("unknown", TOOL, {"scope": SCOPE}),
            ("synthetic-researcher", "broker.place_order", {"scope": SCOPE}),
            ("synthetic-researcher", TOOL, {"scope": SCOPE, "path": "/tmp/x"}),
            ("synthetic-researcher", TOOL, {"scope": SCOPE, "weights": [1, 0]}),
            ("synthetic-researcher", TOOL, {}),
        ):
            with self.subTest(principal=principal, tool=tool), patch.object(probe, "run_multi_asset_scenario") as compute:
                with self.assertRaises(BacktestDenied):
                    run_fixture(principal, tool, request)
                compute.assert_not_called()
    def test_server_owned_policy(self):
        self.assertTrue(authorize("synthetic-researcher", TOOL).allowed)
        self.assertFalse(authorize("synthetic-reviewer", TOOL, request={"approved": True}).allowed)
    def test_actual_fixed_original_backtest(self):
        result = run_fixture("synthetic-researcher", TOOL, {"scope": SCOPE})
        self.assertEqual(result["dataset_class"], "SYNTHETIC_FIXTURE")
        self.assertEqual(result["scientific_status"], "NOT_EVALUATED")
        self.assertIs(result["broker_authority"], False)
        self.assertIs(result["promotion_eligible"], False)
        self.assertEqual(result["result"]["scenario_count"], 1)
        s = result["result"]["scenarios"][0]
        self.assertEqual(s["name"], "multi_asset_75_25")
        self.assertEqual(s["trades"], 7)
        self.assertAlmostEqual(s["total_fees"], 671.6972721743052, places=6)
