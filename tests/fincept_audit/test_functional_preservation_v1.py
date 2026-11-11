"""Source contract, NOT a declaration of 52 working runtime screens."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.fincept_audit.functional_preservation_baseline_v1 import (
    BaselineError, FILES, compare_to_baseline, source_inventory,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE = json.loads(
    (ROOT / "tools/fincept_audit/fincept_source_baseline_v1.json").read_text()
)


def copy_sources(target: Path) -> None:
    for rel in FILES.values():
        out = target / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((ROOT / rel).read_bytes())


class FinceptOriginalBaselineTests(unittest.TestCase):
    def test_original_source_contract_held(self):
        now = source_inventory(ROOT)
        self.assertEqual(compare_to_baseline(now, BASELINE), [])
        self.assertGreaterEqual(len(now["routes"]), 52)
        self.assertGreaterEqual(len(now["widgets"]), 35)
        self.assertGreaterEqual(len(now["templates"]), 6)
        self.assertEqual(
            BASELINE["source_kind"], "STATIC_SOURCE_ONLY_NOT_RUNTIME_PROOF"
        )

    def test_all_six_existing_presets_have_existing_widget_ids(self):
        now = source_inventory(ROOT)
        self.assertEqual(set(BASELINE["templates"]), {
            "portfolio_manager", "hedge_fund", "crypto_trader",
            "equity_trader", "macro_economist", "geopolitics",
        })
        for preset_id, widgets in BASELINE["template_widgets"].items():
            with self.subTest(preset=preset_id):
                self.assertTrue(widgets)
                self.assertTrue(set(widgets).issubset(now["widgets"]))

    def test_removed_original_route_rejected(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            copy_sources(root)
            file = root / FILES["routes"]
            raw = file.read_text(encoding="utf-8-sig")
            file.write_text(raw.replace('register_factory("dashboard"', 'register_factory("removed_dashboard"', 1))
            error = compare_to_baseline(source_inventory(root), BASELINE)
            self.assertIn("REMOVED_ROUTES:dashboard", error)

    def test_changed_factory_class_rejected(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            copy_sources(root)
            file = root / FILES["routes"]
            raw = file.read_text(encoding="utf-8-sig")
            file.write_text(raw.replace("new screens::DashboardScreen;", "new screens::NewsScreen;", 1))
            self.assertIn("CHANGED_ROUTES:dashboard",
                          compare_to_baseline(source_inventory(root), BASELINE))

    def test_modified_original_widget_rejected(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            copy_sources(root)
            file = root / FILES["widgets"]
            raw = file.read_text(encoding="utf-8-sig")
            file.write_text(raw.replace('"Market Indices"', '"Shadow Market Indices"', 1))
            self.assertIn("CHANGED_WIDGETS:indices",
                          compare_to_baseline(source_inventory(root), BASELINE))

    def test_changed_original_preset_rejected(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            copy_sources(root)
            file = root / FILES["templates"]
            raw = file.read_text(encoding="utf-8-sig")
            file.write_text(raw.replace('gi("indices", 0, 0, 4, 5', 'gi("indices", 0, 0, 5, 5', 1))
            self.assertIn("CHANGED_TEMPLATES:portfolio_manager",
                          compare_to_baseline(source_inventory(root), BASELINE))

    def test_new_opt_in_widget_is_allowed(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            copy_sources(root)
            file = root / FILES["widgets"]
            raw = file.read_text(encoding="utf-8-sig")
            # Additive standalone factory, never alter registered original defs.
            raw += '\nregister_widget({"kairos_status", "KAIROS", "Research",\n'
            raw += '   "optional", 4, 3, 2, 2, [](const QJsonObject&) { return widgets::KairosStatus{}; }});\n'
            file.write_text(raw)
            now = source_inventory(root)
            self.assertIn("kairos_status", now["widgets"])
            self.assertEqual(compare_to_baseline(now, BASELINE), [])

    def test_unknown_preset_widget_is_rejected(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            copy_sources(root)
            file = root / FILES["templates"]
            raw = file.read_text(encoding="utf-8-sig")
            raw = raw.replace('gi("indices", 0, 0, 4, 5', 'gi("missing_in_registry", 0, 0, 4, 5', 1)
            file.write_text(raw)
            errors = compare_to_baseline(source_inventory(root), BASELINE)
            self.assertIn("UNKNOWN_TEMPLATE_WIDGET:portfolio_manager:missing_in_registry", errors)

    def test_duplicate_original_route_is_rejected(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            copy_sources(root)
            file = root / FILES["routes"]
            with file.open("a") as h:
                h.write('\ndock_router_->register_factory("dashboard", []() { return new screens::DashboardScreen; });\n')
            with self.assertRaisesRegex(BaselineError, "DUPLICATE_ROUTE"):
                source_inventory(root)


if __name__ == "__main__":
    unittest.main()
