"""Negative mutation tests of ORIGINAL Fincept Qt screen-smoke source safety."""
from __future__ import annotations

from pathlib import Path
import unittest

from tools.fincept_audit.qt_screen_smoke_contract_v1 import (
    RELATIVE_SOURCE, SCHEMA, analyze,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / RELATIVE_SOURCE).read_text(encoding="utf-8-sig")


class ScreenSmokeSourceSafetyTests(unittest.TestCase):
    def test_actual_original_smoke_guard_contract(self):
        report = analyze(SOURCE)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["safety_guard_status"], "PASS_SOURCE_CHECKS")
        self.assertEqual(report["violations"], [])
        self.assertFalse(report["runtime_gui_pass"])
        self.assertFalse(report["native_gui_compiled"])
        self.assertFalse(report["release_ready"])
        self.assertFalse(report["broker_authority"])

    def test_original_empty_registry_false_pass_is_reported(self):
        report = analyze(SOURCE)
        self.assertIn("EMPTY_REGISTRY_CAN_FALSE_PASS", report["runtime_gaps"])
        self.assertIn("NATIVE_QT_GUI_AND_SHOWEVENT_SIDE_EFFECTS_NOT_TESTED",
                      report["runtime_gaps"])

    def test_missing_pin_guard_is_detected(self):
        changed = SOURCE.replace("is_terminal_locked()", "is_terminal_unlocked()")
        self.assertNotEqual(changed, SOURCE)
        self.assertIn("MISSING_NULL_OR_PIN_OR_FULL_REGISTRY_ITERATION",
                      analyze(changed)["violations"])

    def test_pin_lock_bypass_is_detected(self):
        changed = SOURCE.replace("return 3;", "return 0;", 1)
        self.assertIn("PIN_LOCK_NOT_REJECTED", analyze(changed)["violations"])

    def test_no_router_failure_code_is_detected(self):
        changed = SOURCE.replace("return 2;", "return 0;", 1)
        self.assertIn("NULL_ROUTER_NOT_REJECTED", analyze(changed)["violations"])

    def test_scope_of_registered_screens_cannot_silently_narrow(self):
        changed = SOURCE.replace("router->all_screen_ids()", "router->one_screen_id()")
        self.assertIn("MISSING_NULL_OR_PIN_OR_FULL_REGISTRY_ITERATION",
                      analyze(changed)["violations"])

    def test_exclusive_navigation_cannot_be_silently_removed(self):
        changed = SOURCE.replace("router->navigate(id, /*exclusive=*/true)",
                                 "router->navigate(id, /*exclusive=*/false)")
        self.assertIn("MISSING_CONSTRUCTION_BREADCRUMB_OR_RESULT_CHECK",
                      analyze(changed)["violations"])

    def test_pre_construction_failure_breadcrumb_cannot_be_removed(self):
        changed = SOURCE.replace("[Smoke] >>> constructing", "[Smoke] hidden")
        self.assertIn("MISSING_CONSTRUCTION_BREADCRUMB_OR_RESULT_CHECK",
                      analyze(changed)["violations"])

    def test_screen_construction_failure_must_not_return_success(self):
        before = "    return 1;\n}\n\n} // namespace fincept"
        after = "    return 0;\n}\n\n} // namespace fincept"
        self.assertIn(before, SOURCE)
        changed = SOURCE.replace(before, after)
        self.assertIn("MISSING_NONZERO_SCREEN_FAILURE_RETURN",
                      analyze(changed)["violations"])


if __name__ == "__main__":
    unittest.main()

