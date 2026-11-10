"""Source-only Qt dashboard registration and safety contract (not a Qt build)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
QT = ROOT / "fincept-qt"
WIDGET = QT / "src/screens/dashboard/widgets/KairosResearchStatusWidget.cpp"
HEADER = QT / "src/screens/dashboard/widgets/KairosResearchStatusWidget.h"
TEMPLATES = QT / "src/screens/dashboard/canvas/DashboardTemplates.cpp"
REGISTRY = QT / "src/screens/dashboard/canvas/WidgetRegistry.cpp"
CMAKE = QT / "CMakeLists.txt"


class QtDashboardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.widget = WIDGET.read_text(encoding="utf-8")
        cls.header = HEADER.read_text(encoding="utf-8")
        cls.templates = TEMPLATES.read_text(encoding="utf-8-sig")
        cls.registry = REGISTRY.read_text(encoding="utf-8-sig")
        cls.cmake = CMAKE.read_text(encoding="utf-8")

    def test_tile_registered_and_source_built(self):
        self.assertIn('#include "screens/dashboard/widgets/KairosResearchStatusWidget.h"', self.registry)
        self.assertIn('register_widget({"kairos_research_status"', self.registry)
        self.assertEqual(self.cmake.count("src/screens/dashboard/widgets/KairosResearchStatusWidget.cpp"), 2)
        self.assertIn("class KairosResearchStatusWidget final : public BaseWidget", self.header)

    def test_new_preset_uses_existing_widgets(self):
        self.assertIn('{"kairos_research",', self.templates)
        for widget in ("kairos_research_status", "news", "risk_metrics", "screener"):
            self.assertIn(f'gi("{widget}"', self.templates)
            self.assertIn(f'"{widget}"', self.registry)

    def test_default_is_unverified_and_local(self):
        self.assertIn('current_states_.fill(QStringLiteral("NOT_VERIFIED"))', self.widget)
        self.assertIn('QStandardPaths::AppDataLocation', self.widget)
        self.assertIn('kMaxReportBytes = 16384', self.widget)
        self.assertIn('kMaxAgeSeconds = 86400', self.widget)
        self.assertIn('"LOCAL SYNTHETIC REPORT', self.widget)
        self.assertIn('NO BROKER AUTHORITY', self.widget)

    def test_authority_and_side_effects_are_denied_by_design(self):
        for required in ('"NOT_EVALUATED"', '"SYNTHETIC_FIXTURE"',
                         '"broker_authority"', '"external_api_calls"',
                         '"kairos_science"', '"theoretical_portfolio"'):
            self.assertIn(required, self.widget)
        for forbidden in ('QNetworkAccessManager', 'QProcess', 'QNetworkRequest',
                          'QDesktopServices', 'QSqlDatabase', 'IGApi', 'place_order'):
            self.assertNotIn(forbidden, self.widget)


if __name__ == "__main__":
    unittest.main()
