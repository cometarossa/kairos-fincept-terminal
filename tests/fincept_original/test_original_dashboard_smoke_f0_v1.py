"""Static source-contract regression for the ORIGINAL Fincept Qt F0 dashboard.

These offline checks do NOT render a real Linux GUI, verify provider data, or
replace the native --smoke-test. Native Linux Qt build/real screen smoke are
separate acceptance gates.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "fincept-qt/src/app/ScreenSmokeTest.cpp"
SETUP = ROOT / "fincept-qt/src/app/WindowFrame_Setup.cpp"
DASH = ROOT / "fincept-qt/src/screens/dashboard/DashboardScreen.cpp"


class OriginalFinceptStandaloneDashboardF0(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smoke = SMOKE.read_text()
        cls.setup = SETUP.read_text()
        cls.dash = DASH.read_text()

    def test_real_original_dashboard_factory_is_registered(self):
        self.assertRegex(
            self.setup,
            r'register_factory\("dashboard",\s*\[\]\(\)\s*\{'
            r'\s*return new screens::DashboardScreen;\s*\}\)',
        )

    def test_real_original_dashboard_constructs_canvas_and_scroll_area(self):
        self.assertIn("canvas_ = new DashboardCanvas;", self.dash)
        self.assertIn("scroll_area_->setWidget(canvas_);", self.dash)

    def test_smoke_cannot_pass_empty_or_dashboard_missing_registry(self):
        s = self.smoke
        self.assertIn('const QString kDashboardId = QStringLiteral("dashboard");', s)
        self.assertRegex(s, r"if\s*\(ids\.isEmpty\(\)\)\s*\{")
        self.assertRegex(s, r"if\s*\(!ids\.contains\(kDashboardId\)\)\s*\{")
        before_walk=s[:s.index("for (const QString& id : ids)")]
        self.assertIn("return 4;",before_walk)
        self.assertIn("return 5;",before_walk)

    def test_smoke_checks_original_canvas_in_same_navigation_pass(self):
        s = self.smoke
        loop = s[s.index("for (const QString& id : ids)"):]
        check = 'id == kDashboardId && !router->screen_widget(id)->findChild<screens::DashboardCanvas*>()'
        self.assertIn(check, loop)
        self.assertIn('failures << id;',loop[loop.index(check):])
        self.assertLess(loop.index("spin(kSettleMs);"),loop.index(check))
        self.assertLess(loop.index(check),loop.index("if (failures.isEmpty())"))
        self.assertEqual(loop.count("router->navigate(kDashboardId"), 0)
        self.assertEqual(s.count("router->navigate(id, /*exclusive=*/true);"),1)

    def test_auth_lock_still_denies_without_bypass(self):
        lock = self.smoke.index("auth::InactivityGuard::instance().is_terminal_locked()")
        nav = self.smoke.index("router->navigate(id, /*exclusive=*/true);")
        self.assertLess(lock, nav)
        self.assertIn('return 3;',self.smoke[lock:nav])
        self.assertNotIn("unlock_terminal",self.smoke)


if __name__=="__main__":
    unittest.main()
