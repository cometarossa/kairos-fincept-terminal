import unittest
from temporal_contract import preflight


def fixture():
    return dict(schema_version="fincept-kairos-science-v1", attempt_id="fixture-001",
                source_id="fixture-generator", content_digest="sha256:dummy-fixture",
                observed_at="2024-01-01T00:00:00Z",
                available_at="2024-01-01T00:01:00Z",
                received_at="2024-01-01T00:02:00Z",
                decision_as_of="2024-01-01T00:03:00Z",
                research_clock="HISTORICAL_AS_OF_DISCOVERY",
                dataset_class="SYNTHETIC_FIXTURE", entitlement_status="ALLOWED")


class TemporalContractTests(unittest.TestCase):
    def test_fixture_not_admitted(self):
        self.assertEqual(preflight(fixture())["status"], "FIXTURE_ONLY")
        self.assertFalse(preflight(fixture())["authority"])

    def test_future_available_rejected(self):
        x = fixture()
        x["available_at"] = "2024-01-01T00:04:00Z"
        self.assertIn("future_data_leakage", preflight(x)["reasons"])

    def test_late_receipt_rejected(self):
        x = fixture()
        x["received_at"] = "2024-01-01T00:05:00Z"
        self.assertIn("received_after_decision", preflight(x)["reasons"])

    def test_missing_source_rejected(self):
        x = fixture()
        del x["source_id"]
        self.assertEqual(preflight(x)["status"], "REJECT")

    def test_unknown_schema_rejected(self):
        x = fixture()
        x["schema_version"] = "v2"
        self.assertEqual(preflight(x)["status"], "REJECT")

    def test_embedded_broker_route_rejected(self):
        x = fixture()
        x["broker_order"] = {"action": "buy"}
        self.assertEqual(preflight(x)["status"], "REJECT")

    def test_no_entitlement_rejected(self):
        x = fixture()
        x["entitlement_status"] = "UNKNOWN"
        self.assertEqual(preflight(x)["status"], "REJECT")

    def test_prospective_requires_external_ledger(self):
        x = fixture()
        x["research_clock"] = "PROSPECTIVE_PRE_EVENT"
        x["frozen_at"] = "2024-01-01T00:03:00Z"
        self.assertEqual(preflight(x)["status"], "REJECT")

    def test_market_is_only_eligible_not_authorized(self):
        x = fixture()
        x["dataset_class"] = "MARKET_OBSERVED"
        y = preflight(x)
        self.assertEqual(y["status"], "ELIGIBLE_FOR_INDEPENDENT_REVIEW")
        self.assertFalse(y["authority"])

    def test_naive_time_rejected(self):
        x = fixture()
        x["observed_at"] = "2024-01-01T00:00:00"
        self.assertEqual(preflight(x)["status"], "REJECT")


if __name__ == "__main__":
    unittest.main()
