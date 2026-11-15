"""Source-pinned QA coverage matrix and original Qt screener harness boundaries.

This does not execute a broker, Qt GUI, live feed, LLM or Qlib training. A
source-present entry cannot be promoted into a working app feature.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import unittest

REPO = Path(os.environ.get("FINCEPT_QA_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
MATRIX = Path(__file__).resolve().parents[2] / "docs/audits/FINCEPT_FUNCTIONAL_CAPABILITY_MATRIX_V1_20261115.json"
NATIVE = Path(__file__).resolve().parents[2] / "tools/fincept_audit/qt_screener_results_native"
BASE_SHA = "7716ee8613249fb44c4d14036c5bc16ed6f34e97"
SCHEMA = "fincept_source_pinned_functional_coverage_v1"
STATES = {
    "SOURCE_PRESENT_ONLY",
    "EXECUTED_SYNTHETIC_COMPONENT",
    "HISTORICAL_VM_SYNTHETIC",
    "NATIVE_QT_COMPONENT_PASS_LOCAL",
    "POLICY_FORBIDDEN",
}


def git_blob_bytes(b: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(b)).encode("ascii") + b"\0" + b).hexdigest()


class FunctionalMatrixQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.register = json.loads(MATRIX.read_text("utf-8"))
        cls.rows = cls.register["rows"]

    def test_exact_fork_base_and_draft_scope(self):
        d = self.register
        self.assertEqual(d["schema"], SCHEMA)
        self.assertEqual(d["baseline_sha"], BASE_SHA)
        self.assertEqual(d["baseline_ref"], "main")
        self.assertEqual(d["baseline_repository"], "cometarossa/kairos-fincept-terminal")
        self.assertEqual(d["data_as_of"], "2026-11-15")
        for forbidden in (
            "release_ready", "full_fincept_application_verified",
            "installed_gui_verified", "authenticated_agent_tool_available",
            "broker_auth_enabled", "observations_authoritative_for_trading",
        ):
            self.assertIs(d[forbidden], False)

    def test_all_original_DEV00_and_extras_are_present_exactly_once(self):
        self.assertEqual(len(self.rows), 34)
        self.assertEqual([r["index"] for r in self.rows], list(range(1, 35)))
        self.assertEqual(len(set(r["id"] for r in self.rows)), 34)
        self.assertEqual(len(set(r["source_path"] for r in self.rows)), 34)
        self.assertEqual(self.rows[0]["id"], "qlib_service")
        self.assertEqual(self.rows[24]["id"], "portfolio_mcp_tools")
        self.assertEqual(self.rows[28]["id"], "screener_results_model")

    def test_all_origins_match_original_Git_blobs_not_just_names(self):
        for row in self.rows:
            with self.subTest(source=row["id"]):
                relative = Path(row["source_path"])
                self.assertEqual(relative.parts[0], "fincept-qt")
                self.assertFalse(".." in relative.parts)
                file = REPO / relative
                self.assertTrue(file.is_file(), str(relative))
                self.assertEqual(git_blob_bytes(file.read_bytes()), row["source_git_blob"])

    def test_no_claim_of_full_product_coverage(self):
        for row in self.rows:
            with self.subTest(component=row["id"]):
                self.assertEqual(set(row), {
                    "id", "index", "area", "source_path", "source_git_blob",
                    "component_evidence", "evidence_note", "evidence_pr",
                    "full_feature_status",
                })
                self.assertIn(row["component_evidence"], STATES)
                self.assertIn(row["full_feature_status"],
                              {"NOT_VERIFIED", "FORBIDDEN_BY_KAIROS_CONSTITUTION"})
                self.assertTrue(row["evidence_note"])
                if row["component_evidence"] == "SOURCE_PRESENT_ONLY":
                    self.assertIsNone(row["evidence_pr"])
                elif row["component_evidence"] != "POLICY_FORBIDDEN":
                    self.assertIn(row["evidence_pr"], {11, 26, 27, 41, 43, None})

    def test_original_broker_mutations_are_immutable_forbidden(self):
        denied = [r for r in self.rows
                  if r["full_feature_status"] == "FORBIDDEN_BY_KAIROS_CONSTITUTION"]
        self.assertEqual({x["id"] for x in denied}, {
            "exchange_place_order", "exchange_cancel_order", "exchange_set_leverage"})
        self.assertEqual(len(denied), 3)
        for row in denied:
            self.assertEqual(row["component_evidence"], "POLICY_FORBIDDEN")
            self.assertIsNone(row["evidence_pr"])

    def test_partial_proofs_are_not_full_application_passes(self):
        stats = {s: sum(r["component_evidence"] == s for r in self.rows) for s in STATES}
        self.assertEqual(stats["SOURCE_PRESENT_ONLY"], 20)
        self.assertEqual(stats["POLICY_FORBIDDEN"], 3)
        self.assertEqual(sum(stats[k] for k in STATES if k not in
                             ("SOURCE_PRESENT_ONLY", "POLICY_FORBIDDEN")), 11)
        self.assertEqual(
            {r["id"] for r in self.rows if r["component_evidence"] ==
             "NATIVE_QT_COMPONENT_PASS_LOCAL"},
            {"screener_results_model", "status_badge_widget", "search_bar_widget"},
        )

    def test_original_screener_model_source_pinned(self):
        found = next(x for x in self.rows if x["id"] == "screener_results_model")
        self.assertEqual(found["source_git_blob"],
                         "80506006545c2e4fcb1c3f928120f218da55e406")
        self.assertEqual(found["component_evidence"], "NATIVE_QT_COMPONENT_PASS_LOCAL")
        self.assertEqual(found["full_feature_status"], "NOT_VERIFIED")

    def test_real_cpp_target_linked_and_theme_only_stubbed(self):
        cm = (NATIVE / "CMakeLists.txt").read_text("utf-8")
        self.assertIn("Qt6 6.8.3 EXACT REQUIRED COMPONENTS Core Gui Test Sql", cm)
        self.assertIn("ScreenerResultsModel.cpp", cm)
        self.assertIn('"\u0024{FINCEPT_SOURCE_DIR}/screens/screener/ScreenerResultsModel.cpp"', cm)
        self.assertIn("add_test(NAME tst_original_screener_results", cm)
        s = (NATIVE / "stubs/ui/theme/Theme.h").read_text("utf-8")
        self.assertNotIn("QNetworkAccessManager", s)
        self.assertNotIn("class ScreenerResultsModel", s)
        self.assertNotIn("class ScreenerSortProxy", s)
        self.assertNotIn("ScreenerResultsModel::", s)
        self.assertNotIn("ScreenerSortProxy::", s)
        self.assertNotIn("UnifiedTrading", s)

    def test_screener_really_exercises_sort_missing_and_nonreset(self):
        cpp = (NATIVE / "tst_original_screener_results.cpp").read_text("utf-8")
        for label in (
            "numeric ascending with missing last",
            "numeric descending with missing last",
            "missing price sorting sentinel",
            "changed cell sends dataChanged signal",
            "same row keys do not reset entire table",
            "dynamic column id change resets table",
            "stable key-based lookup",
        ):
            with self.subTest(label=label):
                self.assertIn(label, cpp)
        self.assertIn("ScreenerResultsModel", cpp)
        self.assertIn("ScreenerSortProxy", cpp)
        for forbidden in ("IG_LIVE", "IG_DEMO", "place_order(", "QNetworkAccessManager",
                          "std::system(", "QApplication"):
            self.assertNotIn(forbidden, cpp)

    def test_matrix_has_specific_evidence_not_llm_assumptions(self):
        required = {
            "volatility_indicators": 26,
            "momentum_indicators": 26,
            "trend_indicators": 26,
            "volume_indicators": 26,
            "returns_indicators": 26,
            "portfolio_metrics": 27,
            "vectorbt_provider": 41,
            "backtestingpy_provider": 11,
            "status_badge_widget": 43,
            "search_bar_widget": 43,
        }
        indexed = {r["id"]: r for r in self.rows}
        for key, pr in required.items():
            self.assertEqual(indexed[key]["evidence_pr"], pr)
            self.assertNotEqual(indexed[key]["component_evidence"], "SOURCE_PRESENT_ONLY")
        self.assertIsNone(indexed["screener_results_model"]["evidence_pr"])


if __name__ == "__main__":
    unittest.main()
